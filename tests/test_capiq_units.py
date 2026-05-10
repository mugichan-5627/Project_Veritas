"""Quick test: verify capiq_loader handles both India (mixed ₹M/₹000) and Global ($M) files."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "project_veritas"))
os.environ["PYTHONIOENCODING"] = "utf-8"

from memory.capiq_loader import get_comp_stats, get_public_comps, _extract_unit, load_peers_from_capiq

# Test 1: Unit detection
print("=" * 60)
print("  TEST 1: Unit Detection from Column Headers")
print("=" * 60)
tests = [
    ("Market Capitalization\n(₹M)", "M"),
    ("Total Revenue\n(₹000)", "000"),
    ("EBITDA\n($M)", "M"),
    ("EV/EBITDA\n(x)", "x"),
    ("EBITDA Margin\n(%)", None),  # % may not match \w+
]
for col, expected in tests:
    result = _extract_unit(col)
    status = "PASS" if result == expected else f"FAIL (got {result})"
    print(f"  {col.replace(chr(10),' ')[:40]:40s} => {result!s:6s} {status}")

# Test 2: India comps (mixed units)
print("\n" + "=" * 60)
print("  TEST 2: India Healthcare Comps (mixed INR M + 000)")
print("=" * 60)
stats_india = get_comp_stats('healthcare')
if stats_india:
    for k, v in stats_india.items():
        print(f"  {k}: {v}")
    ev_median = stats_india.get('ev_ebitda_median', 0)
    if 0 < ev_median < 100:
        print(f"  VERDICT: PASS (median EV/EBITDA {ev_median:.1f}x is reasonable)")
    else:
        print(f"  VERDICT: FAIL (median EV/EBITDA {ev_median} is unreasonable)")
else:
    print("  No data returned")

# Test 3: Global comps (consistent $M)
print("\n" + "=" * 60)
print("  TEST 3: Global Healthcare Comps (all USD M)")
print("=" * 60)
df_global = get_public_comps('healthcare')
# Check if any global file was used by looking for $ in column names
dollar_cols = [c for c in df_global.columns if '$' in str(c)]
rupee_cols = [c for c in df_global.columns if '₹' in str(c) or 'INR' in str(c).upper()]

if dollar_cols:
    print(f"  USD columns found: {len(dollar_cols)} (global file)")
if rupee_cols:
    print(f"  INR columns found: {len(rupee_cols)} (india file)")

if 'ev_ebitda_final' in df_global.columns:
    valid = df_global['ev_ebitda_final'].dropna()
    valid = valid[(valid > 0) & (valid < 100)]
    print(f"  Valid EV/EBITDA ratios: {len(valid)} companies")
    if len(valid) > 0:
        print(f"  Range: {valid.min():.1f}x - {valid.max():.1f}x")
        print(f"  Median: {valid.median():.1f}x")
        if 2 < valid.median() < 80:
            print(f"  VERDICT: PASS (ratios are in institutional range)")
        else:
            print(f"  VERDICT: FAIL (ratios look wrong)")

# Test 4: Peer loading with revenue matching
print("\n" + "=" * 60)
print("  TEST 4: Peer Loading (Mankind Pharma ~9659 Cr revenue)")
print("=" * 60)
peers = load_peers_from_capiq("healthcare", target_revenue_cr=9659)
for p in peers:
    print(f"  {p['name']:30s} EV/EBITDA: {p['ev_ebitda']:.1f}x  EV/Rev: {p['ev_revenue']}")

print("\n" + "=" * 60)
print("  ALL TESTS COMPLETE")
print("=" * 60)
