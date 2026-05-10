# project_veritas/tools/comparable_company.py
# ─────────────────────────────────────────────────────────────────────
# COMPARABLE COMPANY ANALYSIS ENGINE
#
# Methodology: Rosenbaum & Pearl, "Investment Banking: Valuation,
#              Leveraged Buyouts, and Mergers & Acquisitions"
#              Chapter 3 — Comparable Company Analysis (pp. 130-175)
#
# This tool takes a target company's financials and a set of peer
# companies' trading multiples, then calculates an implied valuation
# range using the 25th percentile / median / 75th percentile approach.
# ─────────────────────────────────────────────────────────────────────


# =====================================================================
# IMPORTS — Loading external libraries we need
# =====================================================================
# "import" is Python's way of saying "go get this tool from the toolbox."
# We're importing two specific functions from the "statistics" library,
# which comes built into Python (no separate install needed).

from statistics import median, quantiles


# =====================================================================
# HELPER FUNCTION: calculate_percentiles
# =====================================================================
# A "function" is a reusable block of code. You define it once, then
# call it whenever you need it — like a formula in Excel that you can
# reference from multiple cells.
#
# This helper takes a list of numbers and returns the 25th percentile,
# median (50th), and 75th percentile.
#
# Excel equivalent:
#   25th percentile = PERCENTILE(range, 0.25)
#   Median          = MEDIAN(range)
#   75th percentile = PERCENTILE(range, 0.75)

def calculate_percentiles(values):
    """
    Given a list of numbers, return (p25, p50, p75).

    Parameters
    ----------
    values : list of float
        The multiples from the peer set (e.g., [9.0, 11.0, 13.0, 14.0])

    Returns
    -------
    tuple of (float, float, float)
        (25th percentile, median, 75th percentile)

    Methodology Source
    ------------------
    Rosenbaum & Pearl, Investment Banking, Chapter 3, p.142:
    "The banker typically presents the 25th percentile, median, and
     75th percentile to frame the valuation range."
    """

    # Step 1: Sort the list from smallest to largest.
    # Why? Percentiles only make sense on ordered data.
    # Excel equivalent: This is like sorting a column A-Z before
    # using PERCENTILE().
    sorted_values = sorted(values)

    # Step 2: Calculate the median (50th percentile).
    # The median is the middle value when data is sorted.
    # If 4 values: average of the 2nd and 3rd.
    # Excel equivalent: =MEDIAN(A1:A4)
    p50 = median(sorted_values)

    # Step 3: Calculate 25th and 75th percentiles.
    # quantiles() splits data into equal-probability intervals.
    # n=4 means "split into 4 quarters" (quartiles).
    # This gives us 3 cut points: [Q1, Q2, Q3] = [25th, 50th, 75th]
    # Excel equivalent: =QUARTILE(A1:A4, 1) and =QUARTILE(A1:A4, 3)
    quartile_cuts = quantiles(sorted_values, n=4)

    # quartile_cuts is a list of 3 numbers: [Q1, Q2, Q3]
    # Index 0 = Q1 (25th percentile)
    # Index 2 = Q3 (75th percentile)
    # (We don't use index 1 because we already calculated median above,
    #  and our median function handles even-count lists more precisely.)
    p25 = quartile_cuts[0]
    p75 = quartile_cuts[2]

    # Step 4: Return all three values as a "tuple" — a fixed group of
    # values that travel together, like a row in Excel.
    return (p25, p50, p75)


# =====================================================================
# HELPER FUNCTION: determine_confidence
# =====================================================================
# How confident are we in the valuation? Depends on how many peers
# we have. More peers = more data points = tighter, more reliable range.
#
# This is not a formula from any textbook — it's a practical heuristic
# (rule of thumb) that any PE analyst would apply intuitively:
#   - 1-2 peers: You're basically guessing. LOW confidence.
#   - 3-4 peers: Decent but thin. MEDIUM confidence.
#   - 5+ peers:  Solid comp set. HIGH confidence.

def determine_confidence(peer_count):
    """
    Return a confidence level based on the number of comparable peers.

    Parameters
    ----------
    peer_count : int
        How many companies are in the peer set.

    Returns
    -------
    str
        "HIGH", "MEDIUM", or "LOW"
    """

    # "if / elif / else" is Python's way of making decisions.
    # It's like a nested IF() in Excel:
    # =IF(peer_count >= 5, "HIGH", IF(peer_count >= 3, "MEDIUM", "LOW"))

    if peer_count >= 5:
        return "HIGH"
    elif peer_count >= 3:
        return "MEDIUM"
    else:
        return "LOW"


# =====================================================================
# HELPER FUNCTION: determine_primary_method
# =====================================================================
# When you have both EV/EBITDA and EV/Revenue valuations, which one
# should you trust more? This function makes that judgment.
#
# Rule of thumb from Rosenbaum & Pearl and Damodaran:
#   - EV/EBITDA is preferred for profitable, mature companies because
#     EBITDA reflects actual operating performance.
#   - EV/Revenue is the fallback for unprofitable or early-stage
#     companies where EBITDA is negative or volatile.
#   - If EBITDA is very low relative to revenue (margin < 10%),
#     EV/Revenue may be more stable.

def determine_primary_method(target_ebitda, target_revenue):
    """
    Decide which valuation multiple is more reliable for this target.

    Parameters
    ----------
    target_ebitda : float
        Target company's EBITDA (in crores)
    target_revenue : float
        Target company's Revenue (in crores)

    Returns
    -------
    str
        Explanation of which method is primary and why.
    """

    # Guard: If EBITDA is zero or negative, the company is unprofitable.
    # EV/EBITDA would produce meaningless or negative values.
    # Excel analogy: =IF(EBITDA <= 0, "use revenue", ...)
    if target_ebitda <= 0:
        return (
            "EV/Revenue is the primary method. "
            "Rationale: Target EBITDA is zero or negative, making "
            "EV/EBITDA inapplicable. Per Damodaran (Investment Valuation, "
            "Ch. 18), revenue multiples are appropriate for unprofitable "
            "or early-stage companies."
        )

    # Calculate EBITDA margin = EBITDA / Revenue
    # This tells us how profitable the company is.
    # Excel: =EBITDA/Revenue
    ebitda_margin = target_ebitda / target_revenue

    # If margin is below 10%, EBITDA is thin and volatile.
    # Small changes in costs swing EBITDA wildly, making EV/EBITDA
    # unreliable. Revenue is more stable in this case.
    if ebitda_margin < 0.10:
        return (
            "EV/Revenue is the primary method. "
            f"Rationale: Target EBITDA margin is {ebitda_margin:.1%}, "
            "which is below 10%. Thin margins make EV/EBITDA volatile. "
            "Per Rosenbaum & Pearl (Ch. 3, p.148), revenue multiples "
            "provide a more stable basis when margins are compressed."
        )

    # If we get here, EBITDA is positive and margin is healthy.
    # EV/EBITDA is the gold standard.
    return (
        "EV/EBITDA is the primary method. "
        f"Rationale: Target EBITDA margin is {ebitda_margin:.1%}, "
        "indicating healthy profitability. Per Rosenbaum & Pearl "
        "(Ch. 3, p.145), EV/EBITDA is the most widely used metric "
        "in comparable company analysis as it is capital structure "
        "neutral and not affected by depreciation policy differences."
    )


# =====================================================================
# MAIN FUNCTION: run_comparable_analysis
# =====================================================================
# This is the main engine. It takes in the target's financials and
# the peer set, runs all the math, and returns a structured result
# dictionary with full source citations.
#
# Think of this as the "final output sheet" in an Excel model — the
# one you'd print and put in front of the Investment Committee.

def run_comparable_analysis(target_ebitda, target_revenue,
                            target_net_debt, peers):
    """
    Run a full Comparable Company Analysis on the target.

    Parameters
    ----------
    target_ebitda : float
        Target company's EBITDA in crores (₹ Cr).
    target_revenue : float
        Target company's Revenue in crores (₹ Cr).
    target_net_debt : float
        Target company's Net Debt in crores (₹ Cr).
        Net Debt = Total Debt - Cash.
        If the company has more cash than debt, this is negative.
    peers : list of dict
        Each peer is a dictionary with keys:
            "name"       : str   — Peer company name
            "ev_ebitda"  : float — Peer's EV/EBITDA multiple
            "ev_revenue" : float — Peer's EV/Revenue multiple

    Returns
    -------
    dict
        Structured valuation output with ranges, methodology citations,
        and confidence level.

    Example
    -------
    >>> result = run_comparable_analysis(
    ...     target_ebitda=13.5,
    ...     target_revenue=45.0,
    ...     target_net_debt=25.0,
    ...     peers=[
    ...         {"name": "Taj Madikeri",  "ev_ebitda": 14.0, "ev_revenue": 3.2},
    ...         {"name": "Royal Orchid",  "ev_ebitda": 11.0, "ev_revenue": 2.1},
    ...         {"name": "Advani Hotels", "ev_ebitda":  9.0, "ev_revenue": 1.8},
    ...         {"name": "CGH Earth",     "ev_ebitda": 13.0, "ev_revenue": 2.8},
    ...     ]
    ... )

    Methodology Source
    ------------------
    Rosenbaum & Pearl, "Investment Banking: Valuation, Leveraged Buyouts,
    and Mergers & Acquisitions," Chapter 3 — Comparable Company Analysis.
    Percentile-based range approach per pp. 142-148.
    """

    # ─────────────────────────────────────────────────────────────
    # STEP 1: INPUT VALIDATION
    # ─────────────────────────────────────────────────────────────
    # Before doing any math, check that the inputs make sense.
    # This is like data validation in Excel (Data → Validation).
    # If someone accidentally passes garbage, we want a clear error
    # message — not a mysterious crash later.

    # Check: Do we have at least 2 peers?
    # You can't calculate a percentile range from 1 data point.
    if len(peers) < 2:
        raise ValueError(
            f"Need at least 2 peers for comparable analysis, "
            f"got {len(peers)}. A single data point cannot produce "
            f"a meaningful valuation range."
        )

    # Check: Is revenue positive?
    # A company with zero or negative revenue doesn't make sense
    # for a multiples-based valuation.
    if target_revenue <= 0:
        raise ValueError(
            f"Target revenue must be positive, got {target_revenue}. "
            f"Revenue multiples require positive revenue."
        )

    # ─────────────────────────────────────────────────────────────
    # STEP 2: EXTRACT MULTIPLES FROM PEER SET
    # ─────────────────────────────────────────────────────────────
    # Pull out the EV/EBITDA and EV/Revenue numbers from each peer
    # into separate lists. This is like copying a column from a
    # table into its own range for analysis.
    #
    # Python "list comprehension" — reads like English:
    #   "For each peer in the peers list, grab their ev_ebitda value"
    #
    # Excel equivalent:
    #   If peers are in rows 2-5 and EV/EBITDA is column C:
    #   ev_ebitda_multiples = {C2, C3, C4, C5}

    ev_ebitda_multiples = [peer["ev_ebitda"] for peer in peers]
    ev_revenue_multiples = [peer["ev_revenue"] for peer in peers]

    # Also grab the peer names for documentation
    peer_names = [peer["name"] for peer in peers]

    # ─────────────────────────────────────────────────────────────
    # STEP 3: CALCULATE PERCENTILE RANGES FOR EACH MULTIPLE
    # ─────────────────────────────────────────────────────────────
    # Call our helper function to get 25th, 50th, 75th percentile
    # for each set of multiples.

    ebitda_p25, ebitda_p50, ebitda_p75 = calculate_percentiles(
        ev_ebitda_multiples
    )
    revenue_p25, revenue_p50, revenue_p75 = calculate_percentiles(
        ev_revenue_multiples
    )

    # ─────────────────────────────────────────────────────────────
    # STEP 4: CALCULATE IMPLIED ENTERPRISE VALUES
    # ─────────────────────────────────────────────────────────────
    # The core formula:
    #   Implied EV = Target's Financial Metric × Peer Multiple
    #
    # For EV/EBITDA:
    #   Implied EV = Target EBITDA × EV/EBITDA multiple
    #   Excel: =B2*C2  (where B2=EBITDA, C2=multiple)
    #
    # For EV/Revenue:
    #   Implied EV = Target Revenue × EV/Revenue multiple
    #   Excel: =B3*D2  (where B3=Revenue, D2=multiple)
    #
    # We do this at each percentile to get low/mid/high.

    ev_by_ebitda_low = target_ebitda * ebitda_p25
    ev_by_ebitda_mid = target_ebitda * ebitda_p50
    ev_by_ebitda_high = target_ebitda * ebitda_p75

    ev_by_revenue_low = target_revenue * revenue_p25
    ev_by_revenue_mid = target_revenue * revenue_p50
    ev_by_revenue_high = target_revenue * revenue_p75

    # ─────────────────────────────────────────────────────────────
    # STEP 5: BRIDGE FROM EV TO EQUITY VALUE
    # ─────────────────────────────────────────────────────────────
    # Equity Value = Enterprise Value - Net Debt
    #
    # This is the "equity bridge" — converting what the whole
    # business is worth into what the equity holders' share is worth.
    #
    # Excel: =EV - Net_Debt
    #
    # We take the LOWEST implied EV from BOTH methods as the floor,
    # the average of the two medians as the midpoint, and the
    # HIGHEST implied EV from BOTH methods as the ceiling.
    # This gives the widest defensible range across both approaches.

    equity_low = min(ev_by_ebitda_low, ev_by_revenue_low) - target_net_debt
    equity_mid = (
        (ev_by_ebitda_mid + ev_by_revenue_mid) / 2
    ) - target_net_debt
    equity_high = max(ev_by_ebitda_high, ev_by_revenue_high) - target_net_debt

    # ─────────────────────────────────────────────────────────────
    # STEP 6: DETERMINE CONFIDENCE AND PRIMARY METHOD
    # ─────────────────────────────────────────────────────────────

    confidence = determine_confidence(len(peers))
    primary_method = determine_primary_method(target_ebitda, target_revenue)

    # ─────────────────────────────────────────────────────────────
    # STEP 7: ASSEMBLE THE FINAL OUTPUT DICTIONARY
    # ─────────────────────────────────────────────────────────────
    # A "dictionary" in Python is like a structured form — each
    # piece of data has a label (key) and a value.
    # Think of it as a JSON object or a named range in Excel.
    #
    # round(x, 2) rounds to 2 decimal places, like setting
    # cell format to "Number, 2 decimal places" in Excel.

    result = {

        # ── EV/EBITDA Valuation Range ──
        "ev_ebitda_range": {
            "low_cr": round(ev_by_ebitda_low, 2),
            "mid_cr": round(ev_by_ebitda_mid, 2),
            "high_cr": round(ev_by_ebitda_high, 2),
            "multiples_used": {
                "p25": round(ebitda_p25, 2),
                "median": round(ebitda_p50, 2),
                "p75": round(ebitda_p75, 2),
            },
            "peer_set": peer_names,
            "formula": "Implied EV = Target EBITDA × EV/EBITDA Multiple",
            "methodology_source": (
                "Rosenbaum & Pearl, Investment Banking: Valuation, "
                "Leveraged Buyouts, and Mergers & Acquisitions, "
                "Chapter 3 — Comparable Company Analysis. "
                "Formula: EV = EBITDA × EV/EBITDA Multiple. "
                "Percentile approach (25th/median/75th) per pp. 142-148."
            ),
        },

        # ── EV/Revenue Valuation Range ──
        "ev_revenue_range": {
            "low_cr": round(ev_by_revenue_low, 2),
            "mid_cr": round(ev_by_revenue_mid, 2),
            "high_cr": round(ev_by_revenue_high, 2),
            "multiples_used": {
                "p25": round(revenue_p25, 2),
                "median": round(revenue_p50, 2),
                "p75": round(revenue_p75, 2),
            },
            "peer_set": peer_names,
            "formula": "Implied EV = Target Revenue × EV/Revenue Multiple",
            "methodology_source": (
                "Rosenbaum & Pearl, Investment Banking: Valuation, "
                "Leveraged Buyouts, and Mergers & Acquisitions, "
                "Chapter 3 — Comparable Company Analysis. "
                "Formula: EV = Revenue × EV/Revenue Multiple. "
                "Percentile approach (25th/median/75th) per pp. 142-148. "
                "Revenue multiples per Damodaran, Investment Valuation, "
                "Chapter 18 — Revenue Multiples and Value."
            ),
        },

        # ── Equity Value Range (the "buyer's check size") ──
        "equity_value_range": {
            "low_cr": round(equity_low, 2),
            "mid_cr": round(equity_mid, 2),
            "high_cr": round(equity_high, 2),
            "formula": "Equity Value = Enterprise Value − Net Debt",
            "net_debt_used_cr": target_net_debt,
            "methodology_source": (
                "Rosenbaum & Pearl, Investment Banking, Chapter 3, "
                "p.155 — Equity Value Bridge. "
                "Formula: Equity Value = Enterprise Value − Net Debt. "
                "Net Debt = Total Debt − Cash & Cash Equivalents."
            ),
        },

        # ── Analytical Judgments ──
        "primary_method": primary_method,
        "confidence": confidence,

        # ── Input Summary (for audit trail) ──
        "inputs_used": {
            "target_ebitda_cr": target_ebitda,
            "target_revenue_cr": target_revenue,
            "target_net_debt_cr": target_net_debt,
            "peer_count": len(peers),
            "peers": peers,
        },
    }

    return result


# =====================================================================
# TEST SECTION — Run this to see the engine in action
# =====================================================================
# To run this test:
#   1. Open a terminal (Command Prompt or PowerShell)
#   2. Navigate to the Project_Veritas folder
#   3. Type: python -m project_veritas.tools.comparable_company
#   4. Press Enter
#
# The "if __name__ == '__main__':" block below is a Python convention.
# It means: "Only run this code if I'm running THIS file directly.
# If another file imports me, skip this part."
#
# Analogy: It's like a sheet in Excel that has both formulas AND a
# test area. The test area only activates when you open that specific
# sheet, not when another sheet references its formulas.

if __name__ == "__main__":

    # ── Define our test peer set (Indian luxury hospitality) ──
    test_peers = [
        {"name": "Taj Madikeri",  "ev_ebitda": 14.0, "ev_revenue": 3.2},
        {"name": "Royal Orchid",  "ev_ebitda": 11.0, "ev_revenue": 2.1},
        {"name": "Advani Hotels", "ev_ebitda":  9.0, "ev_revenue": 1.8},
        {"name": "CGH Earth",     "ev_ebitda": 13.0, "ev_revenue": 2.8},
    ]

    # ── Run the analysis ──
    result = run_comparable_analysis(
        target_ebitda=13.5,       # ₹13.5 Cr EBITDA
        target_revenue=45.0,      # ₹45 Cr Revenue
        target_net_debt=25.0,     # ₹25 Cr Net Debt
        peers=test_peers,
    )

    # ── Print the results in a readable format ──
    # We use Python's "json" module to print the dictionary nicely.
    # "indent=2" means each nested level is indented by 2 spaces.
    import json
    print("=" * 70)
    print("  PROJECT VERITAS — COMPARABLE COMPANY ANALYSIS")
    print("=" * 70)
    print(json.dumps(result, indent=2))
    print("=" * 70)

    # ── Quick summary for visual verification ──
    print("\n--- QUICK VERIFICATION SUMMARY ---")
    print(f"  EV/EBITDA Range: ₹{result['ev_ebitda_range']['low_cr']} Cr"
          f" — ₹{result['ev_ebitda_range']['high_cr']} Cr")
    print(f"  EV/Revenue Range: ₹{result['ev_revenue_range']['low_cr']} Cr"
          f" — ₹{result['ev_revenue_range']['high_cr']} Cr")
    print(f"  Equity Value Range: ₹{result['equity_value_range']['low_cr']} Cr"
          f" — ₹{result['equity_value_range']['high_cr']} Cr")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Primary Method: {result['primary_method'][:60]}...")
