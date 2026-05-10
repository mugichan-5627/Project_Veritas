import os
import sys
from tavily import TavilyClient

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from project_veritas.tools.dcf_engine import _fetch_sector_data_web

def safe_print(text):
    """Safely print text by stripping non-ASCII characters for Windows terminal compatibility."""
    try:
        print(text.encode('ascii', 'ignore').decode('ascii'))
    except:
        pass

def run_test():
    summary = {
        "client_init": "FAIL",
        "company_results": 0,
        "sector_results": 0,
        "fallback_working": "None",
        "found_domains": set(),
        "no_results_domains": set()
    }
    
    all_targeted_domains = [
        "bseindia.com",
        "nseindia.com", 
        "screener.in",
        "moneycontrol.com",
        "stern.nyu.edu",
        "sebi.gov.in"
    ]

    safe_print("\n" + "="*70)
    safe_print("  PROJECT VERITAS - Tavily Search Layer Test")
    safe_print("="*70)

    # PART 1 - Basic connectivity check
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        safe_print("ERROR: TAVILY_API_KEY not found in environment!")
        return

    try:
        client = TavilyClient(api_key=tavily_key)
        safe_print("Tavily client initialized [OK]")
        summary["client_init"] = "PASS"
    except Exception as e:
        safe_print(f"Tavily client init failed: {e}")
        return

    # PART 2 - Search for Mankind Pharma financials
    safe_print("\nPART 2 - Searching for Mankind Pharma financials...")
    try:
        response = client.search(
            query="Mankind Pharma revenue EBITDA FY2024 annual report BSE filing financial results",
            search_depth="advanced",
            max_results=5,
            include_answer=True,
            include_domains=all_targeted_domains
        )
        
        results = response.get("results", [])
        summary["company_results"] = len(results)
        
        for i, r in enumerate(results, 1):
            safe_print("-" * 40)
            safe_print(f"SOURCE [{i}]: {r['url']}")
            safe_print(f"TITLE: {r['title']}")
            safe_print(f"CONTENT PREVIEW: {r['content'][:500]}...")
            
            if '/' in r['url']:
                parts = r['url'].split('/')
                if len(parts) > 2:
                    domain = parts[2]
                    summary["found_domains"].add(domain)

        if response.get("answer"):
            safe_print(f"\nTAVILY DIRECT ANSWER: {response['answer']}")
            
    except Exception as e:
        safe_print(f"Part 2 failed: {e}")

    # PART 3 - Search for India Pharma sector WACC/multiples
    safe_print("\nPART 3 - Searching for India Pharma sector WACC/multiples...")
    try:
        target_domains_p3 = ["stern.nyu.edu", "screener.in", "moneycontrol.com", "bseindia.com"]
        response2 = client.search(
            query="India pharmaceutical sector WACC EV EBITDA multiple Damodaran 2024 valuation",
            search_depth="advanced",
            max_results=5,
            include_answer=True,
            include_domains=target_domains_p3
        )
        
        results2 = response2.get("results", [])
        summary["sector_results"] = len(results2)
        
        for i, r in enumerate(results2, 1):
            safe_print("-" * 40)
            safe_print(f"SOURCE [{i}]: {r['url']}")
            safe_print(f"TITLE: {r['title']}")
            safe_print(f"CONTENT PREVIEW: {r['content'][:500]}...")
            
            if '/' in r['url']:
                parts = r['url'].split('/')
                if len(parts) > 2:
                    domain = parts[2]
                    summary["found_domains"].add(domain)

        if response2.get("answer"):
            safe_print(f"\nTAVILY DIRECT ANSWER: {response2['answer']}")
            
    except Exception as e:
        safe_print(f"Part 3 failed: {e}")

    # PART 4 - Test the actual _fetch_sector_data_web function
    safe_print("\nPART 4 - Testing _fetch_sector_data_web function...")
    try:
        result = _fetch_sector_data_web(
            sector="Pharmaceuticals",
            metric="EBITDA margin WACC beta India"
        )
        
        if result:
            safe_print("WEB FALLBACK FUNCTION: WORKING [OK]")
            safe_print(f"Content length: {len(result)} chars")
            safe_print(f"Preview: {result[:300]}...")
            summary["fallback_working"] = "WORKING"
        else:
            safe_print("WEB FALLBACK FUNCTION: returned None")
            summary["fallback_working"] = "None"
            
    except Exception as e:
        safe_print(f"Part 4 failed: {e}")

    # FINAL SUMMARY
    summary["no_results_domains"] = []
    for d in all_targeted_domains:
        found = False
        for fd in summary["found_domains"]:
            if d in fd:
                found = True
                break
        if not found:
            summary["no_results_domains"].append(d)
    
    status = "READY" if summary["client_init"] == "PASS" and summary["fallback_working"] == "WORKING" else "NEEDS ATTENTION"
    
    safe_print("\n" + "="*70)
    safe_print("  TAVILY TEST SUMMARY - Mankind Pharma")
    safe_print(f"  Part 1 - Client init:     [{summary['client_init']}]")
    safe_print(f"  Part 2 - Company search:  [{summary['company_results']} results found]")
    safe_print(f"  Part 3 - Sector search:   [{summary['sector_results']} results found]")
    safe_print(f"  Part 4 - Fallback fn:     [{summary['fallback_working']}]")
    safe_print(f"\n  Domains that returned results: {sorted(list(summary['found_domains']))}")
    safe_print(f"  Domains with no results:       {sorted(summary['no_results_domains'])}")
    safe_print(f"\n  Web search layer status: {status}")
    safe_print("="*70 + "\n")

if __name__ == "__main__":
    run_test()
