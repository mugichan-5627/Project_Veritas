from project_veritas.agents.valuation_agent import run_valuation_agent
import json

def test_phase2():
    brief = {
        "company_name": "Mankind Pharma",
        "sector": "pharmaceuticals",
        "financials": {
            "revenue": 10000,
            "ebitda": 2500,
            "net_debt": 500
        },
        # Notice we omitted 'peers' so capiq_loader triggers automatically
        "dcf_params": {
            "revenue_growth_rates": [0.12, 0.12, 0.10, 0.10, 0.08],
            "ebitda_margin": 0.25,
            "wacc": 0.11,
            "terminal_growth_rate": 0.04
        },
        "lbo_params": {
            "entry_ebitda": 2500,
            "entry_ev_multiple": 15.0,
            "debt_pct_of_ev": 0.50
        }
    }

    print("Starting Phase 2 RAG Valuation Agent Test...")
    result = run_valuation_agent(brief)
    
    print("\n\n" + "="*50)
    print("FINAL VALUATION RESULT")
    print("="*50)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_phase2()
