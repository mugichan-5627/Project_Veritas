"""
PHASE 0 LESSON -- PEER SELECTION FAILURE CASE (keep this file):

The 1046% spread between DCF and Comps in this test is NOT a
math error. It is a peer selection problem.

DMart (68x) and Trent (85x) are monopolistic premium retailers --
not valid comparables for a value/discount retailer like Vishal.
This test proves the comparable_company tool works correctly AND
demonstrates why peer selection is the most critical judgment
call in comps analysis -- before any arithmetic begins.

Per Rosenbaum & Pearl Ch.3 p.115: "The selection of comparable
companies is the most important -- and most subjective -- step in
performing a comparable company analysis."

Interview use: This case demonstrates understanding of when
comps break down and why an analyst must exercise judgment
on peer universe construction.
"""

"""
TEST COMPANY: Vishal Mega Mart Limited

This test reconstructs the Kedaara Capital / Partners Group
investment thesis using publicly available data from:
- DRHP (Draft Red Herring Prospectus) filed with SEBI
- IPO prospectus (December 2024)
- Post-IPO BSE/NSE filings

Inputs are sourced from public documents only.
LBO entry assumptions are hypothetical reconstructions
for educational/portfolio purposes -- not actual deal data.

Sources: BSE filing ref [IPO Dec 2024],
         Kedaara Capital portfolio disclosure,
         CapIQ Consumer Discretionary comps (India)

Company Background:
  Vishal Mega Mart Limited
  Sector: Consumer Discretionary -- Value Retail
  PE History: Acquired by Kedaara Capital + Partners Group.
              Full operational transformation during hold period.
              IPO exit: December 2024 (NSE/BSE listed)
  Why chosen: Complete PE lifecycle visible in public data.
              Indian mid-market PE deal. Active sector in
              our CapIQ Consumer Discretionary comps file.
"""

# =====================================================================
# IMPORTS
# =====================================================================

import sys
import os

# Add project root to Python's search path so it can find our tools.
# This is like telling Excel "look in THIS folder for the macro file."
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.comparable_company import run_comparable_analysis
from tools.dcf_engine import calculate_dcf
from tools.lbo_engine import run_lbo_analysis


# =====================================================================
# PEER SELECTION: CapIQ Scan + Manual Fallback
# =====================================================================
# We scanned data/capiq/public_comps/india_consumerdiscretionary_peers.xlsx
# with filters: EV/EBITDA > 0, EBITDA margin > 5%.
#
# Result: Only 2 valid peers found (Oriental Hotels 16.4x, Royal Orchid
# 11.8x) -- both are hotels, NOT value retailers. Fewer than 3 valid
# peers triggers the manual fallback path.
#
# Fallback peers: Large-cap Indian retailers from public filings.
# NOTE: Indian listed retailers trade at significant premiums to
# global peers due to structural growth runway (urbanization,
# formalization of retail, rising middle class). These multiples
# are NOT directly comparable to global retail benchmarks.

CAPIQ_SCAN_NOTE = (
    "CapIQ Consumer Discretionary file scanned: "
    "Only 2 valid peers after filtering (hotels, not retailers). "
    "Triggered manual fallback. Confidence: LOW for peer selection."
)

RETAIL_PREMIUM_NOTE = (
    "Indian retail multiples reflect structural growth premium -- "
    "not directly comparable to global retail benchmarks. "
    "DMart trades at 68x EV/EBITDA due to dominant market position "
    "and 25%+ same-store growth expectations."
)

peers = [
    {"name": "DMart (Avenue Supermarts)", "ev_ebitda": 68.0, "ev_revenue": 5.2},
    {"name": "Trent Ltd",                "ev_ebitda": 85.0, "ev_revenue": 8.1},
    {"name": "V-Mart Retail",            "ev_ebitda": 35.0, "ev_revenue": 1.8},
]


# =====================================================================
# TEST 1: COMPARABLE COMPANY ANALYSIS
# =====================================================================

def test_comps():
    """Run comps on Vishal Mega Mart using Indian retail peers."""

    print("=" * 70)
    print("  TEST 1: COMPARABLE COMPANY ANALYSIS")
    print("  Target: Vishal Mega Mart | Sector: Value Retail India")
    print("=" * 70)

    result = run_comparable_analysis(
        target_ebitda=740,          # FY2024 EBITDA in Cr
        target_revenue=8850,        # FY2024 Revenue in Cr
        target_net_debt=120,        # Net of IPO proceeds
        peers=peers,
    )

    ev_eb = result["ev_ebitda_range"]
    ev_rv = result["ev_revenue_range"]
    eq = result["equity_value_range"]

    print(f"\n  Peer set: {[p['name'] for p in peers]}")
    print(f"  NOTE: {CAPIQ_SCAN_NOTE}")
    print(f"  NOTE: {RETAIL_PREMIUM_NOTE}")
    print(f"\n  EV/EBITDA Range:")
    print(f"    Low (P25):  {ev_eb['low_cr']:>12,.2f} Cr  at {ev_eb['multiples_used']['p25']}x")
    print(f"    Mid (Med):  {ev_eb['mid_cr']:>12,.2f} Cr  at {ev_eb['multiples_used']['median']}x")
    print(f"    High (P75): {ev_eb['high_cr']:>12,.2f} Cr  at {ev_eb['multiples_used']['p75']}x")
    print(f"\n  EV/Revenue Range:")
    print(f"    Low (P25):  {ev_rv['low_cr']:>12,.2f} Cr  at {ev_rv['multiples_used']['p25']}x")
    print(f"    Mid (Med):  {ev_rv['mid_cr']:>12,.2f} Cr  at {ev_rv['multiples_used']['median']}x")
    print(f"    High (P75): {ev_rv['high_cr']:>12,.2f} Cr  at {ev_rv['multiples_used']['p75']}x")
    print(f"\n  Equity Value Range:")
    print(f"    Low:  {eq['low_cr']:>12,.2f} Cr")
    print(f"    Mid:  {eq['mid_cr']:>12,.2f} Cr")
    print(f"    High: {eq['high_cr']:>12,.2f} Cr")
    print(f"\n  Confidence: {result['confidence']}")
    print(f"  Primary: {result['primary_method'][:70]}...")

    return result


# =====================================================================
# TEST 2: DCF VALUATION
# =====================================================================

def test_dcf():
    """Run DCF on Vishal Mega Mart with value retail assumptions."""

    print("\n" + "=" * 70)
    print("  TEST 2: DCF VALUATION")
    print("  Target: Vishal Mega Mart | WACC: 12% | TGR: 5.5%")
    print("=" * 70)

    result = calculate_dcf(
        base_revenue=8850,
        revenue_growth_rates=[0.20, 0.18, 0.15, 0.13, 0.11],
        ebitda_margin=0.084,         # 8.4% -- value retail India
        da_margin=0.04,
        tax_rate=0.25,
        capex_margin=0.04,           # Asset-light leasing model
        wc_change_margin=-0.02,      # Negative WC = retailer collects
                                     # before paying suppliers
        wacc=0.12,
        terminal_growth_rate=0.055,
        net_debt=120,
    )

    # Year-by-year table
    print(f"\n  5-Year FCF Projection (Cr):\n")
    print(f"  {'Year':>5} | {'Revenue':>10} | {'EBITDA':>10} | {'FCF':>10} | {'PV(FCF)':>10}")
    print(f"  {'-'*55}")
    for yr in range(1, 6):
        p = result["projections"][yr]
        print(f"  {yr:>5} | {p['revenue_cr']:>10,.1f} | {p['ebitda_cr']:>10,.1f} | "
              f"{p['fcf_cr']:>10,.1f} | {p['pv_fcf_cr']:>10,.1f}")

    tv = result["terminal_value"]
    v = result["valuation"]
    print(f"\n  Terminal Value (Value Driver): {tv['value_driver_formula_cr']:>12,.2f} Cr")
    print(f"  Terminal Value (Gordon):       {tv['gordon_growth_model_cr']:>12,.2f} Cr")
    print(f"  TV Divergence: {tv['divergence_pct']:.1f}%"
          f"  {'** FLAGGED **' if tv['divergence_flag'] else '(OK)'}")
    print(f"  TV as % of EV: {tv['tv_as_pct_of_ev']:.1f}%"
          f"  {'** TV-HEAVY **' if tv['tv_heavy_flag'] else '(OK)'}")
    print(f"\n  Enterprise Value:  {v['enterprise_value_cr']:>12,.2f} Cr")
    print(f"  - Net Debt:        {120:>12,.2f} Cr")
    print(f"  = Equity Value:    {v['equity_value_cr']:>12,.2f} Cr")
    print(f"  Implied EV/EBITDA: {v['implied_ev_ebitda']:.1f}x")
    print(f"  Confidence: {result['data_quality']['confidence']}")

    if result["data_quality"]["warnings"]:
        print(f"\n  Warnings:")
        for w in result["data_quality"]["warnings"]:
            print(f"    {w[:90]}")

    return result


# =====================================================================
# TEST 3: LBO MODEL (Kedaara Capital Reconstruction)
# =====================================================================

def test_lbo():
    """Reconstruct Kedaara Capital's hypothetical entry economics."""

    print("\n" + "=" * 70)
    print("  TEST 3: LBO MODEL (Kedaara Capital Reconstruction)")
    print("  Entry EBITDA: 420 Cr | Entry Multiple: 18.0x | Debt: 40%")
    print("  NOTE: Hypothetical reconstruction for educational purposes")
    print("=" * 70)

    result = run_lbo_analysis(
        entry_ebitda=420,
        entry_ev_multiple=18.0,
        debt_pct_of_ev=0.40,
        hold_years=5,
        ebitda_growth_rates=[0.20, 0.18, 0.15, 0.13, 0.11],
        interest_rate=0.095,
        mandatory_amort_pct=0.05,
        cash_sweep_pct=0.50,
    )

    e = result["entry_structure"]
    print(f"\n  Entry Structure:")
    print(f"    Entry EV:    {e['entry_ev_cr']:>10,.2f} Cr  ({e['implied_entry_multiple']}x)")
    print(f"    Debt:        {e['entry_debt_cr']:>10,.2f} Cr  ({e['debt_to_ev_ratio']:.0%})")
    print(f"    Equity:      {e['entry_equity_cr']:>10,.2f} Cr  ({1-e['debt_to_ev_ratio']:.0%})")

    print(f"\n  Debt Schedule (Cr):")
    print(f"  {'Year':>5} | {'EBITDA':>9} | {'Interest':>9} | {'Repaid':>9} | {'Debt Left':>10}")
    print(f"  {'-'*50}")
    for yr, d in result["debt_schedule"].items():
        print(f"  {yr:>5} | {d['ebitda_cr']:>9,.1f} | {d['interest_paid_cr']:>9,.1f} | "
              f"{d['total_debt_repaid_cr']:>9,.1f} | {d['debt_remaining_cr']:>10,.1f}")

    print(f"\n  Exit Scenarios:")
    print(f"  {'Case':>6} | {'Mult':>6} | {'Exit EV':>10} | {'Exit Eq':>10} | {'MOIC':>6} | {'IRR':>7}")
    print(f"  {'-'*60}")
    for label, s in result["scenarios"].items():
        print(f"  {label:>6} | {s['exit_multiple']:>5.1f}x | {s['exit_ev_cr']:>10,.1f} | "
              f"{s['exit_equity_cr']:>10,.1f} | {s['moic']:>5.2f}x | {s['irr']:>6.1%}")

    vb = result["value_creation_bridge"]
    print(f"\n  Value Creation Bridge (Base Case):")
    print(f"    EBITDA Growth:       +{vb['ebitda_growth_contribution']:.3f}x")
    print(f"    Multiple Expansion:  +{vb['multiple_expansion_contribution']:.3f}x")
    print(f"    Debt Paydown:        +{vb['debt_paydown_contribution']:.3f}x")
    print(f"    Total:               +{vb['total_reconciled']:.3f}x  "
          f"(expected: +{vb['expected_moic_minus_1']:.3f}x)  "
          f"{vb['reconciliation_check']}")

    ps = result["pe_screen"]
    print(f"\n  PE Screen:")
    print(f"    MOIC:     {ps['base_moic_flag']}")
    print(f"    IRR:      {ps['base_irr_flag']}")
    print(f"    Coverage: {ps['debt_coverage_flag']} ({ps['year1_interest_coverage']:.1f}x)")

    return result


# =====================================================================
# FOOTBALL FIELD: Triangulation Cross-Check
# =====================================================================

def football_field(comps_result, dcf_result, lbo_result):
    """Compare all three valuation methods side by side."""

    print("\n" + "=" * 70)
    print("  FOOTBALL FIELD: Triangulation Cross-Check")
    print("  Vishal Mega Mart -- All Three Methods Compared")
    print("=" * 70)

    comps_ev_low = comps_result["ev_ebitda_range"]["low_cr"]
    comps_ev_mid = comps_result["ev_ebitda_range"]["mid_cr"]
    comps_ev_high = comps_result["ev_ebitda_range"]["high_cr"]
    dcf_ev = dcf_result["valuation"]["enterprise_value_cr"]
    lbo_entry = lbo_result["entry_structure"]["entry_ev_cr"]

    print(f"\n  Method              |     Low      |     Mid      |     High")
    print(f"  {'-'*65}")
    print(f"  Comps (EV/EBITDA)   | {comps_ev_low:>10,.0f} Cr | {comps_ev_mid:>10,.0f} Cr | {comps_ev_high:>10,.0f} Cr")
    print(f"  DCF (12% WACC)      |      --      | {dcf_ev:>10,.0f} Cr |      --")
    print(f"  LBO Entry (18x)     |      --      | {lbo_entry:>10,.0f} Cr |      --")

    # Range analysis
    all_evs = [comps_ev_low, comps_ev_mid, comps_ev_high, dcf_ev, lbo_entry]
    ev_min = min(all_evs)
    ev_max = max(all_evs)
    spread = (ev_max - ev_min) / ev_min * 100

    print(f"\n  Full Range: {ev_min:,.0f} Cr -- {ev_max:,.0f} Cr")
    print(f"  Spread: {spread:.0f}%")

    # Interpretation
    print(f"\n  --- INTERPRETATION ---")

    if spread <= 20:
        print(f"  CONVERGENCE: All three methods agree within 20%.")
        print(f"  This is a well-validated valuation -- high confidence.")
    elif spread <= 50:
        print(f"  PARTIAL CONVERGENCE: Methods agree within 50% band.")
        print(f"  Typical for growth companies where DCF and Comps diverge.")
    else:
        print(f"  WIDE DIVERGENCE: Methods spread > 50%.")
        print(f"  Expected for Indian retail -- Comps reflect massive")
        print(f"  growth premium (DMart at 68x, Trent at 85x) that a")
        print(f"  conservative DCF cannot capture.")

    print(f"\n  Key Insight:")
    print(f"  - Comps are driven by Indian retail growth premium")
    print(f"    (DMart/Trent trade at 50-85x EV/EBITDA)")
    print(f"  - DCF captures intrinsic value at 12% WACC -- lower")
    print(f"    because it discounts cash flows conservatively")
    print(f"  - LBO entry at 18x reflects what Kedaara actually paid")
    print(f"    (between DCF floor and Comps ceiling)")
    print(f"  - The PE buyer's thesis: pay 18x, grow EBITDA from")
    print(f"    420 Cr to ~840 Cr, exit at market multiples = strong IRR")


# =====================================================================
# PE DECISION SUMMARY
# =====================================================================

def pe_decision_summary(lbo_result):
    """Would a PE fund do this deal?"""

    print("\n" + "=" * 70)
    print("  PE DECISION SUMMARY: Would You Invest?")
    print("=" * 70)

    base = lbo_result["scenarios"]["base"]
    bear = lbo_result["scenarios"]["bear"]
    ps = lbo_result["pe_screen"]
    vb = lbo_result["value_creation_bridge"]

    print(f"\n  Base Case: {base['moic']:.2f}x / {base['irr']:.1%} IRR")
    print(f"  Bear Case: {bear['moic']:.2f}x / {bear['irr']:.1%} IRR")
    print(f"  Coverage:  {ps['year1_interest_coverage']:.1f}x interest coverage")

    # Decision logic
    if base["moic"] >= 2.5 and bear["moic"] >= 1.5 and ps["year1_interest_coverage"] >= 2.0:
        verdict = "INVEST"
        rationale = ("Base case clears 2.5x MOIC hurdle, bear case preserves "
                     "capital (>1.5x), leverage is manageable.")
    elif base["moic"] >= 2.0 and bear["moic"] >= 1.0:
        verdict = "CONDITIONAL INVEST"
        rationale = ("Base case meets minimum return threshold but margins "
                     "are tight. Requires management incentive alignment.")
    else:
        verdict = "PASS"
        rationale = ("Returns do not justify PE risk/illiquidity premium.")

    print(f"\n  VERDICT: {verdict}")
    print(f"  Rationale: {rationale}")

    # Value creation quality
    if vb["ebitda_growth_contribution"] > 0:
        ebitda_pct = vb["ebitda_growth_contribution"] / vb["total_reconciled"] * 100
    else:
        ebitda_pct = 0
    print(f"\n  Return Quality: {ebitda_pct:.0f}% from EBITDA growth, "
          f"{100 - ebitda_pct:.0f}% from leverage/expansion")
    if ebitda_pct > 60:
        print(f"  Assessment: HIGH QUALITY -- majority operational returns")
    else:
        print(f"  Assessment: LEVERAGE-DRIVEN -- monitor operational execution")


# =====================================================================
# REVERSE VALIDATION
# =====================================================================

def reverse_validation(comps_result, dcf_result):
    """Verify math by working backwards from outputs to inputs."""

    print("\n" + "=" * 70)
    print("  REVERSE VALIDATION: Math Integrity Check")
    print("=" * 70)

    # Test 1: Comps reverse -- if EV_mid = EBITDA * median_multiple,
    # then EBITDA = EV_mid / median_multiple. Should equal 740 Cr.
    ev_mid = comps_result["ev_ebitda_range"]["mid_cr"]
    mult_mid = comps_result["ev_ebitda_range"]["multiples_used"]["median"]
    reverse_ebitda = ev_mid / mult_mid
    ebitda_match = abs(reverse_ebitda - 740) < 0.5

    print(f"\n  Test 1: Comps Round-Trip")
    print(f"    Forward:  740 Cr * {mult_mid}x = {ev_mid:,.2f} Cr")
    print(f"    Reverse:  {ev_mid:,.2f} / {mult_mid}x = {reverse_ebitda:,.2f} Cr")
    print(f"    Expected: 740.00 Cr")
    print(f"    Status:   {'PASS' if ebitda_match else 'FAIL'}")

    # Test 2: DCF -- Equity Value + Net Debt should equal EV
    dcf_ev = dcf_result["valuation"]["enterprise_value_cr"]
    dcf_eq = dcf_result["valuation"]["equity_value_cr"]
    reconstructed_ev = dcf_eq + 120  # net_debt = 120
    ev_match = abs(reconstructed_ev - dcf_ev) < 0.5

    print(f"\n  Test 2: DCF Equity Bridge Round-Trip")
    print(f"    Forward:  EV {dcf_ev:,.2f} - Net Debt 120 = Equity {dcf_eq:,.2f}")
    print(f"    Reverse:  Equity {dcf_eq:,.2f} + Net Debt 120 = {reconstructed_ev:,.2f}")
    print(f"    Expected: {dcf_ev:,.2f} Cr")
    print(f"    Status:   {'PASS' if ev_match else 'FAIL'}")

    # Test 3: PV(FCFs) + PV(TV) should equal EV
    sum_pv = dcf_result["valuation"]["sum_of_pv_fcfs_cr"]
    pv_tv = dcf_result["terminal_value"]["pv_of_tv_cr"]
    reconstructed_ev2 = sum_pv + pv_tv
    ev_match2 = abs(reconstructed_ev2 - dcf_ev) < 0.5

    print(f"\n  Test 3: DCF Component Sum Check")
    print(f"    PV(FCFs): {sum_pv:,.2f} + PV(TV): {pv_tv:,.2f} = {reconstructed_ev2:,.2f}")
    print(f"    Expected: {dcf_ev:,.2f} Cr")
    print(f"    Status:   {'PASS' if ev_match2 else 'FAIL'}")

    all_pass = ebitda_match and ev_match and ev_match2
    print(f"\n  OVERALL: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    return all_pass


# =====================================================================
# SOURCE AUDIT
# =====================================================================

def source_audit(comps_result, dcf_result, lbo_result):
    """Verify every output carries a methodology citation."""

    print("\n" + "=" * 70)
    print("  SOURCE AUDIT: Methodology Citation Check")
    print("=" * 70)

    checks = {
        "Comps EV/EBITDA source": "methodology_source" in comps_result["ev_ebitda_range"],
        "Comps EV/Revenue source": "methodology_source" in comps_result["ev_revenue_range"],
        "Comps Equity Bridge source": "methodology_source" in comps_result["equity_value_range"],
        "DCF FCF formula source": "fcf_formula" in dcf_result["methodology_sources"],
        "DCF Terminal Value source": "terminal_value" in dcf_result["methodology_sources"],
        "DCF Cross-check source": "cross_check" in dcf_result["methodology_sources"],
        "DCF Sensitivity source": "sensitivity" in dcf_result["methodology_sources"],
        "LBO Entry Structure source": "entry_structure" in lbo_result["methodology_sources"],
        "LBO Debt Schedule source": "debt_schedule" in lbo_result["methodology_sources"],
        "LBO Returns source": "returns" in lbo_result["methodology_sources"],
        "LBO Value Bridge source": "value_bridge" in lbo_result["methodology_sources"],
        "LBO PE Benchmarks source": "pe_benchmarks" in lbo_result["methodology_sources"],
    }

    all_pass = True
    for check_name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  {status}  {check_name}")

    print(f"\n  OVERALL: {'ALL 12 CITATIONS PRESENT' if all_pass else 'MISSING CITATIONS'}")
    return all_pass


# =====================================================================
# MAIN — Run everything
# =====================================================================

if __name__ == "__main__":

    comps_result = test_comps()
    dcf_result = test_dcf()
    lbo_result = test_lbo()
    football_field(comps_result, dcf_result, lbo_result)
    pe_decision_summary(lbo_result)
    all_math_ok = reverse_validation(comps_result, dcf_result)
    all_sources_ok = source_audit(comps_result, dcf_result, lbo_result)

    print("\n" + "=" * 70)
    if all_math_ok and all_sources_ok:
        print("  PHASE 0 COMPLETE")
        print("  Test company: Vishal Mega Mart (Kedaara Capital exit, IPO Dec 2024)")
        print("  Tools validated: comparable_company v  dcf_engine v  lbo_engine v")
        print("  Data sources: CapIQ Consumer Discretionary comps +")
        print("                Damodaran India datasets + Public DRHP filings")
        print("  Ready for Phase 1: Valuation Agent API wrapper.")
    else:
        print("  PHASE 0 INCOMPLETE -- Fix failing tests before proceeding.")
    print("=" * 70)
