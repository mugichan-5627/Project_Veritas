# project_veritas/tools/lbo_engine.py
# ─────────────────────────────────────────────────────────────────────
# LEVERAGED BUYOUT (LBO) MODEL ENGINE
#
# Methodology: Rosenbaum & Pearl, Chapter 5 — Leveraged Buyouts.
#              Zeisberger, Mastering Private Equity, Chapters 3-7.
#              McKinsey Valuation 6th Ed., Chapter 6 — Value Bridge.
# ─────────────────────────────────────────────────────────────────────


# =====================================================================
# CONSTANTS — Indian PE defaults (Tier 2 fallbacks)
# =====================================================================

DEFAULTS = {
    "interest_rate": 0.095,         # RBI repo + 350bps spread
    "mandatory_amort_pct": 0.05,    # Standard term loan (Rosenbaum p.289)
    "cash_sweep_pct": 0.50,         # 50% excess cash sweep
}


# =====================================================================
# STUB: Web search fallback — Phase 2 implementation
# =====================================================================

def _fetch_sector_data_web(sector, metric):
    """
    Last-resort data retrieval. Only called if local
    Damodaran and CapIQ data both return None.

    Priority enforced by caller:
    1. Damodaran Excel (already implemented)
    2. CapIQ CSV (already implemented)
    3. THIS FUNCTION — web search only as fallback
    4. Never hallucinate
    """
    import os
    from tavily import TavilyClient

    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        return None  # Web search not configured — skip silently

    try:
        client = TavilyClient(api_key=tavily_key)

        # Construct a precise financial query
        # Never ask vague questions — be specific
        query = (
            f"{sector} sector {metric} India "
            f"Damodaran OR 'SEBI filing' OR 'BSE India' "
            f"OR 'RBI' OR 'ICRA' OR 'CRISIL' "
            f"site:stern.nyu.edu OR site:bseindia.com "
            f"OR site:sebi.gov.in OR site:rbi.org.in"
        )

        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
            include_domains=[
                "stern.nyu.edu",      # Damodaran live data
                "bseindia.com",       # BSE filings
                "sebi.gov.in",        # SEBI disclosures
                "rbi.org.in",         # RBI data
                "icra.in",            # ICRA ratings
                "crisil.com",         # CRISIL ratings
                "moneycontrol.com",   # BSE-listed company filings
                "screener.in",        # Indian company financials aggregator
                "icicidirect.com",    # Research reports
                "nseindia.com"        # NSE filings mirror
            ]
        )

        results = response.get("results", [])
        if not results:
            return None

        # Return raw text — let the calling agent interpret
        # Never extract numbers here — hallucination risk
        combined = "\n\n".join([
            f"SOURCE: {r['url']}\n{r['content'][:2000]}"
            for r in results
        ])

        print(f"WEB FALLBACK: Found {len(results)} sources "
              f"for '{sector} {metric}'")
        print(f"URLs: {[r['url'] for r in results]}")

        return combined

    except Exception as e:
        print(f"WEB FALLBACK FAILED: {e}")
        return None


# =====================================================================
# HELPER: Apply defaults with warnings
# =====================================================================

def _apply_default(value, param_name, warnings_list):
    """If value is None, use default and log a warning."""
    if value is not None:
        return value
    default = DEFAULTS[param_name]
    warnings_list.append(
        f"WARNING: {param_name} not provided. "
        f"Used Indian PE default of {default}. "
        f"Verify against actual term sheet."
    )
    return default


# =====================================================================
# HELPER: PE Screen Flags
# =====================================================================

def _flag_moic(moic):
    """Flag MOIC quality per PE benchmarks."""
    # Source: Zeisberger, Mastering PE, Ch.3
    if moic >= 3.0:
        return "STRONG -- top quartile PE return"
    elif moic >= 2.0:
        return "ACCEPTABLE -- median PE fund return"
    else:
        return "WEAK -- does not clear typical PE hurdle rate"


def _flag_irr(irr):
    """Flag IRR quality per PE benchmarks."""
    if irr >= 0.25:
        return "STRONG -- exceeds typical 20% PE hurdle"
    elif irr >= 0.20:
        return "ACCEPTABLE -- meets hurdle rate"
    else:
        return "WEAK -- below PE hurdle rate"


def _flag_coverage(coverage):
    """Flag interest coverage (EBITDA/Interest in Year 1)."""
    if coverage >= 3.0:
        return "SAFE leverage"
    elif coverage >= 2.0:
        return "WATCH -- tight but manageable"
    else:
        return "DANGEROUS -- debt service risk"


# =====================================================================
# MAIN FUNCTION: run_lbo_analysis
# =====================================================================

def run_lbo_analysis(entry_ebitda, entry_ev_multiple, debt_pct_of_ev,
                     hold_years, ebitda_growth_rates, net_debt_at_target=0,
                     interest_rate=None, mandatory_amort_pct=None,
                     cash_sweep_pct=None):
    """
    Run a full LBO analysis with entry structure, debt schedule,
    three exit scenarios, value creation bridge, and PE screening.

    Parameters
    ----------
    entry_ebitda : float
        EBITDA at acquisition in crores.
    entry_ev_multiple : float
        EV/EBITDA paid at entry.
    debt_pct_of_ev : float
        Fraction of EV funded by debt (e.g., 0.50 = 50%).
    hold_years : int
        Investment horizon (typically 3-7 years).
    ebitda_growth_rates : list of float
        Annual EBITDA growth rates for the hold period.
    net_debt_at_target : float
        Target's existing net debt (added to acquisition debt).
    interest_rate : float or None
        Cost of debt. Default: 9.5% (RBI repo + 350bps).
    mandatory_amort_pct : float or None
        % of initial debt repaid per year. Default: 5%.
    cash_sweep_pct : float or None
        % of excess cash used to repay debt early. Default: 50%.

    Returns
    -------
    dict
        Complete LBO output with scenarios, value bridge, PE screen.

    Methodology Source
    ------------------
    Rosenbaum & Pearl, Chapter 5 -- Leveraged Buyouts, pp. 271-310.
    """

    # ── INPUT VALIDATION ──────────────────────────────────────────

    if entry_ebitda is None or entry_ebitda <= 0:
        raise ValueError(f"entry_ebitda required and must be positive, got {entry_ebitda}")
    if entry_ev_multiple is None or entry_ev_multiple <= 0:
        raise ValueError(f"entry_ev_multiple required and must be positive, got {entry_ev_multiple}")
    if len(ebitda_growth_rates) != hold_years:
        raise ValueError(
            f"Need {hold_years} growth rates, got {len(ebitda_growth_rates)}"
        )

    # ── APPLY DEFAULTS ────────────────────────────────────────────

    warnings = []
    interest_rate = _apply_default(interest_rate, "interest_rate", warnings)
    mandatory_amort_pct = _apply_default(mandatory_amort_pct, "mandatory_amort_pct", warnings)
    cash_sweep_pct = _apply_default(cash_sweep_pct, "cash_sweep_pct", warnings)

    # ─────────────────────────────────────────────────────────────
    # STEP 1: ENTRY STRUCTURE (Sources & Uses)
    # ─────────────────────────────────────────────────────────────
    # Entry EV = EBITDA × Multiple
    # Excel: =B2*B3
    # Source: Rosenbaum & Pearl Ch.5 p.271

    entry_ev = entry_ebitda * entry_ev_multiple
    entry_debt = entry_ev * debt_pct_of_ev
    entry_equity = entry_ev * (1 - debt_pct_of_ev)

    initial_debt = entry_debt  # Save for amort calculation

    # ─────────────────────────────────────────────────────────────
    # STEP 2: ANNUAL DEBT SCHEDULE
    # ─────────────────────────────────────────────────────────────
    # For each year:
    #   Interest = Debt_begin × interest_rate
    #   Mandatory repayment = Initial_debt × amort_pct
    #   Cash for sweep = (EBITDA - Interest) × sweep_pct
    #   Total repaid = mandatory + sweep (capped at remaining debt)
    #
    # Excel: Build row-by-row, each year references prior year's
    #        ending debt as this year's beginning debt.
    #
    # Source: Rosenbaum & Pearl Ch.5 p.289

    debt_schedule = {}
    debt_remaining = entry_debt
    ebitda = entry_ebitda

    for year in range(1, hold_years + 1):
        growth = ebitda_growth_rates[year - 1]
        ebitda = ebitda * (1 + growth)

        # Interest on beginning-of-year debt
        interest_paid = debt_remaining * interest_rate

        # Cash available after interest
        ebitda_after_interest = ebitda - interest_paid

        # Mandatory amortization (fixed % of INITIAL debt)
        mandatory_repay = min(initial_debt * mandatory_amort_pct, debt_remaining)

        # Cash sweep: % of EBITDA-after-interest goes to extra debt paydown
        if ebitda_after_interest > 0:
            cash_for_sweep = ebitda_after_interest * cash_sweep_pct
        else:
            cash_for_sweep = 0

        # Additional repayment from sweep (can't exceed remaining debt after mandatory)
        additional_repay = min(cash_for_sweep, debt_remaining - mandatory_repay)
        additional_repay = max(additional_repay, 0)  # Never negative

        total_repaid = mandatory_repay + additional_repay
        debt_remaining = debt_remaining - total_repaid

        debt_schedule[year] = {
            "ebitda_cr": round(ebitda, 2),
            "interest_paid_cr": round(interest_paid, 2),
            "mandatory_repay_cr": round(mandatory_repay, 2),
            "sweep_repay_cr": round(additional_repay, 2),
            "total_debt_repaid_cr": round(total_repaid, 2),
            "debt_remaining_cr": round(debt_remaining, 2),
        }

    # Final values at exit
    exit_ebitda = ebitda
    exit_debt = debt_remaining
    total_debt_paid_down = entry_debt - exit_debt

    # Interest coverage check (Year 1)
    yr1_coverage = debt_schedule[1]["ebitda_cr"] / debt_schedule[1]["interest_paid_cr"]

    # ─────────────────────────────────────────────────────────────
    # STEP 3: EXIT & RETURNS (3 scenarios)
    # ─────────────────────────────────────────────────────────────
    # Bear: exit_multiple = entry - 2.0 (multiple compression)
    # Base: exit_multiple = entry (no change)
    # Bull: exit_multiple = entry + 2.0 (multiple expansion)
    #
    # MOIC = Exit Equity / Entry Equity
    # IRR approx = MOIC^(1/n) - 1
    #
    # Source: Zeisberger, Mastering PE, Ch.7

    scenario_multiples = {
        "bear": entry_ev_multiple - 2.0,
        "base": entry_ev_multiple,
        "bull": entry_ev_multiple + 2.0,
    }

    scenarios = {}
    for label, exit_mult in scenario_multiples.items():
        exit_ev = exit_ebitda * exit_mult
        exit_equity = exit_ev - exit_debt

        if exit_equity <= 0:
            moic = 0.0
            irr = -1.0  # Total loss
        else:
            moic = exit_equity / entry_equity
            # IRR approximation: (MOIC)^(1/n) - 1
            irr = (moic ** (1 / hold_years)) - 1

        scenarios[label] = {
            "exit_multiple": exit_mult,
            "exit_ebitda_cr": round(exit_ebitda, 2),
            "exit_ev_cr": round(exit_ev, 2),
            "exit_debt_cr": round(exit_debt, 2),
            "exit_equity_cr": round(exit_equity, 2),
            "moic": round(moic, 2),
            "irr": round(irr, 4),
            "moic_flag": _flag_moic(moic),
            "irr_flag": _flag_irr(irr),
        }

    # ─────────────────────────────────────────────────────────────
    # STEP 4: VALUE CREATION BRIDGE (Base case)
    # ─────────────────────────────────────────────────────────────
    # Decomposes MOIC into three sources:
    #
    # Component 1 (EBITDA Growth):
    #   = (Exit EBITDA - Entry EBITDA) * Exit Multiple / Entry Equity
    #   Excel: =(exit_ebitda - entry_ebitda) * exit_mult / equity
    #
    # Component 2 (Multiple Expansion):
    #   = Entry EBITDA * (Exit Multiple - Entry Multiple) / Entry Equity
    #   Excel: =entry_ebitda * (exit_mult - entry_mult) / equity
    #
    # Component 3 (Debt Paydown):
    #   = (Entry Debt - Exit Debt) / Entry Equity
    #   Excel: =(entry_debt - exit_debt) / equity
    #
    # Verify: Sum of components ~= MOIC - 1.0
    #
    # Source: McKinsey Ch.6, Reinard PE Value Creation Vol.I Ch.8

    base_exit_mult = entry_ev_multiple  # Base case: no expansion

    ebitda_growth_contrib = (
        (exit_ebitda - entry_ebitda) * base_exit_mult / entry_equity
    )
    multiple_expansion_contrib = (
        entry_ebitda * (base_exit_mult - entry_ev_multiple) / entry_equity
    )
    debt_paydown_contrib = total_debt_paid_down / entry_equity

    bridge_total = ebitda_growth_contrib + multiple_expansion_contrib + debt_paydown_contrib
    expected_total = scenarios["base"]["moic"] - 1.0

    # Reconciliation check: do the components sum to MOIC - 1?
    if expected_total != 0:
        recon_error = abs(bridge_total - expected_total) / abs(expected_total)
    else:
        recon_error = 0.0
    recon_pass = recon_error < 0.05  # Within 5%

    value_bridge = {
        "ebitda_growth_contribution": round(ebitda_growth_contrib, 3),
        "multiple_expansion_contribution": round(multiple_expansion_contrib, 3),
        "debt_paydown_contribution": round(debt_paydown_contrib, 3),
        "total_reconciled": round(bridge_total, 3),
        "expected_moic_minus_1": round(expected_total, 3),
        "reconciliation_check": "PASS" if recon_pass else "FAIL",
    }

    if not recon_pass:
        warnings.append(
            f"WARNING: Value bridge does not reconcile. "
            f"Sum of components: {bridge_total:.3f}, "
            f"Expected (MOIC-1): {expected_total:.3f}. "
            f"Error: {recon_error:.1%}."
        )

    # ─────────────────────────────────────────────────────────────
    # CONFIDENCE & PE SCREEN
    # ─────────────────────────────────────────────────────────────

    confidence = "HIGH" if len(warnings) == 0 else ("MEDIUM" if len(warnings) <= 2 else "LOW")

    pe_screen = {
        "base_moic_flag": scenarios["base"]["moic_flag"],
        "base_irr_flag": scenarios["base"]["irr_flag"],
        "debt_coverage_flag": _flag_coverage(yr1_coverage),
        "year1_interest_coverage": round(yr1_coverage, 2),
    }

    # ─────────────────────────────────────────────────────────────
    # ASSEMBLE OUTPUT
    # ─────────────────────────────────────────────────────────────

    result = {
        "entry_structure": {
            "entry_ev_cr": round(entry_ev, 2),
            "entry_debt_cr": round(entry_debt, 2),
            "entry_equity_cr": round(entry_equity, 2),
            "debt_to_ev_ratio": round(debt_pct_of_ev, 2),
            "implied_entry_multiple": entry_ev_multiple,
        },
        "debt_schedule": debt_schedule,
        "scenarios": scenarios,
        "value_creation_bridge": value_bridge,
        "pe_screen": pe_screen,
        "data_quality": {
            "inputs_defaulted": [w.split(".")[0] for w in warnings if "not provided" in w],
            "warnings": warnings,
            "confidence": confidence,
        },
        "methodology_sources": {
            "entry_structure": (
                "Rosenbaum & Pearl, Ch.5 p.271 -- Sources & Uses table. "
                "Equity + Debt = Total EV at acquisition."
            ),
            "debt_schedule": (
                "Rosenbaum & Pearl, Ch.5 p.289 -- Debt Repayment Schedule. "
                "Zeisberger, Mastering PE, Ch.4 -- Debt Waterfall. "
                "Mandatory amortisation + cash sweep = total annual paydown."
            ),
            "returns": (
                "Zeisberger, Mastering PE, Ch.7 -- Returns. "
                "MOIC = Exit Equity / Entry Equity. "
                "IRR approximation: (MOIC)^(1/n) - 1."
            ),
            "value_bridge": (
                "McKinsey Valuation 6th Ed., Ch.6. "
                "Reinard, PE Value Creation Analysis Vol.I, Ch.8. "
                "Three sources: earnings growth, re-rating, leverage."
            ),
            "pe_benchmarks": (
                "Zeisberger, Mastering PE, Ch.3 -- PE Return Benchmarks. "
                "Standard hurdle: 20% IRR / 2.5x MOIC."
            ),
        },
    }

    return result


# =====================================================================
# TEST SECTION
# =====================================================================

if __name__ == "__main__":

    result = run_lbo_analysis(
        entry_ebitda=13.5,
        entry_ev_multiple=12.0,
        debt_pct_of_ev=0.50,
        hold_years=5,
        ebitda_growth_rates=[0.20, 0.18, 0.15, 0.12, 0.10],
        interest_rate=0.095,
        mandatory_amort_pct=0.05,
        cash_sweep_pct=0.50,
    )

    # ── Entry Structure ──
    e = result["entry_structure"]
    print("=" * 70)
    print("  PROJECT VERITAS -- LBO MODEL ENGINE")
    print("=" * 70)
    print(f"\n--- ENTRY STRUCTURE (Sources & Uses) ---")
    print(f"  Entry EV:      {e['entry_ev_cr']:>10.2f} Cr  ({e['implied_entry_multiple']}x EBITDA)")
    print(f"  Debt (source): {e['entry_debt_cr']:>10.2f} Cr  ({e['debt_to_ev_ratio']:.0%} of EV)")
    print(f"  Equity (use):  {e['entry_equity_cr']:>10.2f} Cr  ({1-e['debt_to_ev_ratio']:.0%} of EV)")

    # ── Debt Schedule ──
    print(f"\n--- DEBT SCHEDULE (Cr) ---\n")
    hdr = f"{'Year':>5} | {'EBITDA':>8} | {'Interest':>8} | {'Repaid':>8} | {'Debt Left':>10}"
    print(hdr)
    print("-" * len(hdr))
    for yr, d in result["debt_schedule"].items():
        print(f"{yr:>5} | {d['ebitda_cr']:>8.2f} | {d['interest_paid_cr']:>8.2f} | "
              f"{d['total_debt_repaid_cr']:>8.2f} | {d['debt_remaining_cr']:>10.2f}")

    # ── Exit Scenarios ──
    print(f"\n--- EXIT SCENARIOS ---\n")
    hdr2 = f"{'Case':>6} | {'Exit Mult':>9} | {'Exit EV':>9} | {'Exit Eq':>9} | {'MOIC':>6} | {'IRR':>7} | Flag"
    print(hdr2)
    print("-" * len(hdr2))
    for label, s in result["scenarios"].items():
        print(f"{label:>6} | {s['exit_multiple']:>9.1f}x | {s['exit_ev_cr']:>8.1f} | "
              f"{s['exit_equity_cr']:>8.1f} | {s['moic']:>5.2f}x | "
              f"{s['irr']:>6.1%} | {s['moic_flag']}")

    # ── Value Creation Bridge ──
    vb = result["value_creation_bridge"]
    print(f"\n--- VALUE CREATION BRIDGE (Base Case) ---")
    print(f"  EBITDA Growth:       +{vb['ebitda_growth_contribution']:.3f}x")
    print(f"  Multiple Expansion:  +{vb['multiple_expansion_contribution']:.3f}x")
    print(f"  Debt Paydown:        +{vb['debt_paydown_contribution']:.3f}x")
    print(f"  ────────────────────────────")
    print(f"  Total (bridge):      +{vb['total_reconciled']:.3f}x")
    print(f"  Expected (MOIC-1):   +{vb['expected_moic_minus_1']:.3f}x")
    print(f"  Reconciliation:       {vb['reconciliation_check']}")

    # ── PE Screen ──
    ps = result["pe_screen"]
    print(f"\n--- PE SCREENING ---")
    print(f"  MOIC:      {ps['base_moic_flag']}")
    print(f"  IRR:       {ps['base_irr_flag']}")
    print(f"  Coverage:  {ps['debt_coverage_flag']} ({ps['year1_interest_coverage']:.1f}x)")

    # ── Warnings ──
    if result["data_quality"]["warnings"]:
        print(f"\n--- WARNINGS ---")
        for w in result["data_quality"]["warnings"]:
            print(f"  {w}")

    print(f"\n  Confidence: {result['data_quality']['confidence']}")

    # ── CROSS-CHECK: Football Field ──
    print(f"\n{'=' * 70}")
    print(f"  TRIANGULATION CROSS-CHECK (Football Field)")
    print(f"{'=' * 70}")
    print(f"  Comparable Comps (median EV):   162.00 Cr  (12.0x on 13.5 Cr EBITDA)")
    print(f"  DCF Engine (Enterprise Value):  117.38 Cr  (13% WACC, conservative)")
    print(f"  LBO Entry EV:                   {e['entry_ev_cr']:.2f} Cr  ({e['implied_entry_multiple']}x entry)")
    print(f"")
    print(f"  Range: 117 Cr (DCF floor) ---- 162 Cr (market/LBO) = 38% spread")
    print(f"  Interpretation below...")
    print("=" * 70)
