"""
RUN AGENT — Phase 1 Runner

This is the script you actually type to use Project Veritas.
It sends a company brief to the valuation agent and prints
the structured output including football field and PE decision.

Usage:
  py -m project_veritas.agents.run_agent

To enable live Claude mode:
  set ANTHROPIC_API_KEY=sk-ant-...
  py -m project_veritas.agents.run_agent
"""

import json
from project_veritas.agents.valuation_agent import run_valuation_agent


# =====================================================================
# COMPANY BRIEF — Mankind Pharma (same case as Phase 0 test)
# =====================================================================
# Using the same inputs lets us directly compare Phase 0 results
# (RONIC = WACC, DCF = Rs 18,932 Cr) vs Phase 1 results
# (RONIC = sector ROE from Damodaran, DCF should increase).

company_brief = {
    "company_name": "Mankind Pharma Limited",
    "sector": "Pharmaceuticals",
    "financials": {
        "revenue": 9659,
        "ebitda": 2100,
        "net_debt": -850
    },
    "peers": [
        {"name": "Sun Pharma",  "ev_ebitda": 26.2, "ev_revenue": 5.8},
        {"name": "Dr. Reddys",  "ev_ebitda": 11.8, "ev_revenue": 3.1},
        {"name": "Cipla",       "ev_ebitda": 14.2, "ev_revenue": 3.9},
        {"name": "Aurobindo",   "ev_ebitda": 12.9, "ev_revenue": 2.4},
        {"name": "Zydus",       "ev_ebitda": 14.0, "ev_revenue": 3.2},
    ],
    "dcf_params": {
        "base_revenue": 9659,
        "revenue_growth_rates": [0.16, 0.15, 0.13, 0.12, 0.10],
        "ebitda_margin": 0.217,
        "da_margin": 0.03,
        "tax_rate": 0.25,
        "capex_margin": 0.03,
        "wc_change_margin": 0.02,
        "wacc": 0.115,
        "terminal_growth_rate": 0.055,
        "net_debt": -850,
    },
    "lbo_params": {
        "entry_ebitda": 1200,
        "entry_ev_multiple": 20.0,
        "debt_pct_of_ev": 0.35,
        "hold_years": 5,
        "ebitda_growth_rates": [0.16, 0.15, 0.13, 0.12, 0.10],
        "interest_rate": 0.09,
        "mandatory_amort_pct": 0.05,
        "cash_sweep_pct": 0.60,
    },
}

# =====================================================================
# RUN THE AGENT
# =====================================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)
    print("  PROJECT VERITAS — Valuation Agent")
    print("  Phase 1: Tool-Use Loop Architecture")
    print("=" * 70)

    result = run_valuation_agent(company_brief)

    # ---- Pretty-print the final output ----
    print("\n" + "=" * 70)
    print("  AGENT OUTPUT — Structured Valuation Result")
    print("=" * 70)

    print(f"\n  Company: {result.get('company_name', 'N/A')}")
    print(f"  Sector:  {result.get('sector', 'N/A')}")

    # Football field
    ff = result.get("football_field", {})
    if ff:
        print(f"\n  FOOTBALL FIELD:")
        print(f"  {'Method':<35} | {'Low':>12} | {'Mid':>12} | {'High':>12}")
        print(f"  {'-'*77}")
        for method, vals in ff.items():
            label = vals.get("method", method)[:35]
            print(f"  {label:<35} | {vals['low']:>10,.0f}Cr | "
                  f"{vals['mid']:>10,.0f}Cr | {vals['high']:>10,.0f}Cr")

    # Convergence
    quality = result.get("convergence_quality", "N/A")
    spread = result.get("convergence_spread_pct", 0)
    print(f"\n  CONVERGENCE: {quality} ({spread:.0f}% spread)")

    # PE Decision
    print(f"  PE DECISION: {result.get('pe_decision', 'N/A')}")
    print(f"\n  RECOMMENDATION:")
    print(f"  {result.get('primary_recommendation', 'N/A')}")

    # Risks
    risks = result.get("key_risks", [])
    if risks:
        print(f"\n  KEY RISKS:")
        for r in risks:
            print(f"    - {r}")

    # Data gaps
    gaps = result.get("data_gaps", [])
    if gaps:
        print(f"\n  DATA GAPS:")
        for g in gaps:
            print(f"    - {g}")

    # Methods & Sources
    print(f"\n  METHODS: {', '.join(result.get('methods_used', []))}")
    print(f"  SOURCES:")
    for s in result.get("sources_cited", []):
        print(f"    - {s}")

    # ---- Phase 0 vs Phase 1 comparison ----
    print("\n" + "=" * 70)
    print("  PHASE 0 vs PHASE 1 COMPARISON")
    print("=" * 70)

    dcf_mid = ff.get("dcf", {}).get("mid", 0)
    print(f"\n  DCF Enterprise Value:")
    print(f"    Phase 0 (RONIC = WACC 11.5%):      Rs 18,932 Cr")
    print(f"    Phase 1 (RONIC = Damodaran ROE):    Rs {dcf_mid:,.0f} Cr")
    if dcf_mid > 0:
        delta = (dcf_mid - 18932) / 18932 * 100
        print(f"    Delta: {'+' if delta > 0 else ''}{delta:.1f}%"
              f"  {'(RONIC lookup working!)' if delta > 5 else ''}")

    print(f"\n  Convergence Spread:")
    print(f"    Phase 0: 56% (MODERATE)")
    print(f"    Phase 1: {spread:.0f}% ({quality})")

    print("\n" + "=" * 70)
