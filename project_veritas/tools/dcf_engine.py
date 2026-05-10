# project_veritas/tools/dcf_engine.py
# ─────────────────────────────────────────────────────────────────────
# DISCOUNTED CASH FLOW (DCF) VALUATION ENGINE
#
# Methodology: McKinsey & Company, "Valuation: Measuring and Managing
#              the Value of Companies," 6th Edition, Chapter 3.
# Cross-check: Damodaran, "Investment Valuation," 3rd Edition, Ch. 12.
# Sensitivity: Rosenbaum & Pearl, "Investment Banking," Chapter 4.
# ─────────────────────────────────────────────────────────────────────


# =====================================================================
# IMPORTS
# =====================================================================

from statistics import median


# =====================================================================
# CONSTANTS — Indian mid-market defaults (Tier 2 fallbacks)
# =====================================================================
# These are used ONLY when the user doesn't provide a value AND
# we can't find sector data. Every use is flagged with a warning.

DEFAULTS = {
    "ebitda_margin": 0.18,      # Damodaran marginIndia median
    "da_margin": 0.04,          # Damodaran India median
    "tax_rate": 0.25,           # Indian corporate tax rate
    "capex_margin": 0.05,       # Damodaran capexIndia median
    "wc_change_margin": 0.02,   # Damodaran wcdataIndia median
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
# HELPER: Apply defaults with warnings (Tiered NA Handling)
# =====================================================================

def _apply_defaults(value, param_name, warnings_list):
    """
    If value is None, substitute the Indian mid-market default
    and log a warning. If value is provided, return it unchanged.

    Parameters
    ----------
    value : float or None
        The user-provided input.
    param_name : str
        Name of the parameter (must match a key in DEFAULTS).
    warnings_list : list
        Mutable list — we append warning strings into this.

    Returns
    -------
    float
        Either the original value or the default.
    """
    if value is not None:
        return value

    default = DEFAULTS[param_name]
    warning_msg = (
        f"WARNING: {param_name} not provided. "
        f"Used Indian mid-market default of {default:.0%} "
        f"per Damodaran India dataset. "
        f"Verify against company filings before IC presentation."
    )
    warnings_list.append(warning_msg)
    return default


# =====================================================================
# MAIN FUNCTION: calculate_dcf
# =====================================================================

def calculate_dcf(base_revenue, revenue_growth_rates, wacc,
                  terminal_growth_rate, net_debt,
                  ebitda_margin=None, da_margin=None,
                  tax_rate=None, capex_margin=None,
                  wc_change_margin=None, ronic=None, sector=None):
    """
    Run a full DCF valuation with 5-year projection, terminal value
    (dual-method), equity bridge, and sensitivity analysis.

    Parameters
    ----------
    base_revenue : float
        Year 0 Revenue in crores. REQUIRED -- cannot be defaulted.
    revenue_growth_rates : list of float
        Annual growth rates for years 1-5, e.g. [0.22, 0.20, ...].
    wacc : float
        Weighted Average Cost of Capital, e.g. 0.13 for 13%.
        REQUIRED -- cannot be defaulted.
    terminal_growth_rate : float
        Long-run perpetuity growth rate, e.g. 0.05 for 5%.
    net_debt : float
        Net Debt in crores (Total Debt - Cash).
    ebitda_margin : float or None
        EBITDA as fraction of revenue. Default: 0.18.
    da_margin : float or None
        Depreciation & Amortization as fraction of revenue.
    tax_rate : float or None
        Effective corporate tax rate. Default: 0.25.
    capex_margin : float or None
        Capital expenditure as fraction of revenue. Default: 0.05.
    wc_change_margin : float or None
        Change in working capital as fraction of revenue. Default: 0.02.
    ronic : float or None
        Return on New Invested Capital for Value Driver Formula.
        If None, defaults to WACC (conservative assumption).
    sector : str or None
        Sector name for Damodaran data lookup (Phase 2).

    Returns
    -------
    dict
        Complete valuation output with projections, terminal value,
        sensitivity table, data quality flags, and methodology sources.

    Methodology Source
    ------------------
    McKinsey Valuation 6th Ed., Chapter 3 -- Frameworks for Valuation.
    FCF = NOPLAT + D&A - Capex - delta_NWC
    TV = NOPLAT(1-g/RONIC)/(WACC-g) [Value Driver Formula, p.214]
    """

    # ── INPUT VALIDATION ──────────────────────────────────────────
    # base_revenue and wacc are Tier 3: cannot be defaulted.

    if base_revenue is None or base_revenue <= 0:
        raise ValueError(
            f"base_revenue is required and must be positive, "
            f"got {base_revenue}."
        )
    if wacc is None or wacc <= 0:
        raise ValueError(
            f"wacc is required and must be positive, got {wacc}."
        )
    if terminal_growth_rate >= wacc:
        raise ValueError(
            f"terminal_growth_rate ({terminal_growth_rate:.2%}) must be "
            f"less than wacc ({wacc:.2%}). Otherwise terminal value "
            f"formula produces infinity -- the math breaks down."
        )
    if len(revenue_growth_rates) != 5:
        raise ValueError(
            f"Need exactly 5 annual growth rates, "
            f"got {len(revenue_growth_rates)}."
        )

    # ── APPLY DEFAULTS (Tiered NA Handling) ───────────────────────
    warnings = []

    ebitda_margin = _apply_defaults(ebitda_margin, "ebitda_margin", warnings)
    da_margin = _apply_defaults(da_margin, "da_margin", warnings)
    tax_rate = _apply_defaults(tax_rate, "tax_rate", warnings)
    capex_margin = _apply_defaults(capex_margin, "capex_margin", warnings)
    wc_change_margin = _apply_defaults(
        wc_change_margin, "wc_change_margin", warnings
    )

    # RONIC defaults to WACC (conservative: new capital earns
    # exactly its cost, creating no excess value).
    if ronic is None:
        ronic = wacc
        warnings.append(
            f"WARNING: RONIC not provided. Defaulted to WACC ({wacc:.2%}). "
            f"This is conservative -- assumes new invested capital earns "
            f"exactly its cost. For optimistic case, use sector ROE from "
            f"Damodaran roeIndia dataset."
        )

    # ─────────────────────────────────────────────────────────────
    # STEP 1: BUILD 5-YEAR P&L AND FCF PROJECTION
    # ─────────────────────────────────────────────────────────────
    # Each year we calculate:
    #   Revenue = Prior Revenue * (1 + growth_rate)
    #   EBITDA  = Revenue * ebitda_margin
    #   D&A     = Revenue * da_margin
    #   EBIT    = EBITDA - D&A
    #   NOPLAT  = EBIT * (1 - tax_rate)
    #   FCF     = NOPLAT + D&A - Capex - delta_WC
    #
    # Excel equivalents (assuming Year 1 starts in column C):
    #   C2 (Revenue)  = B2 * (1 + C1)     where C1 = growth rate
    #   C3 (EBITDA)   = C2 * $margin
    #   C4 (D&A)      = C2 * $da_margin
    #   C5 (EBIT)     = C3 - C4
    #   C6 (NOPLAT)   = C5 * (1 - $tax)
    #   C7 (Capex)    = C2 * $capex_margin
    #   C8 (delta_WC) = C2 * $wc_margin
    #   C9 (FCF)      = C6 + C4 - C7 - C8
    #
    # Source: McKinsey Valuation 6th Ed., Ch.3 p.192

    projections = {}
    revenue = base_revenue

    for year in range(1, 6):
        # Year index is 0-based in the growth_rates list
        growth = revenue_growth_rates[year - 1]

        revenue = revenue * (1 + growth)
        ebitda = revenue * ebitda_margin
        da = revenue * da_margin
        ebit = ebitda - da
        noplat = ebit * (1 - tax_rate)
        capex = revenue * capex_margin
        delta_wc = revenue * wc_change_margin
        fcf = noplat + da - capex - delta_wc

        projections[year] = {
            "revenue_cr": round(revenue, 2),
            "ebitda_cr": round(ebitda, 2),
            "da_cr": round(da, 2),
            "ebit_cr": round(ebit, 2),
            "noplat_cr": round(noplat, 2),
            "capex_cr": round(capex, 2),
            "delta_wc_cr": round(delta_wc, 2),
            "fcf_cr": round(fcf, 2),
            "growth_rate": growth,
        }

    # Save Year 5 values for terminal value calculation
    noplat_yr5 = projections[5]["noplat_cr"]
    fcf_yr5 = projections[5]["fcf_cr"]
    ebitda_yr1 = projections[1]["ebitda_cr"]

    # ─────────────────────────────────────────────────────────────
    # STEP 2: TERMINAL VALUE (Dual Method)
    # ─────────────────────────────────────────────────────────────

    # METHOD A: McKinsey Value Driver Formula
    # TV = NOPLAT_yr5 * (1 - g/RONIC) / (WACC - g)
    #
    # What (1 - g/RONIC) means: this is the "reinvestment factor."
    # If the company grows at g and earns RONIC on new capital,
    # it must reinvest (g/RONIC) fraction of NOPLAT to fund growth.
    # The rest is distributable to investors.
    #
    # Excel: = NOPLAT_yr5 * (1 - g/RONIC) / (WACC - g)
    # Source: McKinsey Valuation 6th Ed., Ch.3 p.214

    reinvestment_rate = terminal_growth_rate / ronic
    tv_value_driver = noplat_yr5 * (1 - reinvestment_rate) / (
        wacc - terminal_growth_rate
    )

    # METHOD B: Gordon Growth Model (Cross-check)
    # TV = FCF_yr5 * (1 + g) / (WACC - g)
    #
    # Simpler formula that assumes FCF grows at g forever.
    # Source: Damodaran, Investment Valuation 3rd Ed., Ch.12

    tv_gordon = fcf_yr5 * (1 + terminal_growth_rate) / (
        wacc - terminal_growth_rate
    )

    # DIVERGENCE CHECK: Flag if the two TV estimates differ > 20%
    # This would mean our reinvestment assumptions are inconsistent
    # with our FCF projection -- a model integrity issue.
    if tv_gordon != 0:
        tv_divergence_pct = abs(tv_value_driver - tv_gordon) / abs(tv_gordon)
    else:
        tv_divergence_pct = 0.0
    divergence_flag = tv_divergence_pct > 0.20

    # Use Value Driver as primary (McKinsey preferred method)
    terminal_value = tv_value_driver

    # ─────────────────────────────────────────────────────────────
    # STEP 3: DISCOUNT ALL CASH FLOWS TO PRESENT VALUE
    # ─────────────────────────────────────────────────────────────
    # PV = Future Value / (1 + WACC)^year
    #
    # Excel: = FCF / (1+WACC)^year   i.e.  =C9/(1.13)^1
    # Source: McKinsey Ch.3, Damodaran Ch.12

    sum_pv_fcf = 0.0
    for year in range(1, 6):
        discount_factor = 1 / ((1 + wacc) ** year)
        pv_fcf = projections[year]["fcf_cr"] * discount_factor
        projections[year]["discount_factor"] = round(discount_factor, 6)
        projections[year]["pv_fcf_cr"] = round(pv_fcf, 2)
        sum_pv_fcf += pv_fcf

    # Discount terminal value back to present (it sits at end of Year 5)
    pv_terminal = terminal_value / ((1 + wacc) ** 5)

    # Enterprise Value = Sum of PV(FCFs) + PV(Terminal Value)
    enterprise_value = sum_pv_fcf + pv_terminal

    # Equity Value = EV - Net Debt
    equity_value = enterprise_value - net_debt

    # TV as percentage of EV -- flag if > 75%
    tv_pct_of_ev = (pv_terminal / enterprise_value) * 100 if enterprise_value > 0 else 0
    tv_heavy_flag = tv_pct_of_ev > 75

    # Implied EV/EBITDA (for cross-check against comparable_company.py)
    # = Enterprise Value / Year 1 EBITDA (NTM convention)
    implied_ev_ebitda = enterprise_value / ebitda_yr1 if ebitda_yr1 > 0 else None

    # ─────────────────────────────────────────────────────────────
    # STEP 4: SENSITIVITY TABLE (3x3)
    # ─────────────────────────────────────────────────────────────
    # Vary WACC +/-1% and terminal growth +/-0.5%
    # For each combo, recalculate TV and discount, keep FCFs same.
    #
    # Source: Rosenbaum & Pearl Ch.4, standard stress ranges.

    wacc_scenarios = [
        round(wacc - 0.01, 4),
        round(wacc, 4),
        round(wacc + 0.01, 4),
    ]
    tgr_scenarios = [
        round(terminal_growth_rate - 0.005, 4),
        round(terminal_growth_rate, 4),
        round(terminal_growth_rate + 0.005, 4),
    ]

    sensitivity_table = {}
    for w in wacc_scenarios:
        wacc_label = f"wacc_{w:.1%}"
        sensitivity_table[wacc_label] = {}
        for g in tgr_scenarios:
            tgr_label = f"tgr_{g:.1%}"

            # Guard: g must be < w for the formula to work
            if g >= w:
                sensitivity_table[wacc_label][tgr_label] = "N/A (g >= WACC)"
                continue

            # Recalculate TV with this combo
            sens_tv = noplat_yr5 * (1 - g / ronic) / (w - g)
            # Recalculate PV of TV
            sens_pv_tv = sens_tv / ((1 + w) ** 5)
            # Recalculate PV of FCFs with new WACC
            sens_pv_fcf = 0.0
            for yr in range(1, 6):
                sens_pv_fcf += projections[yr]["fcf_cr"] / ((1 + w) ** yr)
            # EV for this scenario
            sens_ev = sens_pv_fcf + sens_pv_tv
            sensitivity_table[wacc_label][tgr_label] = round(sens_ev, 2)

    # ─────────────────────────────────────────────────────────────
    # STEP 5: DETERMINE DATA QUALITY / CONFIDENCE
    # ─────────────────────────────────────────────────────────────

    if len(warnings) == 0:
        confidence = "HIGH"
    elif len(warnings) <= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if tv_heavy_flag:
        warnings.append(
            f"WARNING: Terminal Value represents {tv_pct_of_ev:.1f}% of "
            f"Enterprise Value. Values above 75% indicate heavy reliance "
            f"on long-term assumptions. Stress-test terminal growth rate "
            f"and WACC carefully."
        )
    if divergence_flag:
        warnings.append(
            f"WARNING: Terminal Value methods diverge by "
            f"{tv_divergence_pct:.1%}. Value Driver: {tv_value_driver:.2f} Cr "
            f"vs Gordon Growth: {tv_gordon:.2f} Cr. Review reinvestment "
            f"assumptions for consistency."
        )

    # ─────────────────────────────────────────────────────────────
    # STEP 6: ASSEMBLE OUTPUT
    # ─────────────────────────────────────────────────────────────

    result = {
        "projections": projections,

        "terminal_value": {
            "value_driver_formula_cr": round(tv_value_driver, 2),
            "gordon_growth_model_cr": round(tv_gordon, 2),
            "divergence_pct": round(tv_divergence_pct * 100, 1),
            "divergence_flag": divergence_flag,
            "pv_of_tv_cr": round(pv_terminal, 2),
            "tv_as_pct_of_ev": round(tv_pct_of_ev, 1),
            "tv_heavy_flag": tv_heavy_flag,
        },

        "valuation": {
            "sum_of_pv_fcfs_cr": round(sum_pv_fcf, 2),
            "enterprise_value_cr": round(enterprise_value, 2),
            "equity_value_cr": round(equity_value, 2),
            "implied_ev_ebitda": (
                round(implied_ev_ebitda, 2) if implied_ev_ebitda else None
            ),
        },

        "sensitivity_table": sensitivity_table,

        "data_quality": {
            "inputs_defaulted": [
                w.split(".")[0] for w in warnings
                if w.startswith("WARNING:")
                and "not provided" in w
            ],
            "warnings": warnings,
            "confidence": confidence,
        },

        "methodology_sources": {
            "fcf_formula": (
                "McKinsey Valuation 6th Ed., Chapter 3, p.192. "
                "FCF = NOPLAT + D&A - Capex - delta_NWC. "
                "NOPLAT = EBIT * (1 - Tax Rate)."
            ),
            "terminal_value": (
                "McKinsey Valuation 6th Ed., Chapter 3, p.214. "
                "Value Driver Formula: "
                "TV = NOPLAT*(1-g/RONIC)/(WACC-g). "
                "Conservative: RONIC defaults to WACC when sector "
                "data unavailable."
            ),
            "cross_check": (
                "Gordon Growth Model -- Damodaran, Investment "
                "Valuation 3rd Ed., Ch.12. "
                "TV = FCF*(1+g)/(WACC-g). "
                "Divergence > 20% flags model integrity issue."
            ),
            "sensitivity": (
                "Rosenbaum & Pearl, Investment Banking, Ch.4. "
                "Standard stress ranges: WACC +/-1%, "
                "terminal growth +/-0.5%."
            ),
        },

        "inputs_used": {
            "base_revenue_cr": base_revenue,
            "revenue_growth_rates": revenue_growth_rates,
            "ebitda_margin": ebitda_margin,
            "da_margin": da_margin,
            "tax_rate": tax_rate,
            "capex_margin": capex_margin,
            "wc_change_margin": wc_change_margin,
            "wacc": wacc,
            "terminal_growth_rate": terminal_growth_rate,
            "ronic": ronic,
            "net_debt_cr": net_debt,
        },
    }

    return result


# =====================================================================
# TEST SECTION
# =====================================================================
# Run: py -m project_veritas.tools.dcf_engine

if __name__ == "__main__":

    result = calculate_dcf(
        base_revenue=45,
        revenue_growth_rates=[0.22, 0.20, 0.17, 0.14, 0.11],
        ebitda_margin=0.30,
        da_margin=0.05,
        tax_rate=0.25,
        capex_margin=0.06,
        wc_change_margin=0.02,
        wacc=0.13,
        terminal_growth_rate=0.05,
        net_debt=25,
    )

    # ── Year-by-Year Projection Table ──
    print("=" * 75)
    print("  PROJECT VERITAS -- DCF VALUATION ENGINE")
    print("=" * 75)

    print("\n--- 5-YEAR FCF PROJECTION (all values in Cr) ---\n")
    header = (
        f"{'Year':>5} | {'Revenue':>10} | {'EBITDA':>10} | "
        f"{'NOPLAT':>10} | {'FCF':>10} | {'PV(FCF)':>10}"
    )
    print(header)
    print("-" * len(header))
    for yr in range(1, 6):
        p = result["projections"][yr]
        print(
            f"{yr:>5} | {p['revenue_cr']:>10.2f} | {p['ebitda_cr']:>10.2f} | "
            f"{p['noplat_cr']:>10.2f} | {p['fcf_cr']:>10.2f} | "
            f"{p['pv_fcf_cr']:>10.2f}"
        )

    # ── Terminal Value ──
    tv = result["terminal_value"]
    print(f"\n--- TERMINAL VALUE ---")
    print(f"  Value Driver Formula:  {tv['value_driver_formula_cr']:>10.2f} Cr")
    print(f"  Gordon Growth Model:   {tv['gordon_growth_model_cr']:>10.2f} Cr")
    print(f"  Divergence:            {tv['divergence_pct']:>9.1f}%"
          f"  {'** FLAGGED **' if tv['divergence_flag'] else '(OK)'}")
    print(f"  PV of Terminal Value:  {tv['pv_of_tv_cr']:>10.2f} Cr")
    print(f"  TV as % of EV:         {tv['tv_as_pct_of_ev']:>9.1f}%"
          f"  {'** TV-HEAVY **' if tv['tv_heavy_flag'] else '(OK)'}")

    # ── Valuation Summary ──
    v = result["valuation"]
    print(f"\n--- VALUATION SUMMARY ---")
    print(f"  Sum of PV(FCFs):       {v['sum_of_pv_fcfs_cr']:>10.2f} Cr")
    print(f"  + PV(Terminal Value):  {tv['pv_of_tv_cr']:>10.2f} Cr")
    print(f"  = Enterprise Value:    {v['enterprise_value_cr']:>10.2f} Cr")
    print(f"  - Net Debt:            {result['inputs_used']['net_debt_cr']:>10.2f} Cr")
    print(f"  = Equity Value:        {v['equity_value_cr']:>10.2f} Cr")
    print(f"  Implied EV/EBITDA:     {v['implied_ev_ebitda']:>10.2f}x"
          f"  (vs Comps median: 12.0x)")

    # ── Sensitivity Table ──
    print(f"\n--- SENSITIVITY TABLE: Enterprise Value (Cr) ---")
    print(f"{'':>15}", end="")
    tgr_keys = list(list(result["sensitivity_table"].values())[0].keys())
    for tgr in tgr_keys:
        print(f" | {tgr:>12}", end="")
    print()
    print("-" * 60)
    for wacc_label, tgr_dict in result["sensitivity_table"].items():
        print(f"{wacc_label:>15}", end="")
        for val in tgr_dict.values():
            if isinstance(val, str):
                print(f" | {val:>12}", end="")
            else:
                print(f" | {val:>12.2f}", end="")
        print()

    # ── Warnings ──
    if result["data_quality"]["warnings"]:
        print(f"\n--- DATA QUALITY WARNINGS ---")
        for w in result["data_quality"]["warnings"]:
            print(f"  {w}")
    print(f"\n  Confidence: {result['data_quality']['confidence']}")
    print("=" * 75)
