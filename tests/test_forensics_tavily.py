import sys
sys.path.insert(
    0, r'C:\Users\Moosa\Downloads\Project_Veritas'
)
import json
import os

# Set keys from environment
tavily_key = os.environ.get("TAVILY_API_KEY")
if not tavily_key:
    print("ERROR: TAVILY_API_KEY not set")
    exit(1)

print("=" * 55)
print(" FORENSICS TAVILY ISOLATION TEST")
print(" Company: Mankind Pharma (MANKIND.NS)")
print("=" * 55)

# Test 1 — Financial statements via yfinance
print("\n[TEST 1] Financial Statements (yfinance)...")
from project_veritas.agents.financial_forensics_agent import fetch_financial_statements

statements = fetch_financial_statements(
    "Mankind Pharma", "MANKIND.NS"
)
print(f"  Source: {statements.get('source')}")
if statements.get("statements"):
    for k, v in statements["statements"].items():
        print(f"  {k}: {v}")
elif statements.get("raw_content"):
    print(f"  Web answer: "
          f"{statements['raw_content'][:300]}")

# Test 2 — Filing search
print("\n[TEST 2] Regulatory Filing Search...")
from project_veritas.agents.financial_forensics_agent import search_filings

filings = search_filings("Mankind Pharma")
print(f"  Searches completed: "
      f"{len(filings.get('results', []))}")
for i, r in enumerate(
        filings.get("results", [])[:2]):
    print(f"  [{i+1}] Query: {r.get('query','')[:50]}")
    if r.get("answer"):
        print(f"       Answer: {r['answer'][:200]}")

# Test 3 — Pure Python forensic tests
print("\n[TEST 3] Forensic Math Tests (no API)...")
from project_veritas.agents.financial_forensics_agent import run_forensic_tests

test_results = run_forensic_tests(
    raw_financials={
        "revenue": 9659,
        "ebitda": 2100,
        "net_debt": -850
    },
    statements=statements.get("statements", {}),
    biz_intel={
        "promoter_holding_pct": "74.87%"
    }
)

print(f"  Forensic Score: {test_results['score']}/100")
print(f"  PASS: {test_results['pass_count']} | "
      f"WARN: {test_results['warn_count']} | "
      f"FAIL: {test_results['fail_count']} | "
      f"INSUFFICIENT: {test_results['insufficient_count']}")
print("\n  Test Results:")
for test_name, result in test_results["tests"].items():
    status = result.get("status", "UNKNOWN")
    note = result.get("note", "")[:60]
    print(f"  {test_name:25s}: {status:20s} | {note}")

# Summary
print("\n" + "=" * 55)
print(" SUMMARY")
print("=" * 55)
print(f" Financial data source: "
      f"{statements.get('source', 'NONE')}")
print(f" Filing searches:       "
      f"{len(filings.get('results', []))} completed")
print(f" Forensic score:        "
      f"{test_results['score']}/100")
print(f" Score Reliability:     "
      f"{test_results.get('score_reliability','N/A')}")
print(f" Caveat:                "
      f"{test_results.get('score_caveat','')[:100]}")
print(f" Tavily credits used:   ~4-6")
print("=" * 55)
