import os
import sys
import json
from unittest.mock import MagicMock, patch

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from project_veritas.agents.orchestrator import DueDiligenceOrchestrator

# --- Mock Data ---
class MockBlock:
    def __init__(self, type_str, name=None, input_data=None, id_str=None):
        self.type = type_str
        self.name = name
        self.input = input_data
        self.id = id_str

class MockResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content

# Keep track of iteration counts per agent to simulate tool calls then finalize
call_counts = {"biz": 0, "forensics": 0, "market": 0}

def mock_messages_create(*args, **kwargs):
    system_prompt = kwargs.get("system", "")
    
    if "business analyst" in system_prompt:
        call_counts["biz"] += 1
        if call_counts["biz"] == 1:
            return MockResponse("tool_use", [MockBlock("tool_use", "search_web", {"query": "Mankind Pharma business model"}, "call_1")])
        elif call_counts["biz"] == 2:
            return MockResponse("tool_use", [MockBlock("tool_use", "search_web", {"query": "Mankind Pharma promoter background"}, "call_2")])
        else:
            return MockResponse("tool_use", [MockBlock("tool_use", "finalize_biz_intel", {
                "company_name": "Mankind Pharma", "ticker": "MANKIND.NS", "sector": "Healthcare",
                "subsector": "Pharma", "founded": "1995", "headquarters": "New Delhi",
                "business_model": "Develops, manufactures, and markets pharmaceutical formulations.",
                "revenue_segments": [{"segment": "Pharma", "pct_revenue": "100%"}],
                "geographic_presence": "India", "key_products_services": ["Manforce", "Prega News"],
                "promoter_background": "Ramesh Juneja", "promoter_holding_pct": "74%",
                "key_executives": [{"name": "Ramesh Juneja", "role": "Chairman"}],
                "market_cap_cr": 80000, "employee_count": "14000", "listing_status": "Listed",
                "pe_investment_history": "ChrysCapital", "recent_developments": ["Acquired BSV"],
                "analyst_consensus": "Buy", "data_confidence": "HIGH", "data_gaps": []
            }, "call_3")])
            
    elif "forensic accounting" in system_prompt:
        call_counts["forensics"] += 1
        if call_counts["forensics"] == 1:
            return MockResponse("tool_use", [MockBlock("tool_use", "search_filings", {"company": "Mankind Pharma"}, "call_1")])
        elif call_counts["forensics"] == 2:
            return MockResponse("tool_use", [MockBlock("tool_use", "fetch_financial_statements", {"company": "Mankind Pharma", "ticker": "MANKIND.NS"}, "call_2")])
        elif call_counts["forensics"] == 3:
            return MockResponse("tool_use", [MockBlock("tool_use", "query_forensic_knowledge", {"sector": "healthcare"}, "call_3")])
        else:
            return MockResponse("tool_use", [MockBlock("tool_use", "finalize_forensics", {
                "forensic_score": 85, "red_flags": [],
                "reported_ebitda_cr": 2000, "adjusted_ebitda_cr": 1950,
                "ebitda_adjustments": [{"adjustment": "One-time legal cost", "amount_cr": -50, "rationale": "Non-recurring"}],
                "debt_capacity_assessment": "Strong", "quality_of_earnings": "High", "data_gaps": []
            }, "call_4")])
            
    elif "market intelligence" in system_prompt:
        call_counts["market"] += 1
        if call_counts["market"] == 1:
            return MockResponse("tool_use", [MockBlock("tool_use", "search_market_research", {"query": "India pharma market size"}, "call_1")])
        elif call_counts["market"] == 2:
            return MockResponse("tool_use", [MockBlock("tool_use", "get_public_comp_multiples", {"sector": "healthcare"}, "call_2")])
        elif call_counts["market"] == 3:
            return MockResponse("tool_use", [MockBlock("tool_use", "get_transaction_multiples", {"sector": "healthcare"}, "call_3")])
        else:
            return MockResponse("tool_use", [MockBlock("tool_use", "finalize_market_intel", {
                "sector": "Healthcare", "sector_tam_cr": 300000, "sector_growth_rate": "10%",
                "competitive_position": "Leader", "key_competitors": ["Sun Pharma", "Cipla"],
                "recent_sector_ma": ["Torrent acquired Curatio"], "sector_pe_activity": "High",
                "sector_tailwinds": ["Rising incomes"], "sector_headwinds": ["Price caps"],
                "implied_entry_multiple_range": "20x - 25x", "data_gaps": []
            }, "call_4")])
            
    elif "governance and stewardship" in system_prompt:
        call_counts["management"] = call_counts.get("management", 0) + 1
        if call_counts["management"] == 1:
            return MockResponse("tool_use", [MockBlock("tool_use", "search_web", {"query": "Mankind Pharma governance issues"}, "call_1")])
        elif call_counts["management"] == 2:
            return MockResponse("tool_use", [MockBlock("tool_use", "fetch_analyst_sentiment", {"company": "Mankind Pharma"}, "call_2")])
        else:
            return MockResponse("tool_use", [MockBlock("tool_use", "finalize_management", {
                "management_score": 85,
                "promoter_background": "Strong execution track record",
                "key_executives": ["Ramesh Juneja", "Rajeev Juneja"],
                "board_independence": "ADEQUATE",
                "governance_flags": [],
                "analyst_sentiment": "POSITIVE",
                "succession_risk": "LOW",
                "capital_allocation_track_record": "Disciplined",
                "diligence_questions": ["What is the long term R&D strategy?"],
                "data_gaps": []
            }, "call_3")])
            
    return MockResponse("end_turn", [MockBlock("text", "Unknown agent")])

def run_test():
    print("Starting Mocked E2E Test (Agents 1-3)...")
    
    # Ensure TAVILY_API_KEY is available or mock it if it's missing just so the tool runs without crash
    if not os.environ.get("TAVILY_API_KEY"):
        os.environ["TAVILY_API_KEY"] = "tvly-mock-key-for-test"
        
    orchestrator = DueDiligenceOrchestrator(anthropic_api_key="mocked")
    
    with patch('anthropic.Anthropic') as MockAnthropic:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = mock_messages_create
        MockAnthropic.return_value = mock_client
        
        # Patch Tavily to avoid failing if it's a fake key
        with patch('tavily.TavilyClient.search') as mock_tavily:
            mock_tavily.return_value = {"results": [{"title": "Mock", "content": "Mock data", "url": "http://mock"}]}
            
            # The tools might try to hit ChromaDB or other APIs. If ChromaDB throws error, we'll patch that next.
            try:
                result = orchestrator.run_full_dd(company_name="Mankind Pharma", ticker="MANKIND.NS", sector="Healthcare")
                print("\n=== TEST SUCCESS ===")
                print("\n--- FULL DEAL CONTEXT DUMP ---")
                import pprint
                pprint.pprint(result)
            except Exception as e:
                print(f"\n=== TEST FAILED ===")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    run_test()
