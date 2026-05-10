"""
DEBATE AGENTS — Agent 6A (Deal Champion) & Agent 6B (Risk Partner)

Inspired by TauricResearch/TradingAgents Bull/Bear Researcher architecture.
Instead of a single Red Team agent, we split the adversarial review into
a structured debate between two personas:

  Agent 6A — Deal Champion (Bullish)
    Argues FOR the investment. Defends the valuation, highlights upside,
    and pushes back on overly conservative assumptions.

  Agent 6B — Risk Partner (Bearish)
    Argues AGAINST the investment. Attacks assumptions, cites forensic
    red flags, and stress-tests the thesis with pre-mortem scenarios.

The debate runs for up to MAX_DEBATE_ROUNDS rounds. Each round:
  1. Champion makes a case citing deal_context evidence
  2. Risk Partner rebuts with counter-evidence
  3. Both outputs are logged into a debate_transcript

The transcript is then passed to the IC Agent (Agent 7) for final decision.

Architecture:
  - Uses Anthropic Claude API (or AWS Bedrock as fallback)
  - Each debater has access to query_knowledge_base for RAG grounding
  - Structured Pydantic-style JSON output via tool_use
  - Full debate transcript preserved for UI "struggle" visualization

Author: Moosa (Project Veritas)
Date: May 2026
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from memory.memory_agent import get_methodology_context

logger = logging.getLogger(__name__)

MAX_DEBATE_ROUNDS = 3


def _execute_tavily_search(query: str) -> str:
    """Executes a Tavily web search and returns formatted results."""
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if not tavily_key:
        return "Tavily API key not set. Web search unavailable."

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
        res = client.search(query=query, search_depth="advanced", max_results=3)

        formatted = []
        for r in res.get("results", []):
            formatted.append(
                f"SOURCE: {r.get('url', 'N/A')}\n"
                f"TITLE: {r.get('title', 'N/A')}\n"
                f"CONTENT: {r.get('content', '')[:500]}\n"
            )
        return "\n---\n".join(formatted) if formatted else "No results found."
    except Exception as e:
        return f"Web search error: {str(e)}"

# =====================================================================
# SYSTEM PROMPTS — Two opposing personas
# =====================================================================

CHAMPION_SYSTEM_PROMPT = """You are the DEAL CHAMPION at a top-tier PE fund's Investment Committee.
All monetary values are in USD millions (USD M).

YOUR MANDATE: Argue FOR this investment with conviction.

RULES:
1. Every claim MUST cite specific data (forensics, valuation, market intel)
2. Acknowledge legitimate risks but explain why they are manageable or priced in
3. Never dismiss forensic red flags — explain mitigation strategies
4. Reference specific valuation numbers, multiples, and growth rates
5. If the Risk Partner raises a valid point, concede it but propose a structural solution
6. Use query_knowledge_base AND search_web to gather evidence BEFORE submitting
7. In your sources_cited, list EVERY source (RAG document name or web URL) you used

OUTPUT FORMAT: Respond with a structured JSON argument using the submit_argument tool."""

RISK_PARTNER_SYSTEM_PROMPT = """You are the RISK PARTNER at a top-tier PE fund's Investment Committee.
All monetary values are in USD millions (USD M).

YOUR MANDATE: Stress-test this investment ruthlessly.

RULES:
1. Every critique MUST cite specific data (forensics, valuation, market intel)
2. Attack the weakest assumptions first: growth rates, margin sustainability, governance
3. If forensic_score < 70, hammer the QoE issues
4. Run pre-mortem scenarios: "What if revenue growth is 5% instead of 15%?"
5. Challenge the Do Not Exceed price — is it truly conservative enough?
6. Use query_knowledge_base AND search_web to find counter-evidence BEFORE submitting
7. In your sources_cited, list EVERY source (RAG document name or web URL) you used

OUTPUT FORMAT: Respond with a structured JSON rebuttal using the submit_argument tool."""

# =====================================================================
# TOOL DEFINITIONS — Shared by both debaters
# =====================================================================

DEBATE_TOOLS = [
    {
        "name": "query_knowledge_base",
        "description": (
            "Retrieves methodology passages from the institutional PDF library "
            "to ground your argument in academic or industry evidence. "
            "Use this to cite Damodaran, McKinsey, Rosenbaum, ICRA, or CFA governance frameworks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "methodology_type": {
                    "type": "string",
                    "description": "comparable_company / dcf_terminal_value / lbo_returns / credit_analysis / sector_specific / india_market_context"
                },
                "sector": {
                    "type": "string",
                    "description": "Sector name (optional)"
                }
            },
            "required": ["methodology_type"]
        }
    },
    {
        "name": "search_web",
        "description": (
            "Searches the web via Tavily for real-time market data, news, analyst reports, "
            "regulatory filings, or competitive intelligence to support your argument. "
            "Use this for current events, recent earnings, or breaking news about the target."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for real-time intelligence"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "submit_argument",
        "description": "Submit your structured argument for this debate round. You MUST call at least one research tool (query_knowledge_base or search_web) before submitting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {
                    "type": "string",
                    "enum": ["BULL", "BEAR"],
                    "description": "Your stance"
                },
                "headline": {
                    "type": "string",
                    "description": "One-line summary of your argument (max 100 chars)"
                },
                "argument": {
                    "type": "string",
                    "description": "Your full argument with citations. All values in USD millions."
                },
                "evidence_cited": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of specific data points cited from the deal"
                },
                "sources_cited": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of sources used. Format: 'RAG: Damodaran_Investment_Valuation p.45' or 'WEB: reuters.com/article/...'. Every claim must have a source."
                },
                "concessions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Points you concede to the opposing side"
                },
                "conviction_score": {
                    "type": "integer",
                    "description": "How strongly you feel about your position (1-10)"
                }
            },
            "required": ["position", "headline", "argument",
                         "evidence_cited", "sources_cited", "conviction_score"]
        }
    }
]


# =====================================================================
# HELPER: Build the deal context summary for the debaters
# =====================================================================

def _build_deal_summary(deal_context: Dict[str, Any]) -> str:
    """
    Formats the full deal_context into a readable brief for the debaters.
    This ensures both sides have identical information.
    """
    company = deal_context.get("company_name", "Unknown")
    sector = deal_context.get("sector", "Unknown")

    # Forensics summary (USD millions)
    forensics = deal_context.get("forensics", {})
    # Support both old (Rs Cr) and new (USD M) field names
    ebitda_reported = forensics.get('reported_ebitda_usd_m', forensics.get('reported_ebitda_cr', 'N/A'))
    ebitda_adjusted = forensics.get('adjusted_ebitda_usd_m', forensics.get('adjusted_ebitda_cr', 'N/A'))
    forensic_block = (
        f"Forensic Score: {forensics.get('forensic_score', 'N/A')}/100\n"
        f"Quality of Earnings: {forensics.get('quality_of_earnings', 'N/A')}\n"
        f"Reported EBITDA: ${ebitda_reported}M\n"
        f"Adjusted EBITDA: ${ebitda_adjusted}M\n"
        f"EBITDA Adjustment: {forensics.get('ebitda_adjustment_pct', 'N/A')}%\n"
        f"Red Flags: {json.dumps(forensics.get('red_flags', []))}\n"
        f"Green Flags: {json.dumps(forensics.get('green_flags', []))}\n"
        f"Related Party Risk: {forensics.get('related_party_risk', 'N/A')}\n"
        f"Debt Capacity: {forensics.get('debt_capacity_assessment', 'N/A')}"
    )

    # Market intel summary
    market = deal_context.get("market_intel", {})
    market_block = (
        f"Competitive Position: {market.get('competitive_position', 'N/A')}\n"
        f"Sector PE Activity: {market.get('sector_pe_activity', 'N/A')}\n"
        f"Implied Entry Multiple: {market.get('implied_entry_multiple_range', 'N/A')}"
    )

    # Management summary
    mgmt = deal_context.get("management", {})
    mgmt_block = (
        f"Management Score: {mgmt.get('management_score', 'N/A')}/100\n"
        f"Board Independence: {mgmt.get('board_independence', 'N/A')}\n"
        f"Governance Flags: {json.dumps(mgmt.get('governance_flags', []))}\n"
        f"Succession Risk: {mgmt.get('succession_risk', 'N/A')}\n"
        f"Analyst Sentiment: {mgmt.get('analyst_sentiment', 'N/A')}"
    )

    # Valuation summary (USD millions)
    val = deal_context.get("valuation", {})
    dne = val.get('do_not_exceed_ev_usd_m', val.get('do_not_exceed_price_cr', 'N/A'))
    ff = val.get('football_field_usd_m', val.get('football_field', {}))
    val_block = (
        f"PE Decision: {val.get('pe_decision', 'N/A')}\n"
        f"Do Not Exceed EV: ${dne}M\n"
        f"Convergence Quality: {val.get('convergence_quality', 'N/A')}\n"
        f"Convergence Spread: {val.get('convergence_spread_pct', 'N/A')}%\n"
        f"Football Field (USD M): {json.dumps(ff, indent=2)}\n"
        f"Key Risks: {json.dumps(val.get('key_risks', []))}\n"
        f"Methods Used: {json.dumps(val.get('methods_used', []))}"
    )

    return (
        f"=== DEAL BRIEF FOR IC DEBATE (All values USD Millions) ===\n"
        f"Company: {company}\n"
        f"Sector: {sector}\n\n"
        f"--- FORENSIC ANALYSIS (Agent 2) ---\n{forensic_block}\n\n"
        f"--- MARKET INTELLIGENCE (Agent 3) ---\n{market_block}\n\n"
        f"--- MANAGEMENT ASSESSMENT (Agent 4) ---\n{mgmt_block}\n\n"
        f"--- VALUATION (Agent 5) ---\n{val_block}\n"
        f"=== END DEAL BRIEF ==="
    )


# =====================================================================
# SINGLE DEBATER TURN
# =====================================================================

def _run_debater_turn(
    role: str,
    system_prompt: str,
    deal_summary: str,
    debate_history: List[Dict[str, Any]],
    round_num: int,
    sector: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Runs a single turn for one debater (Champion or Risk Partner).
    Returns the structured argument or a fallback.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    # Build the user message with full context
    history_text = ""
    if debate_history:
        history_text = "\n\n--- DEBATE HISTORY ---\n"
        for entry in debate_history:
            history_text += (
                f"\n[Round {entry['round']}] {entry['role']} ({entry['position']}):\n"
                f"Headline: {entry['headline']}\n"
                f"Argument: {entry['argument']}\n"
                f"Conviction: {entry['conviction_score']}/10\n"
                f"Concessions: {json.dumps(entry.get('concessions', []))}\n"
            )
        history_text += "--- END HISTORY ---\n"

    user_message = (
        f"This is Round {round_num} of the IC debate.\n\n"
        f"{deal_summary}\n\n"
        f"{history_text}\n\n"
        f"Please review ALL evidence and submit your argument for Round {round_num}. "
        f"You MUST call at least one research tool (query_knowledge_base or search_web) "
        f"to gather evidence BEFORE calling submit_argument. "
        f"In your sources_cited field, list every source as 'RAG: filename' or 'WEB: url'."
    )

    messages = [{"role": "user", "content": user_message}]

    max_iter = 4
    for iteration in range(max_iter):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                system=system_prompt,
                tools=DEBATE_TOOLS,
                messages=messages,
            )
        except Exception as e:
            logger.error(f"[{role}] API error: {e}")
            return _fallback_argument(role, round_num, str(e))

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if block.name == "submit_argument":
                        result = block.input
                        result["role"] = role
                        result["round"] = round_num
                        print(f"  [{role}] Round {round_num}: {result.get('headline', '...')}")
                        print(f"  [{role}] Conviction: {result.get('conviction_score', '?')}/10")
                        return result

                    elif block.name == "query_knowledge_base":
                        kb_result = get_methodology_context(
                            block.input.get("methodology_type", ""),
                            sector=block.input.get("sector", sector)
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": kb_result if isinstance(kb_result, str) else json.dumps(kb_result)
                        })

                    elif block.name == "search_web":
                        web_result = _execute_tavily_search(block.input.get("query", ""))
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": web_result
                        })

            messages.append({"role": "assistant", "content": response.content})
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            # Agent ended without submitting — ask it to use the tool
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": "Please submit your argument using the submit_argument tool."
            })

    return _fallback_argument(role, round_num, "Max iterations reached")


def _fallback_argument(role: str, round_num: int, reason: str) -> Dict[str, Any]:
    """Returns a safe fallback if the debater fails."""
    return {
        "role": role,
        "round": round_num,
        "position": "BULL" if role == "DEAL_CHAMPION" else "BEAR",
        "headline": f"[FALLBACK] {role} could not generate argument",
        "argument": f"Agent failed to produce structured output. Reason: {reason}",
        "evidence_cited": [],
        "concessions": [],
        "conviction_score": 1
    }


# =====================================================================
# MAIN DEBATE ORCHESTRATOR
# =====================================================================

def run_debate(
    deal_context: Dict[str, Any],
    max_rounds: int = MAX_DEBATE_ROUNDS,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Runs the full Bull vs Bear debate.

    Returns:
        {
            "debate_transcript": [...],
            "total_rounds": int,
            "champion_final_conviction": int,
            "risk_partner_final_conviction": int,
            "consensus_reached": bool,
            "consensus_type": "BULL_DOMINANT" | "BEAR_DOMINANT" | "CONTESTED"
        }
    """
    company = deal_context.get("company_name", "Unknown")
    sector = deal_context.get("sector", "")

    print(f"\n{'='*60}")
    print(f"  IC DEBATE: {company}")
    print(f"  Deal Champion vs Risk Partner")
    print(f"  Max Rounds: {max_rounds}")
    print(f"{'='*60}")

    deal_summary = _build_deal_summary(deal_context)
    debate_transcript: List[Dict[str, Any]] = []

    for round_num in range(1, max_rounds + 1):
        print(f"\n--- Round {round_num}/{max_rounds} ---")

        # Champion argues first
        print(f"  [DEAL CHAMPION] Preparing argument...")
        champion_arg = _run_debater_turn(
            role="DEAL_CHAMPION",
            system_prompt=CHAMPION_SYSTEM_PROMPT,
            deal_summary=deal_summary,
            debate_history=debate_transcript,
            round_num=round_num,
            sector=sector,
            api_key=api_key
        )
        debate_transcript.append(champion_arg)

        # Risk Partner rebuts
        print(f"  [RISK PARTNER] Preparing rebuttal...")
        risk_arg = _run_debater_turn(
            role="RISK_PARTNER",
            system_prompt=RISK_PARTNER_SYSTEM_PROMPT,
            deal_summary=deal_summary,
            debate_history=debate_transcript,
            round_num=round_num,
            sector=sector,
            api_key=api_key
        )
        debate_transcript.append(risk_arg)

        # Check for early consensus
        bull_conv = champion_arg.get("conviction_score", 5)
        bear_conv = risk_arg.get("conviction_score", 5)

        # If both sides converge (bull drops below 4 or bear drops below 4)
        if bull_conv <= 3 and bear_conv >= 8:
            print(f"\n  EARLY CONSENSUS: Risk Partner dominant (Bull withdrew)")
            break
        elif bear_conv <= 3 and bull_conv >= 8:
            print(f"\n  EARLY CONSENSUS: Deal Champion dominant (Bear withdrew)")
            break

    # Determine consensus
    final_bull = debate_transcript[-2].get("conviction_score", 5) if len(debate_transcript) >= 2 else 5
    final_bear = debate_transcript[-1].get("conviction_score", 5) if len(debate_transcript) >= 1 else 5

    if final_bull >= 7 and final_bear <= 4:
        consensus_type = "BULL_DOMINANT"
    elif final_bear >= 7 and final_bull <= 4:
        consensus_type = "BEAR_DOMINANT"
    else:
        consensus_type = "CONTESTED"

    result = {
        "debate_transcript": debate_transcript,
        "total_rounds": len(debate_transcript) // 2,
        "champion_final_conviction": final_bull,
        "risk_partner_final_conviction": final_bear,
        "consensus_reached": consensus_type != "CONTESTED",
        "consensus_type": consensus_type
    }

    print(f"\n{'='*60}")
    print(f"  DEBATE COMPLETE")
    print(f"  Rounds: {result['total_rounds']}")
    print(f"  Champion Conviction: {final_bull}/10")
    print(f"  Risk Partner Conviction: {final_bear}/10")
    print(f"  Consensus: {consensus_type}")
    print(f"{'='*60}")

    return result
