import sys
import os
import json

sys.path.insert(0, r'C:\Users\Moosa\Downloads\Project_Veritas')

from project_veritas.agents.market_intel_agent import search_sector_landscape, load_precedent_transactions, assess_competitive_position

tavily_key = os.environ.get("TAVILY_API_KEY")
if not tavily_key:
    print("ERROR: TAVILY_API_KEY not set")
    exit(1)

print("=" * 55)
print(" MARKET INTEL TAVILY ISOLATION TEST")
print("=" * 55)

print("\n[TEST 1] Sector Landscape (Tavily)...")
landscape = search_sector_landscape("Pharmaceuticals", "Mankind Pharma")
for i, res in enumerate(landscape.get("results", [])):
    print(f"  Query: {res.get('query')}")
    ans = res.get('answer', '')
    print(f"  Answer: {ans[:150]}...\n")

print("\n[TEST 2] Precedent Transactions (CapIQ)...")
deals_res = load_precedent_transactions("pharmaceuticals")
if "error" in deals_res:
    print(f"  Error: {deals_res['error']}")
else:
    deals = deals_res.get("deals", [])
    print(f"  Deals found: {len(deals)}")
    for i, d in enumerate(deals[:3]):
        # The column names are lowercased in the agent. CapIQ standard exports:
        date = d.get('announced date\nmm/dd/yyyy', 'Unknown')
        target = d.get('target/issuer name', 'Unknown')
        evebitda = d.get('implied enterprise value/ ebitda\n(x)', 'N/A')
        evrev = d.get('implied enterprise value/ total revenue\n(x)', 'N/A')
        print(f"  [{i+1}] {date} | {target} | EV/EBITDA: {evebitda} | EV/Rev: {evrev}")

print("\n[TEST 3] Competitive Position...")
comp_pos = assess_competitive_position("Mankind Pharma", "Pharmaceuticals", 9659, 0.217, {})
print("  Output:")
for k, v in comp_pos.items():
    print(f"    {k}: {v}")

print("=" * 55)
