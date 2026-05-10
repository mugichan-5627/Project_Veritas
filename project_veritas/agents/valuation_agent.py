"""
VALUATION AGENT — Phase 1 Core

This is the "brain" that sits on top of the three Phase 0 tools.
It receives a company brief, decides which tools to call, calls
them with the right inputs, and returns a structured valuation.

Architecture:
  - Claude API (claude-opus-4-5) with 4 tools registered
  - Claude decides tool order based on system prompt persona
  - Agent loops until finalize_valuation() is called
  - Max 8 iterations (prevents runaway loops)
  - RONIC lookup from Damodaran roeIndia.xls before DCF runs
  - Web search fallback via Tavily (last resort, verified sources only)

Requires:
  - ANTHROPIC_API_KEY environment variable
  - TAVILY_API_KEY environment variable (optional, enables web fallback)
"""

import os
import sys
import json
import pandas as pd
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Add project root to path so we can import Phase 0 tools
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, PROJECT_ROOT)

from tools.comparable_company import run_comparable_analysis
from tools.dcf_engine import calculate_dcf
from tools.dcf_engine import _fetch_sector_data_web as dcf_web_search
from tools.lbo_engine import run_lbo_analysis
from tools.lbo_engine import _fetch_sector_data_web as lbo_web_search


# =====================================================================
# SYSTEM PROMPT — The analyst's training and mandate
# =====================================================================
# Without this, Claude is a generalist. With this, Claude becomes a
# PE analyst who knows to triangulate, cite sources, and never guess.

SYSTEM_PROMPT = """You are a Senior Investment Analyst at a top-tier Indian PE fund \
with 15 years of experience. You have deep expertise in:
- Comparable company analysis (Rosenbaum & Pearl methodology)
- DCF valuation (McKinsey Value Driver Framework + Damodaran)
- LBO return analysis (Reinard/Zeisberger PE benchmarks)

Your job is to produce institutional-grade valuation analysis.

RULES YOU NEVER BREAK:
1. Always run at least 2 of 3 valuation methods before concluding
2. Always cite the source and methodology for every number
3. If data is missing, flag it explicitly — never estimate silently
4. Always triangulate: compare methods and explain divergences
5. RONIC: look up sector ROE from Damodaran data if available, \
never default to WACC without flagging it
6. Your output will be reviewed by a CFO — precision matters
7. Before running any valuation tool, call query_knowledge_base to retrieve methodology context. This grounds every calculation in institutional source material. Your citations must reference actual retrieved passages, not your training data.

SECTOR RONIC LOOKUP PROTOCOL:
When running DCF, before defaulting RONIC to WACC:
1. Check if sector_name parameter is provided
2. If yes, load data/damodaran/roeIndia.xls and find sector ROE
3. Use sector ROE as RONIC — this closes the DCF/comps gap
4. If sector not found in file, then default to WACC and flag

DATA PRIORITY ORDER (never violate):
1. User-provided inputs
2. Local Damodaran Excel files (data/damodaran/)
3. CapIQ exports (data/capiq/)
4. yfinance — Indian market data (.NS/.BO tickers)
5. Tavily web search (verified domains only)
6. NEVER hallucinate"""


# =====================================================================
# TOOL DEFINITIONS — What Claude sees as available instruments
# =====================================================================
# These are JSON schemas that tell Claude what each tool does and
# what parameters it expects. Claude reads these and decides which
# tool to call based on the company brief and system prompt.

TOOLS = [
    {
        "name": "query_knowledge_base",
        "description": (
            "Retrieves relevant methodology passages from the institutional PDF library "
            "(Rosenbaum, Damodaran, McKinsey, ICRA). Call this BEFORE running any "
            "valuation tool to retrieve the methodology context. Returns verbatim "
            "passages with source and page citations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "methodology_type": {
                    "type": "string",
                    "description": "comparable_company / dcf_terminal_value / lbo_returns / wacc_calculation / sector_specific / credit_analysis / india_market_context"
                },
                "sector": {
                    "type": "string",
                    "description": "Sector name (optional)"
                },
                "include_current_deal": {
                    "type": "boolean",
                    "description": "Set to true to query the current target's specific documents"
                }
            },
            "required": ["methodology_type"]
        }
    },
    {
        "name": "run_comparable_analysis",
        "description": (
            "Runs comparable company analysis using Rosenbaum & Pearl "
            "percentile methodology. Returns implied EV range at "
            "P25/median/P75 using EV/EBITDA and EV/Revenue multiples "
            "from the peer set."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_ebitda": {
                    "type": "number",
                    "description": "Target company EBITDA in Rs Crores"
                },
                "target_revenue": {
                    "type": "number",
                    "description": "Target company Revenue in Rs Crores"
                },
                "target_net_debt": {
                    "type": "number",
                    "description": "Net debt in Rs Crores (negative = net cash)"
                },
                "peers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "ev_ebitda": {"type": "number"},
                            "ev_revenue": {"type": "number"}
                        },
                        "required": ["name", "ev_ebitda", "ev_revenue"]
                    },
                    "description": "Array of peer companies with multiples"
                },
                "sector_name": {
                    "type": "string",
                    "description": "Sector name for confidence context"
                }
            },
            "required": ["target_ebitda", "target_revenue",
                         "target_net_debt", "peers"]
        }
    },
    {
        "name": "run_dcf_analysis",
        "description": (
            "Runs DCF valuation using McKinsey Value Driver Formula for "
            "terminal value with Gordon Growth cross-check. Returns 5-year "
            "FCF projection, sensitivity table, and implied EV. Attempts "
            "sector ROE lookup from Damodaran data for RONIC before "
            "defaulting to WACC."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "base_revenue": {"type": "number"},
                "revenue_growth_rates": {
                    "type": "array", "items": {"type": "number"}
                },
                "ebitda_margin": {"type": "number"},
                "da_margin": {"type": "number"},
                "tax_rate": {"type": "number"},
                "capex_margin": {"type": "number"},
                "wc_change_margin": {"type": "number"},
                "wacc": {"type": "number"},
                "terminal_growth_rate": {"type": "number"},
                "net_debt": {"type": "number"},
                "sector_name": {
                    "type": "string",
                    "description": "Sector name — triggers Damodaran ROE lookup for RONIC"
                }
            },
            "required": ["base_revenue", "revenue_growth_rates",
                         "wacc", "terminal_growth_rate", "net_debt"]
        }
    },
    {
        "name": "run_lbo_analysis",
        "description": (
            "Runs LBO return analysis with debt schedule and value "
            "creation bridge. Returns MOIC/IRR across bear/base/bull "
            "scenarios with PE screen flags per Zeisberger benchmarks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_ebitda": {"type": "number"},
                "entry_ev_multiple": {"type": "number"},
                "debt_pct_of_ev": {"type": "number"},
                "hold_years": {"type": "integer"},
                "ebitda_growth_rates": {
                    "type": "array", "items": {"type": "number"}
                },
                "interest_rate": {"type": "number"},
                "mandatory_amort_pct": {"type": "number"},
                "cash_sweep_pct": {"type": "number"}
            },
            "required": ["entry_ebitda", "entry_ev_multiple",
                         "debt_pct_of_ev", "hold_years",
                         "ebitda_growth_rates", "interest_rate",
                         "mandatory_amort_pct", "cash_sweep_pct"]
        }
    },
    {
        "name": "finalize_valuation",
        "description": (
            "Call this ONLY when you have run at least 2 of the 3 "
            "valuation methods and are ready to synthesize findings. "
            "This ends the agent loop."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "sector": {"type": "string"},
                "football_field": {
                    "type": "object",
                    "description": "Object with low/mid/high for each method used"
                },
                "convergence_quality": {
                    "type": "string",
                    "enum": ["EXCELLENT", "GOOD", "MODERATE", "POOR"]
                },
                "convergence_spread_pct": {"type": "number"},
                "pe_decision": {
                    "type": "string",
                    "enum": ["PROCEED", "PROCEED WITH CAUTION", "PASS"]
                },
                "primary_recommendation": {"type": "string"},
                "do_not_exceed_price_cr": {
                    "type": "number",
                    "description": "The absolute maximum EV in Rs Crores you would pay before the deal destroys value. Factoring in QoE and Governance risks."
                },
                "key_risks": {
                    "type": "array", "items": {"type": "string"}
                },
                "data_gaps": {
                    "type": "array", "items": {"type": "string"}
                },
                "methods_used": {
                    "type": "array", "items": {"type": "string"}
                },
                "sources_cited": {
                    "type": "array", "items": {"type": "string"}
                }
            },
            "required": ["company_name", "sector", "football_field",
                         "convergence_quality", "convergence_spread_pct",
                         "pe_decision", "primary_recommendation", "do_not_exceed_price_cr",
                         "key_risks", "data_gaps", "methods_used",
                         "sources_cited"]
        }
    }
]


# =====================================================================
# RONIC LOOKUP — The Phase 0 → Phase 1 upgrade
# =====================================================================
# In Phase 0, DCF defaulted RONIC to WACC (conservative). This crushed
# terminal value and created the 56% spread vs comps/LBO.
# Now we read the actual sector ROE from Damodaran's roeIndia.xls.
# For Pharmaceuticals, this gives ~15.6% vs WACC of 11.5% — the DCF
# terminal value rises, closing the gap to ~25-30% spread.

def _get_sector_ronic(sector_name: str) -> float | None:
    """
    Read data/damodaran/roeIndia.xls and find sector ROE.

    Uses fuzzy matching because user might say "Pharmaceuticals"
    but Damodaran labels the row "Drugs (Pharmaceutical)".

    Returns ROE as decimal (e.g. 0.156 for 15.6%) or None.
    """
    roe_path = os.path.join(
        PROJECT_ROOT, "..", "data", "damodaran", "roeIndia.xls"
    )

    if not os.path.exists(roe_path):
        print(f"  RONIC LOOKUP: File not found at {roe_path}")
        print(f"  RONIC LOOKUP: Defaulting RONIC to WACC (conservative)")
        return None

    try:
        # Read the Industry Averages sheet
        # Header row is row 7 (0-indexed), data starts row 8
        df = pd.read_excel(roe_path, sheet_name="Industry Averages",
                           header=None)

        # Column 0 = Industry Name, Column 2 = ROE (unadjusted)
        best_match = None
        best_score = 0.0
        best_roe = None

        search_term = sector_name.lower().strip()

        for i in range(8, len(df)):
            label = str(df.iloc[i, 0]).strip()
            if label == "nan" or label == "":
                continue

            label_lower = label.lower()

            # Method 1: Direct substring match (highest priority)
            if search_term in label_lower or label_lower in search_term:
                score = 0.95
            else:
                # Method 2: Check if any word matches
                search_words = search_term.split()
                label_words = label_lower.replace("(", " ").replace(")", " ").split()

                word_match = any(
                    sw in label_words or any(sw in lw for lw in label_words)
                    for sw in search_words
                )
                if word_match:
                    score = 0.80
                else:
                    # Method 3: SequenceMatcher fuzzy score
                    score = SequenceMatcher(
                        None, search_term, label_lower
                    ).ratio()

            if score > best_score:
                best_score = score
                best_match = label
                try:
                    best_roe = float(df.iloc[i, 2])
                except (ValueError, TypeError):
                    best_roe = None

        # Threshold: only accept matches above 60% similarity
        if best_score >= 0.60 and best_roe is not None:
            print(f"  RONIC LOOKUP: Sector '{sector_name}' -> "
                  f"matched '{best_match}' -> ROE = {best_roe:.1%}")
            return best_roe
        else:
            print(f"  RONIC LOOKUP: No match for '{sector_name}' "
                  f"(best: '{best_match}' at {best_score:.0%}) -> "
                  f"defaulting RONIC to WACC (conservative)")
            return None

    except Exception as e:
        print(f"  RONIC LOOKUP ERROR: {e}")
        print(f"  RONIC LOOKUP: Defaulting RONIC to WACC (conservative)")
        return None


# =====================================================================
# TOOL EXECUTOR — Routes Claude's tool calls to Phase 0 functions
# =====================================================================

def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Takes a tool name + input dict from Claude's response,
    calls the matching Phase 0 function, returns JSON string.

    For DCF: injects RONIC from Damodaran before calling.
    For finalize: returns the input as-is (it IS the output).

    Web fallback: after every tool call, if result contains any
    key with value None AND sector_name is available, attempts
    Tavily web search as last resort.
    """
    sector_name = tool_input.get("sector_name", "")

    if tool_name == "query_knowledge_base":
        from project_veritas.memory.memory_agent import get_methodology_context
        result = get_methodology_context(
            methodology_type=tool_input["methodology_type"],
            sector=tool_input.get("sector"),
            include_current_deal=tool_input.get("include_current_deal", False)
        )
        return json.dumps({"context": result})

    elif tool_name == "run_comparable_analysis":
        # Remove sector_name before passing — our tool doesn't take it
        clean_input = {k: v for k, v in tool_input.items()
                       if k != "sector_name"}
        result = run_comparable_analysis(**clean_input)
        
        # Determine source
        source = "CapIQ peers file ✓"
        result, final_source = _apply_web_fallback(result, sector_name, source)
        print(f"DATA SOURCE: {final_source}")
        return json.dumps(result, indent=2, default=str)

    elif tool_name == "run_dcf_analysis":
        # RONIC LOOKUP — the Phase 1 upgrade
        sector = tool_input.pop("sector_name", None)
        source = "Default assumption ⚠ (flag for review)"
        if sector:
            ronic = _get_sector_ronic(sector)
            if ronic is not None:
                tool_input["ronic"] = ronic
                source = "Damodaran roeIndia.xls ✓"
            else:
                source = "Default assumption ⚠ (flag for review)"

        result = calculate_dcf(**tool_input)
        result, final_source = _apply_web_fallback(result, sector or sector_name, source)
        print(f"DATA SOURCE: {final_source}")
        return json.dumps(result, indent=2, default=str)

    elif tool_name == "run_lbo_analysis":
        result = run_lbo_analysis(**tool_input)
        source = "User-provided LBO parameters ✓"
        result, final_source = _apply_web_fallback(result, sector_name, source)
        print(f"DATA SOURCE: {final_source}")
        return json.dumps(result, indent=2, default=str)

    elif tool_name == "finalize_valuation":
        return json.dumps(tool_input, indent=2, default=str)

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


def _apply_web_fallback(result: dict, sector_name: str, current_source: str) -> tuple[dict, str]:
    """
    After every tool call, check if any top-level key has value None.
    If so AND sector_name is available, attempt web search fallback.
    Returns (updated_result, actual_source_used).
    """
    if not sector_name:
        return result, current_source

    # Check if any top-level value is None
    has_none = any(v is None for v in result.values())
    if not has_none:
        return result, current_source

    # Attempt web search as last resort
    web_result = dcf_web_search(
        sector=sector_name,
        metric="EBITDA margin WACC beta"
    )

    if web_result is not None:
        result["web_sources_consulted"] = web_result[:200]  # preview only
        result["web_fallback_used"] = True
        return result, "Web fallback ✓ (verify before IC)"
    else:
        # If web search fails, we stick with current_source (e.g. Default)
        return result, current_source





# =====================================================================
# LIVE CLAUDE MODE — Uses Anthropic API with tool-use loop
# =====================================================================

def _run_live_agent(deal_context: dict, client) -> dict:
    """Run the agent using Claude API with tool-use loop."""

    print("=" * 60)
    print("  RUNNING IN LIVE CLAUDE MODE (VALUATION AGENT)")
    print("=" * 60)

    # Safely extract values from the full deal context
    company_name = deal_context.get("company_name", "Unknown Target")
    sector = deal_context.get("sector", "Unknown Sector")
    
    raw_fin = deal_context.get("raw_financials", {})
    revenue = raw_fin.get("revenue", 0)
    reported_ebitda = raw_fin.get("ebitda", 0)
    net_debt = raw_fin.get("net_debt", 0)
    
    # CRITICAL: Use Adjusted EBITDA from Forensics Agent if available!
    forensics = deal_context.get("forensics", {})
    adjusted_ebitda = deal_context.get("adjusted_ebitda") or reported_ebitda
    qoe_notes = forensics.get("quality_of_earnings", "No QoE findings available.")
    
    market_intel = deal_context.get("market_intel", {})
    implied_multiple = market_intel.get("implied_entry_multiple_range", "Unknown")
    
    management = deal_context.get("management", {})
    gov_flags = management.get("governance_flags", [])

    # Build the initial user message from the complete deal context
    user_message = (
        f"Analyze {company_name} for potential PE investment valuation.\n\n"
        f"Sector: {sector}\n\n"
        f"**1. Core Financials**\n"
        f"  Revenue: Rs {revenue:,} Cr\n"
        f"  Reported EBITDA: Rs {reported_ebitda:,} Cr\n"
        f"  Net Debt: Rs {net_debt:,} Cr"
        f"{' (net cash position)' if net_debt < 0 else ''}\n\n"
        f"**2. Quality of Earnings (From Financial Forensics Agent)**\n"
        f"  ADJUSTED EBITDA: Rs {adjusted_ebitda:,} Cr  <-- MUST USE THIS FOR ALL VALUATION MATH\n"
        f"  Forensics Notes: {qoe_notes}\n\n"
        f"**3. Market Intelligence (From Market Intel Agent)**\n"
        f"  Implied Entry Multiple: {implied_multiple}\n\n"
        f"**4. Governance & Management (From Management Agent)**\n"
        f"  Governance Flags: {gov_flags if gov_flags else 'None detected.'}\n\n"
    )

    if deal_context.get("peers"):
        user_message += "**5. Comparable Peers Provided**\n"
        for p in deal_context["peers"]:
            user_message += (
                f"  - {p.get('name', 'Unknown')}: EV/EBITDA={p.get('ev_ebitda', 'N/A')}x, "
                f"EV/Rev={p.get('ev_revenue', 'N/A')}x\n"
            )

    user_message += (
        "\n\n**INSTRUCTIONS:**\n"
        "1. Run all three valuation methods (comps, DCF, LBO).\n"
        "2. MUST use the Adjusted EBITDA for your calculations, NOT the reported EBITDA.\n"
        "3. Incorporate the Governance Flags into your risk assessment. If severe, apply a higher WACC or penalize the 'Do Not Exceed' price.\n"
        "4. Call `finalize_valuation` to synthesize your findings, ensuring you provide a strict 'do_not_exceed_price_cr'."
    )

    messages = [{"role": "user", "content": user_message}]

    max_iterations = 8
    for iteration in range(1, max_iterations + 1):
        print(f"\n  [Iteration {iteration}] Claude is thinking...")

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Check if Claude wants to use tools
        if response.stop_reason == "tool_use":
            # Process each tool call in the response
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    print(f"  [Iteration {iteration}] "
                          f"Tool called: {tool_name}")

                    result_str = _execute_tool(tool_name, tool_input)

                    print(f"  [Iteration {iteration}] Tool complete. "
                          f"Result length: {len(result_str)} chars")

                    # If finalize was called, we're done
                    if tool_name == "finalize_valuation":
                        print(f"  [Iteration {iteration}] "
                              f"Agent finalized. Loop complete.")
                        return json.loads(result_str)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            # Feed results back to Claude for next iteration
            messages.append({"role": "assistant",
                             "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            # Claude finished without calling finalize — extract text
            print(f"  [Iteration {iteration}] "
                  f"Claude ended without finalize_valuation.")
            text = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            return {"error": "Agent ended without finalize", "text": text}

    return {"error": f"Agent exceeded {max_iterations} iterations"}



# =====================================================================
# MAIN ENTRY POINT
# =====================================================================

def run_valuation_agent(deal_context: dict) -> dict:
    """
    Main entry point for the valuation agent.

    deal_context contains all outputs from previous agents (Forensics, Market, Management).
    Returns a structured dict with football field, convergence,
    PE decision, 'do_not_exceed' price, and full audit trail.

    Requires ANTHROPIC_API_KEY environment variable.
    """
    
    # Check for peers in deal_context, auto-load if missing
    if "peers" not in deal_context or not deal_context["peers"]:
        from project_veritas.memory.capiq_loader import load_peers_from_capiq
        
        sector = deal_context.get("sector", "unknown")
        raw_fin = deal_context.get("raw_financials", {})
        rev = raw_fin.get("revenue", 0)
        
        peers = load_peers_from_capiq(sector=sector, target_revenue_usd_m=rev)
        deal_context["peers"] = peers
        
        print(f"AUTO-LOADED PEERS: {len(peers)} companies")

    import os
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        # We will allow mocking for the UI tests if key is missing, 
        # but warn the user.
        print("WARNING: ANTHROPIC_API_KEY not set. Returning mocked valuation.")
        return {
            "company_name": deal_context.get("company_name", "Unknown"),
            "sector": deal_context.get("sector", "Unknown"),
            "football_field": {
                "Comps": {"low": 1000, "mid": 1200, "high": 1400},
                "DCF": {"low": 900, "mid": 1100, "high": 1300},
                "LBO": {"low": 850, "mid": 1000, "high": 1150}
            },
            "convergence_quality": "MODERATE",
            "convergence_spread_pct": 18.5,
            "do_not_exceed_price_cr": 1100,
            "pe_decision": "PROCEED WITH CAUTION",
            "primary_recommendation": "MOCKED: Valuation engine bypassed due to missing API key.",
            "key_risks": ["Mocked response", "No real API call made"],
            "data_gaps": [],
            "methods_used": ["Mocked Comps", "Mocked DCF", "Mocked LBO"],
            "sources_cited": ["Mock Data"]
        }

    client = anthropic.Anthropic()
    return _run_live_agent(deal_context, client)
