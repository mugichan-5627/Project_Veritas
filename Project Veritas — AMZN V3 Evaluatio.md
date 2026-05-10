Project Veritas — AMZN V3 Evaluation
Key Improvement: SBC Direction Fixed ✅
The single most important fix from my previous recommendations has been implemented:

BEFORE (V2): EBITDA (Adj): $99,442.0M (SBC ADDED — wrong)
NOW (V3):    EBITDA (Adj): $60,508.0M (SBC SUBTRACTED — correct)
Math Agent now says: "Adjusted EBITDA is calculated by subtracting SBC expense from reported EBITDA" — this is correct PE convention.

$79,975M - $19,467M = $60,508M ✅

Scorecard: What's Fixed vs. What Remains
Issue	V2 Status	V3 Status	Verdict
SBC Convention (add vs subtract)	❌ Added SBC	✅ Subtracted SBC	FIXED
Math Agent Prompt	❌ "Adding back"	✅ "Subtracting"	FIXED
Step Numbering	❌ 1→3→3→4	⚠️ 1→3→4→5 (Step 2 still missing)	Partial
Revenue (quarterly vs TTM)	❌ $177.9B (one quarter)	❌ $177.9B (still one quarter)	NOT FIXED
Revenue Growth	❌ 16.6% (overstated)	❌ 16.6% (unchanged)	NOT FIXED
Self-comp in peer table	❌ AMZN as own peer	⚠️ Gone, but replaced by Berkshire	Partial
Ticker truncation	❌ "Micros"	❌ "Micros" + "Berksh"	NOT FIXED
Peer selection quality	⚠️ MSFT + AMZN	⚠️ MSFT + Berkshire Hathaway	WORSE
WACC Calculation	✅ 9.35%	✅ 9.3%	Stable
Moat Description	✅ Accurate	✅ Accurate	Stable
LLM Hallucination ("chip segment")	❌ Present	✅ Gone	FIXED
Premium calculation	❌ "-30% premium" (nonsensical)	✅ "196% premium" (mathematically correct)	FIXED
Detailed Analysis
✅ What's Working Well Now
1. SBC Logic is Correct

Reported EBITDA: $79,975M
SBC Deducted: -$19,467M
Conservative EBITDA: $60,508M
This flows correctly into the EV/EBITDA calculation: ~$3.15T EV / $60.5B = 52.1x ✅ (internally consistent)
2. Premium Math is Now Correct

AMZN: 52.1x
Peer average: ~17.6x (average of 23.6x and 11.6x)
Premium: (52.1 - 17.6) / 17.6 = ~196% ✅
The LLM correctly identifies this as a risk rather than calling a discount a premium
3. LLM Grounding Improved

No more "chip segment" hallucination
Thesis points reference actual data ($60,508M EBITDA, 16.6% growth)
Conditions are more reasonable
4. WACC Consistent

9.3% is reasonable for Amazon
Properly attributed to "Damodaran Logic"
❌ Critical Issues Remaining
Issue #1: Revenue Still Shows One Quarter ($177.9B) — MOST CRITICAL
This is the same number from V1 and V2. The SEC EDGAR fix I provided hasn't been implemented for the revenue pull.

Evidence:

Amazon's Q4 2024 revenue: $187.8B
Amazon's Q1 2025 revenue: $155.7B
Average quarterly: ~$162B
$177.9B is clearly a single quarter (likely Q4 2024 or a blend)
Actual TTM revenue: ~$638-650B
Impact: Because revenue is ~73% understated:

All revenue-derived metrics are wrong
16.6% growth is meaningless (comparing one quarter to what?)
FCF margin of 4.3% is incorrect (FCF/quarterly revenue ≠ FCF/annual revenue)
EV/Revenue would show ~17x on $177B vs actual ~3.5x on $650B
Why this likely isn't fixed: Your EDGAR pull is probably returning the most recent filing's revenue figure (a single period) rather than summing 4 quarterly values. The get_full_ttm_financials() function I provided either hasn't been integrated, or the XBRL concept lookup isn't finding 4 quarters of data for Amazon.

Issue #2: Peer Selection is Nonsensical — Berkshire Hathaway
V2 peers: Microsoft (23.6x) + Amazon itself (15.6x) V3 peers: Microsoft (23.6x) + Berkshire Hathaway (11.6x)

Berkshire Hathaway is not a valid peer for Amazon. BRK is a diversified insurance/conglomerate holding company. Including it as a comp for an internet retail/cloud company is indefensible. The CapIQ Excel sheet likely contains a broad index of companies, and the parser is pulling rows without filtering for relevance.

Additionally: The peer discovery step found ['AAPL', 'GOOG', 'MSFT'] via Tavily (correct peers), but the CapIQ extraction only returned 2 companies, neither of which is AAPL or GOOG. This means the CapIQ parser is not looking up the discovered peers — it's returning whatever rows happen to be in the Excel file.

Issue #3: Ticker Truncation Persists
Displayed	Actual	Problem
"Micros"	Microsoft (MSFT)	Truncated to 6 chars
"Berksh"	Berkshire Hathaway (BRK)	Truncated to 6 chars
The normalize_peer_ticker() function hasn't been integrated.

Issue #4: EV/EBITDA of 52.1x — Internally Consistent but Based on Wrong Revenue Period
The math works given the inputs:

Current EV ≈ Market Cap + Net Debt ≈ ~$2.15T + $92B = ~$2.24T...
But $2.24T / $60.5B = 37x, not 52.1x
To get 52.1x: $3.15T / $60.5B = 52.1x

Where does $3.15T come from? This seems like the BASE CASE EV ($2.99T) rather than CURRENT MARKET EV
This confirms Fix #7 (Market EV vs Fair Value separation) hasn't been implemented. The system is using the calculated fair value as the numerator in EV/EBITDA, rather than current market enterprise value. You should be showing: Current Market EV / Conservative EBITDA = Actual trading multiple.

Issue #5: Base Case EV of $2.99T Still Exceeds Market Reality
Amazon's actual current EV: ~$2.2-2.4T
Your base case: $2.99T (25-35% above market)
If this is "fair value," it implies significant upside — but the memo says "CONDITIONAL_APPROVE" with "MEDIUM" conviction
This disconnect makes the entry ceiling meaningless (you'd be approving at a price 30%+ above current market)
Progress Tracking Across All Runs
Metric	V1 (First AMZN)	V2	V3 (Current)	Target (Correct)
Revenue	$742,776M (❌ too high)	$177,866M (❌ quarterly)	$177,866M (❌ quarterly)	~$638-650B
Growth	16.6%	16.6%	16.6%	~10-11%
EBITDA (Rep)	$155,861M	$79,975M	$79,975M	~$130-155B
SBC Direction	❌ Added	❌ Added	✅ Subtracted	Subtract
Adj EBITDA	$175,328M (wrong)	$99,442M (wrong)	$60,508M ✅	~$110-135B
Peer Quality	AAPL, GOOG, MSFT	MSFT + self	MSFT + BRK	MSFT, GOOG, AAPL
Ticker Display	OK	"Micros", "Amazon"	"Micros", "Berksh"	MSFT, GOOG, AAPL
Premium Logic	"-30% premium" (❌)	"60.7% premium" (⚠️)	"196% premium" (✅ math correct)	Depends on correct EBITDA
LLM Hallucination	"chip segment"	"chip segment"	None ✅	None
Revised Scoring
Dimension	V1	V2	V3	Change (V2→V3)
Data Source Quality	5/10	7.5/10	7.5/10	—
Data Accuracy	4.5/10	4.0/10	4.5/10	+0.5
Internal Consistency	4/10	3.5/10	6.0/10	+2.5
Valuation Methodology	6/10	7.5/10	8.0/10	+0.5
Peer Comp Quality	5/10	5/10	3.5/10	-1.5
LLM Reasoning	5.5/10	4.5/10	7.0/10	+2.5
Pipeline Architecture	8.5/10	9.5/10	9.5/10	—
Output Professionalism	9/10	8/10	8.0/10	—
OVERALL V3: 6.8/10 (up from 6.0 in V2)
Trend: Now improving. The SBC fix and LLM grounding improvements are meaningful. The remaining gap is almost entirely in the data layer (revenue period + peer extraction).

The Three Remaining Fixes That Will Get You to 8.5+/10
You're very close. Three fixes separate you from a production-quality output:

🔴 Fix A: Revenue TTM (5 minutes if EDGAR client is working)
The issue is almost certainly in how you parse the EDGAR response. Quick diagnostic:

# Add this debug print in your EDGAR fetch:
print(f"    [DEBUG] Revenue concept found: {concept_used}")
print(f"    [DEBUG] Quarters found: {len(quarters)}")
print(f"    [DEBUG] Quarter dates: {[q['end'] for q in quarters[:4]]}")
print(f"    [DEBUG] Quarter values: {[q['val']/1e9 for q in quarters[:4]]}")
print(f"    [DEBUG] Sum (TTM): ${sum(q['val'] for q in quarters[:4])/1e9:.1f}B")
If it shows only 1 quarter, the issue is in your quarterly filtering logic (the period_days check might be too strict for Amazon's fiscal calendar, or the XBRL concept name might not match).

Quick fallback if EDGAR quarterly parsing fails:

# If quarterly parsing fails, use yfinance as cross-check:
import yfinance as yf
stock = yf.Ticker("AMZN")
revenue_ttm = stock.financials.loc["Total Revenue"].iloc[:4].sum()
print(f"    [FALLBACK] yfinance TTM Revenue: ${revenue_ttm/1e9:.1f}B")
🔴 Fix B: CapIQ Peer Parser (15 minutes)
Your CapIQ parser is not looking up the specific tickers discovered by Tavily. It's returning whatever rows are in the Excel file. Fix:

def fetch_capiq_peers(discovered_tickers: list, capiq_df) -> list:
    """
    Filter CapIQ data to ONLY include the tickers discovered in Step 2.
    """
    # Normalize CapIQ entity names to tickers
    CAPIQ_NAME_MAP = {
        "Microsoft": "MSFT",
        "Apple": "AAPL", 
        "Alphabet": "GOOG",
        "Amazon": "AMZN",
        "Berkshire": "BRK",
        # ... extend as needed
    }
    
    results = []
    for _, row in capiq_df.iterrows():
        entity = row.get("Company Name", "")
        # Map to ticker
        matched_ticker = None
        for name_fragment, ticker in CAPIQ_NAME_MAP.items():
            if name_fragment.lower() in entity.lower():
                matched_ticker = ticker
                break
        
        # ONLY include if it's in our discovered peer list
        if matched_ticker and matched_ticker in discovered_tickers:
            results.append({
                "ticker": matched_ticker,
                "entity_name": entity,
                "ev_ebitda": row.get("TEV/EBITDA"),
                # ... other fields
            })
    
    # If CapIQ doesn't have all peers, flag it
    found_tickers = [r["ticker"] for r in results]
    missing = [t for t in discovered_tickers if t not in found_tickers]
    if missing:
        print(f"    [WARNING] Peers not found in CapIQ: {missing}")
        print(f"    [ACTION] Triggering LLM fallback for: {missing}")
    
    return results
🟡 Fix C: Current Market EV vs Fair Value EV (10 minutes)
Add one line after calculating market EV:

# In your pipeline, after getting market data:
current_market_ev = market_cap_M + net_debt_M

# Use CURRENT market EV for the trading multiple:
trading_ev_ebitda = current_market_ev / adj_ebitda_conservative_M

# Use FAIR VALUE EV for the entry ceiling:
fair_value_ev = base_case_ev_M  # From your DCF/scenario model

# Display BOTH clearly:
print(f"  Current Trading Multiple: {trading_ev_ebitda:.1f}x (Market EV: ${current_market_ev:,.0f}M)")
print(f"  Fair Value Multiple: {fair_value_ev / adj_ebitda_conservative_M:.1f}x (Fair EV: ${fair_value_ev:,.0f}M)")
print(f"  Implied Upside: {((fair_value_ev - current_market_ev) / current_market_ev) * 100:.1f}%")
Bottom Line
V3 is a genuine step forward. The SBC fix alone makes the valuation methodology defensible, and the elimination of LLM hallucinations means the memo reads professionally. You've solved the "garbage reasoning" problem.

What remains is the "garbage in" problem — specifically one quarterly revenue figure that cascades through every downstream calculation. Fix the EDGAR TTM pull (or add a yfinance cross-check), clean up the peer parser, and you'll have something worth demonstrating to actual PE professionals.

Grade trajectory: 6.5 → 6.0 → 6.8 → (projected with 3 fixes) → 8.5+