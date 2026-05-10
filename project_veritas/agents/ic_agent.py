"""
IC AGENT — Agent 7 (Investment Committee)

Inspired by TauricResearch/TradingAgents Portfolio Manager pattern.
This is the final executive authority in the Project Veritas pipeline.

It reads:
  1. The full deal_context (Agents 1-5 outputs)
  2. The complete debate transcript (Agent 6A vs 6B)

It decides:
  - APPROVE: Proceed to term sheet
  - CONDITIONAL_APPROVE: Proceed but with specific conditions
  - REJECT: Walk away from the deal

Memory Reflection (TradingAgents-inspired):
  - Logs every decision to a local SQLite database
  - On future deals, retrieves past decisions to enforce consistency
  - e.g., "We rejected Company X for 15% growth with weak governance.
           Why is Champion arguing for Company Y with 12% growth
           and the same governance flags?"

Author: Moosa (Project Veritas)
Date: May 2026
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)

# Path for the IC decision memory database
IC_MEMORY_DB = os.path.join(
    os.path.dirname(__file__), "..", "memory", "ic_decisions.db"
)

# =====================================================================
# IC SYSTEM PROMPT
# =====================================================================

IC_SYSTEM_PROMPT = """You are the INVESTMENT COMMITTEE CHAIR at a top-tier PE fund.

You have just witnessed a structured debate between the Deal Champion (bullish)
and the Risk Partner (bearish). You have also reviewed the full deal context
including forensic analysis, market intelligence, management assessment,
and valuation from Agents 1-5.

YOUR ROLE:
You are the final decision-maker. You do not re-analyze the numbers.
Instead, you evaluate:
1. The QUALITY of arguments from both sides — who cited better evidence?
2. Whether the Deal Champion adequately addressed the Risk Partner's concerns
3. Whether the valuation leaves enough margin of safety
4. Whether the management team is trustworthy enough to partner with
5. Whether the forensic quality of earnings supports the entry price

DECISION CRITERIA:
- APPROVE: Strong bull case, risks are well-understood and priced in,
  management is trustworthy, forensic score >= 70, valuation convergence is GOOD+
- CONDITIONAL_APPROVE: Decent opportunity but specific conditions must be met
  before closing (e.g., "proceed only if promoter pledge drops below 10%")
- REJECT: Bear case is more compelling, deal-killer risks exist, or the
  margin of safety is insufficient

PAST DECISIONS:
You will be provided with your past IC decisions (if any). Use them to
maintain consistency. If you rejected a similar deal before, explain why
this one is different — or reject it too.

RULES:
1. Never approve a deal where forensic_score < 50
2. Never approve if governance_flags contain "FRAUD" or "SEBI_NOTICE"
3. If convergence_quality is "POOR", require at least CONDITIONAL_APPROVE conditions
4. Always explain your reasoning by referencing specific debate arguments
5. Your memo will be read by Limited Partners — precision and clarity matter"""

# =====================================================================
# TOOL DEFINITIONS
# =====================================================================

IC_TOOLS = [
    {
        "name": "submit_ic_decision",
        "description": "Submit the final Investment Committee decision.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": ["APPROVE", "CONDITIONAL_APPROVE", "REJECT"],
                    "description": "The IC's final decision"
                },
                "conviction_level": {
                    "type": "string",
                    "enum": ["HIGH", "MEDIUM", "LOW"],
                    "description": "How confident the IC is in this decision"
                },
                "executive_summary": {
                    "type": "string",
                    "description": "2-3 paragraph summary of the decision rationale"
                },
                "key_thesis_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Top 3-5 points supporting the decision"
                },
                "conditions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Conditions for CONDITIONAL_APPROVE (empty if APPROVE/REJECT)"
                },
                "deal_killers_identified": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Any absolute deal-breakers found"
                },
                "recommended_entry_price_cr": {
                    "type": "number",
                    "description": "The IC's recommended maximum entry EV in Rs Crores"
                },
                "debate_winner": {
                    "type": "string",
                    "enum": ["DEAL_CHAMPION", "RISK_PARTNER", "DRAW"],
                    "description": "Who made the more compelling case?"
                },
                "strongest_bull_argument": {
                    "type": "string",
                    "description": "The single most compelling point from the Champion"
                },
                "strongest_bear_argument": {
                    "type": "string",
                    "description": "The single most compelling point from the Risk Partner"
                },
                "next_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Immediate next steps if approved/conditionally approved"
                }
            },
            "required": [
                "decision", "conviction_level", "executive_summary",
                "key_thesis_points", "conditions", "deal_killers_identified",
                "recommended_entry_price_cr", "debate_winner",
                "strongest_bull_argument", "strongest_bear_argument",
                "next_steps"
            ]
        }
    }
]


# =====================================================================
# SQLITE MEMORY — Decision Reflection
# =====================================================================

def _init_memory_db():
    """Creates the IC decisions table if it doesn't exist."""
    os.makedirs(os.path.dirname(IC_MEMORY_DB), exist_ok=True)
    conn = sqlite3.connect(IC_MEMORY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ic_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            company_name TEXT NOT NULL,
            sector TEXT,
            decision TEXT NOT NULL,
            conviction TEXT,
            recommended_price_cr REAL,
            forensic_score INTEGER,
            management_score INTEGER,
            executive_summary TEXT,
            debate_winner TEXT,
            deal_killers TEXT
        )
    """)
    conn.commit()
    conn.close()


def _get_past_decisions(limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieves the last N IC decisions for reflection."""
    _init_memory_db()
    conn = sqlite3.connect(IC_MEMORY_DB)
    cursor = conn.execute(
        "SELECT * FROM ic_decisions ORDER BY id DESC LIMIT ?", (limit,)
    )
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def _save_decision(
    company_name: str,
    sector: str,
    decision: Dict[str, Any],
    forensic_score: int,
    management_score: int
):
    """Persists an IC decision to the memory database."""
    _init_memory_db()
    conn = sqlite3.connect(IC_MEMORY_DB)
    conn.execute(
        """INSERT INTO ic_decisions
           (timestamp, company_name, sector, decision, conviction,
            recommended_price_cr, forensic_score, management_score,
            executive_summary, debate_winner, deal_killers)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(),
            company_name,
            sector,
            decision.get("decision", "UNKNOWN"),
            decision.get("conviction_level", "LOW"),
            decision.get("recommended_entry_price_cr", 0),
            forensic_score,
            management_score,
            decision.get("executive_summary", ""),
            decision.get("debate_winner", "DRAW"),
            json.dumps(decision.get("deal_killers_identified", []))
        )
    )
    conn.commit()
    conn.close()


def make_decision(
    decision: Dict[str, Any],
    debate: Dict[str, Any],
    forensic: Dict[str, Any],
    financials: Dict[str, Any],
    valuation: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Consistency check before finalising verdict.
    Ensures the IC decision respects conviction, forensic and valuation floors.
    """
    verdict = decision.get("decision", "REJECT")
    reasoning = [decision.get("executive_summary", "")]
    
    champion_score = debate.get('champion_final_conviction', 5)
    risk_score = debate.get('risk_partner_final_conviction', 5)
    forensic_total = forensic.get('forensic_score', 0)
    
    current_price = financials.get('current_price') or valuation.get('current_price') or 0
    fair_value = valuation.get('fair_equity_value_m') or valuation.get('fair_price') or 0
    
    if fair_value <= 0:
        return decision # Avoid division by zero

    # Rule: Can't REJECT if champion >8 AND forensic >75 
    # unless valuation premium is extreme (>50% above fair)
    if verdict == "REJECT":
        premium = (current_price - fair_value) / fair_value
        if champion_score >= 8 and forensic_total >= 75:
            if premium < 0.50:
                verdict = "HOLD"
                reasoning.append(
                    "Verdict upgraded from REJECT to HOLD: "
                    "Strong champion conviction and healthy "
                    "forensic score do not support rejection "
                    "at current valuation premium."
                )

    # Rule: Can't APPROVE if forensic <60
    if verdict == "APPROVE" and forensic_total < 60:
        verdict = "HOLD"
        reasoning.append(
            "Verdict downgraded from APPROVE to HOLD: "
            "Forensic score below 60 indicates earnings "
            "quality concerns that prevent full approval."
        )

    # Rule: Can't APPROVE if valuation premium >40%
    if verdict == "APPROVE" and current_price > fair_value * 1.40:
        verdict = "HOLD"
        reasoning.append(
            "Verdict downgraded from APPROVE to HOLD: "
            "Current price exceeds fair value by >40%."
        )
        
    # Update decision object
    decision["decision"] = verdict
    decision["executive_summary"] = " | ".join([r for r in reasoning if r])
    return decision


# =====================================================================
# IC AGENT RUNNER
# =====================================================================

def make_decision(decision: Dict[str, Any], debate: Dict[str, Any], forensic: Dict[str, Any], financials: Dict[str, Any], valuation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforces institutional consistency rules on the IC's decision.
    """
    verdict = decision.get("decision", "REJECT")
    champion_score = debate.get("champion_final_conviction", 0)
    forensic_total = forensic.get("forensic_score", 0)
    reasoning = decision.get("executive_summary", "")
    
    current_price = financials.get("current_price", 0)
    fair_value_ps = (valuation.get("fair_equity_value_m", 0) / financials.get("shares_outstanding_M", 1)) if financials.get("shares_outstanding_M") else 0
    
    # Rule 1: Can't REJECT if champion > 8 AND forensic > 75 
    # unless valuation premium is extreme (>50% above fair)
    if verdict == "REJECT":
        premium = 0
        if fair_value_ps > 0:
            premium = (current_price - fair_value_ps) / fair_value_ps
            
        if champion_score >= 8 and forensic_total >= 75:
            if premium < 0.50:
                decision["decision"] = "HOLD"
                decision["executive_summary"] = (
                    "**[VERDICT UPGRADE: HOLD]** Strong deal champion conviction and "
                    "healthy forensic score do not support outright rejection at current "
                    "valuation levels. Decision shifted to HOLD for further analysis.\n\n"
                ) + reasoning

    # Rule 2: Can't APPROVE if forensic < 60
    if verdict == "APPROVE" and forensic_total < 60:
        decision["decision"] = "HOLD"
        decision["executive_summary"] = (
            "**[VERDICT DOWNGRADE: HOLD]** Forensic score below 60 indicates "
            "earnings quality or leverage risks that preclude an immediate APPROVE. "
            "Decision shifted to HOLD pending forensic audit.\n\n"
        ) + reasoning

    return decision

def run_ic_agent(
    deal_context: Dict[str, Any],
    debate_result: Dict[str, Any],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Runs the IC Agent. Reads deal_context + debate transcript,
    checks past decisions for consistency, and issues final verdict.
    """
    import anthropic

    company = deal_context.get("company_name", "Unknown")
    sector = deal_context.get("sector", "")

    print(f"\n{'='*60}")
    print(f"  INVESTMENT COMMITTEE — {company}")
    print(f"  Reading debate transcript and deal context...")
    print(f"{'='*60}")

    # Build the debate transcript text
    transcript_text = ""
    for entry in debate_result.get("debate_transcript", []):
        transcript_text += (
            f"\n[Round {entry.get('round', '?')}] "
            f"{entry.get('role', 'UNKNOWN')} ({entry.get('position', '?')}):\n"
            f"Headline: {entry.get('headline', 'N/A')}\n"
            f"Argument: {entry.get('argument', 'N/A')}\n"
            f"Evidence: {json.dumps(entry.get('evidence_cited', []))}\n"
            f"Concessions: {json.dumps(entry.get('concessions', []))}\n"
            f"Conviction: {entry.get('conviction_score', '?')}/10\n"
        )

    # Get past decisions for reflection
    past_decisions = _get_past_decisions(limit=5)
    past_text = ""
    if past_decisions:
        past_text = "\n\n--- YOUR PAST IC DECISIONS (for consistency) ---\n"
        for pd in past_decisions:
            past_text += (
                f"\n[{pd['timestamp']}] {pd['company_name']} ({pd['sector']}): "
                f"{pd['decision']} (Conviction: {pd['conviction']})\n"
                f"  Forensic Score: {pd['forensic_score']}, "
                f"Mgmt Score: {pd['management_score']}\n"
                f"  Summary: {pd['executive_summary'][:200]}...\n"
            )
        past_text += "--- END PAST DECISIONS ---\n"

    # Key metrics for quick reference
    forensics = deal_context.get("forensics", {})
    mgmt = deal_context.get("management", {})
    val = deal_context.get("valuation", {})

    metrics_block = (
        f"\n--- KEY METRICS ---\n"
        f"Forensic Score: {forensics.get('forensic_score', 'N/A')}/100\n"
        f"QoE: {forensics.get('quality_of_earnings', 'N/A')}\n"
        f"Adjusted EBITDA: Rs {forensics.get('adjusted_ebitda_cr', 'N/A')} Cr\n"
        f"Management Score: {mgmt.get('management_score', 'N/A')}/100\n"
        f"Governance Flags: {json.dumps(mgmt.get('governance_flags', []))}\n"
        f"PE Decision (Agent 5): {val.get('pe_decision', 'N/A')}\n"
        f"Do Not Exceed: Rs {val.get('do_not_exceed_price_cr', 'N/A')} Cr\n"
        f"Convergence: {val.get('convergence_quality', 'N/A')} "
        f"({val.get('convergence_spread_pct', 'N/A')}%)\n"
        f"--- END METRICS ---"
    )

    # Debate summary
    debate_summary = (
        f"\n--- DEBATE SUMMARY ---\n"
        f"Total Rounds: {debate_result.get('total_rounds', 'N/A')}\n"
        f"Champion Final Conviction: "
        f"{debate_result.get('champion_final_conviction', 'N/A')}/10\n"
        f"Risk Partner Final Conviction: "
        f"{debate_result.get('risk_partner_final_conviction', 'N/A')}/10\n"
        f"Consensus: {debate_result.get('consensus_type', 'N/A')}\n"
        f"--- END SUMMARY ---"
    )

    user_message = (
        f"You are chairing the Investment Committee for {company} ({sector}).\n\n"
        f"{metrics_block}\n\n"
        f"--- FULL DEBATE TRANSCRIPT ---\n{transcript_text}\n"
        f"--- END TRANSCRIPT ---\n\n"
        f"{debate_summary}\n"
        f"{past_text}\n\n"
        f"Please review everything and submit your IC decision using "
        f"the submit_ic_decision tool."
    )

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    messages = [{"role": "user", "content": user_message}]

    max_iter = 3
    for iteration in range(max_iter):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=IC_SYSTEM_PROMPT,
                tools=IC_TOOLS,
                messages=messages,
            )
        except Exception as e:
            logger.error(f"IC Agent API error: {e}")
            return _fallback_decision(company, str(e))

        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use" and block.name == "submit_ic_decision":
                    decision = block.input

                    # Consistency check (Fix requested)
                    decision = make_decision(
                        decision=decision,
                        debate=debate_result,
                        forensic=forensics,
                        financials=deal_context.get("financial_data", {}),
                        valuation=val
                    )

                    # Save to memory
                    _save_decision(
                        company_name=company,
                        sector=sector,
                        decision=decision,
                        forensic_score=forensics.get("forensic_score", 0),
                        management_score=mgmt.get("management_score", 0)
                    )

                    print(f"\n  IC DECISION: {decision.get('decision', 'N/A')}")
                    print(f"  Conviction: {decision.get('conviction_level', 'N/A')}")
                    print(f"  Debate Winner: {decision.get('debate_winner', 'N/A')}")
                    print(f"  Max Entry: Rs {decision.get('recommended_entry_price_cr', 'N/A')} Cr")

                    return decision

        elif response.stop_reason == "end_turn":
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": "Please submit your decision using the submit_ic_decision tool."
            })

    return _fallback_decision(company, "Max iterations reached")


def _fallback_decision(company: str, reason: str) -> Dict[str, Any]:
    """Safe fallback if IC Agent fails."""
    return {
        "decision": "REJECT",
        "conviction_level": "LOW",
        "executive_summary": f"IC Agent failed to produce decision. Reason: {reason}. "
                            f"Defaulting to REJECT for safety.",
        "key_thesis_points": ["Agent failure — manual review required"],
        "conditions": [],
        "deal_killers_identified": [f"System error: {reason}"],
        "recommended_entry_price_cr": 0,
        "debate_winner": "DRAW",
        "strongest_bull_argument": "N/A",
        "strongest_bear_argument": "N/A",
        "next_steps": ["Manual IC review required"]
    }
