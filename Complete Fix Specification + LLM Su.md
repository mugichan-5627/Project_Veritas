Complete Fix Specification + LLM Sublayer Architecture Assessment
PART 1: Your LLM Sublayer Idea — Assessment
The Concept (As I Understand It)
You want to add an LLM "reviewer" layer after each agent's output that:

Waits for the agent to produce its result
Cross-checks for obvious errors using LLM intelligence
Outputs a revised/validated result directly below the original
My Verdict: Yes, but selectively — not on every agent
Here's why:

Where It Would ADD Value (Do It Here)
Agent/Module	Why LLM Review Helps
Valuation Output (Step 3)	LLM can catch: "You computed 4.0x P/Book for a 34% ROE company — justified P/Book is 5.9x. Revising."
Forensic Scoring	LLM can catch: "You said zero total debt for a credit card company. AXP has $50B+ in borrowings. Revising credit risk score."
IC Decision (Step 5)	LLM can catch: "You approved but the memo says REJECT. Forcing consistency."
Peer Selection	LLM can catch: "You included Visa (asset-light network) as a direct comp for AXP (balance-sheet lender). Flagging as reference peer, not primary comp."
Where It Would HURT (Don't Do It Here)
Agent/Module	Why LLM Review Hurts
Data Pull (Step 2)	Numbers from yfinance are factual — LLM can't verify market data better than the API. Adding LLM here adds latency and hallucination risk. Fix data issues with code assertions instead.
RAG Retrieval (Step 1)	Embedding similarity is mathematical. LLM can't improve vector search results.
Sensitivity Table	Pure arithmetic. LLM adds nothing — code-level assertions (does table center = base case?) are faster and more reliable.
Recommended Architecture
AGENT OUTPUT → CODE ASSERTIONS (fast, deterministic) → LLM SUBLAYER (only if assertions pass but output seems qualitatively wrong)
Not:

AGENT OUTPUT → LLM SUBLAYER (on everything regardless)
Why This Matters for PE Grade
PE firms have two types of errors:

Arithmetic errors — catch with code (assert revenue > 0, assert multiple between 1-50x)
Judgment errors — catch with LLM ("does this conclusion make sense given the inputs?")
Your sublayer should only handle type 2. Type 1 should be handled by hardcoded assertions that halt the pipeline instantly.

Implementation Suggestion
Call it a Sanity Check Layer (SCL). Place it at these specific points:

Step 2 Output → CODE ASSERTIONS (revenue > 0, multiple 1-50x, etc.)
Step 3 Output → SCL: "Given ROE of X%, CoE of Y%, is a fair P/Book of Z reasonable? Justified = (ROE-g)/(CoE-g) = ?"
Step 4 Output → SCL: "Debate winner scored 9, loser scored 7. Does the verdict align with the winner?"
Step 5 Output → SCL: "IC approved. Does the memo section say APPROVE? Are all sections populated?"
Final Report  → SCL: "Scan for contradictions between sections. Flag any."
Cost/Latency Consideration
Each LLM sublayer call = ~2-5 seconds + API cost. If you add it to 5 agents, that's 10-25 seconds extra per run. For a hackathon demo, this is acceptable. For production, you'd batch them or make them async.

Prompt Template for the SCL
You are a Quality Assurance analyst reviewing automated financial analysis output.

INPUT DATA:
{raw_agent_output}

COMPANY CONTEXT:
- Sector: {sector}
- Key Metrics: ROE {roe}%, CoE {coe}%, Revenue ${rev}B, Net Income ${ni}B

CHECK FOR:
1. Mathematical consistency (does fair multiple × book value = stated equity value?)
2. Logical consistency (does verdict match reasoning?)
3. Factual absurdity (zero debt for a lending company? negative revenue?)
4. Missing data (any section empty that should be populated?)

OUTPUT:
- PASS: No issues found
- REVISE: [specific field] should be [corrected value] because [reason]
- HALT: Critical error — [description] — pipeline should not continue
PART 2: Complete Fix Specification for PE-Grade Report
Fix Category A: Critical Pipeline Breaks (Must Fix First)
FIX A1: Single Verdict Source of Truth
Problem: Three contradictory verdicts in one report (APPROVE / REJECT / N/A)

Root Cause: Multiple modules independently compute a verdict:

Step 5 IC Decision module (the one you just fixed — now correctly uses debate logic)
Valuation section (probably has rule: if implied_price < current_price → REJECT)
Executive Memo section (reads from a different variable or gets None)
Specification:

The IC decision from Step 5 is THE ONLY verdict. Every other section reads from it.

Create one canonical verdict object after Step 5 completes:

verdict = {
    "decision": "APPROVE" | "REJECT" | "HOLD",
    "conviction": "HIGH" | "MEDIUM" | "LOW",
    "debate_winner": "DEAL_CHAMPION" | "RISK_PARTNER",
    "reasoning": [list of reason strings],
    "conditions": [list of condition strings],
    "max_entry_price": float (if APPROVE/HOLD) or None (if REJECT)
}
Every downstream section (Valuation display, Executive Memo, conditions) reads ONLY from this object. Delete any other verdict logic anywhere in the report renderer.

The valuation section should show numbers WITHOUT a verdict label. It says "Base Case Equity: $X" and "Implied Fair Value: $Y" — but does NOT say APPROVE or REJECT. Only the Executive Memo section shows the verdict.

FIX A2: IC Reasoning Format — List to Prose
Problem: Raw Python list printed in report: ["The Deal Champion...", "The forensic score..."]

Specification:

After the IC returns its reasoning as a list, format before rendering:

If reasoning is a list: join with newline, prefix each with "• "
If reasoning is a string: use as-is
Strip any quotes, brackets, or escape characters
The rendered output should look like:

[REASONING]
  • The Deal Champion scored 9/10, demonstrating stronger conviction than the Risk Partner's 7/10
  • Forensic score of 66 exceeds the institutional minimum threshold of 40
  • ROE of 34.4% with stable margins indicates durable earnings quality
  • Fair P/Book of 5.5x vs current 6.3x represents a modest 13% franchise premium
Apply the same formatting to RISKS and CONDITIONS sections.

FIX A3: Memo Section Population
Problem: Thesis Pillars, What Must Go Right / Wrong, and Risks are all blank

Root Cause: The IC output format changed (from string to list), so the memo renderer receives unexpected input type and renders nothing rather than crashing.

Specification:

The Executive Memo must be populated from the IC verdict object. Map fields as follows:

IC VERDICT: verdict["decision"] + verdict["conviction"]
THESIS PILLARS: Extract from IC reasoning — first 2-3 items that are positive (contain words like "strong", "exceeds", "quality", "growth")
WHAT MUST GO RIGHT: Extract from IC conditions
WHAT CAN GO WRONG: Extract from IC reasoning items that are negative/cautionary, OR from Risk Partner's final argument
REASONING: Full formatted reasoning list
RISKS: Risk Partner's key points (store these from Step 4 debate output)
CONDITIONS: verdict["conditions"]
If any section would be empty after this mapping, populate with: "Refer to reasoning section above" — never leave blank.

FIX A4: Valuation Multiple Disconnect
Problem: Step 3 outputs "Fair P/Book: 5.5x" but Base Case Equity implies ~4.0x is actually being applied.

Root Cause: The fair multiple from Step 3 is NOT being used as the input to the equity value calculation. Something else is computing the equity value independently.

Specification:

Trace and enforce this chain:

Step 3 outputs: fair_p_book = 5.5
Equity Value computation: equity_value = fair_p_book × total_book_equity
Per share: implied_price = equity_value / diluted_shares
Where:

total_book_equity = Book Value Per Share × Shares Outstanding (from yfinance ticker.info['bookValue'] × ticker.info['sharesOutstanding'])
Verify: $49.85 × ~710M = ~$35.4B
Expected output: 5.5 × $35.4B = $194.7B equity value → $194.7B / 710M = $274/share

If the system outputs anything materially different from this math, there's an intermediate step corrupting the value. Find it. Common culprits:

Net debt being subtracted (should NOT be for P/Book — this is already equity value, not enterprise value)
A secondary "discount" factor being applied
The fair multiple being overwritten by a different computation between Step 3 and the valuation section
Bear/Base/Bull being averaged rather than using Base as the anchor
Add assertion: abs(base_case_equity - fair_p_book * total_book_equity) / base_case_equity < 0.05 — if they differ by more than 5%, log error.

FIX A5: Max Entry Price Logic
Problem: Shows "MAX ENTRY PRICE: $0.00" even when IC approves

Specification:

If IC APPROVES: max_entry_price = implied_fair_value (this is the ceiling — don't pay above this)
If IC HOLDS: max_entry_price = implied_fair_value × 0.9 (want 10% margin of safety)
If IC REJECTS: max_entry_price = implied_fair_value × 0.75 (would reconsider at 25% discount to fair value) — label as "Re-evaluation Threshold" not "Max Entry Price"
Never show $0.00. If the valuation computation failed, show "N/A — valuation computation error" rather than zero.

Fix Category B: Data Accuracy Issues
FIX B1: "Zero Total Debt" for Credit/Lending Companies
Problem: System tells LLM that AXP has zero debt. AXP has ~$50B+ in borrowings.

Root Cause: yfinance field ticker.info['totalDebt'] or ticker.balance_sheet.loc['Long Term Debt'] may return 0 or NaN for financial companies because their debt is classified differently (as "borrowings", "deposits", "notes payable" rather than "Long Term Debt").

Specification:

For financial sector companies (detected by sector router), compute total debt as:

total_debt = sum of all non-null values from:
  - Long Term Debt
  - Short Term Borrowings / Short Long Term Debt  
  - Current Long Term Debt
  - Long Term Debt And Capital Lease Obligation
Check all available balance sheet fields: print(ticker.balance_sheet.index.tolist()) to identify which debt-related lines yfinance exposes for financials.

If ALL debt fields return 0/NaN for a company classified as "Credit Services" or "Banks", this is a data gap — flag it: "⚠️ Debt data unavailable from automated source. Manual verification required." Do NOT tell the LLM "zero debt" because it will hallucinate from that.

Alternatively, compute implied debt: Total Assets - Total Shareholders' Equity = Total Liabilities — for AXP this would show ~$200B+ in liabilities, proving debt exists.

FIX B2: Cost of Equity Determinism
Problem: CoE fluctuates between runs (9.12% → 10.6% → 9.15%) for the same company.

Root Cause: Either beta is being pulled from different sources, or the risk-free rate is being pulled live and changes with market hours, or some randomness in the computation.

Specification:

Pin every component:

beta = ticker.info['beta']  # Pull once at start of pipeline, store
risk_free_rate = ticker for ^TNX (US 10Y yield) OR hardcode at 4.30% for stability
equity_risk_premium = 5.50%  # Damodaran 2025 estimate, fixed
country_risk_premium = 0.0%  # For US companies; use Damodaran file for non-US

coe = risk_free_rate + beta * equity_risk_premium + country_risk_premium
Store in the data object. Never recompute. Log the value and components at Step 2.

If beta is None from yfinance (happens for some tickers), use sector average:

Financial Services: 1.1
Technology: 1.2
Healthcare: 0.9
Consumer Staples: 0.7
Utilities: 0.5
Energy: 1.0
FIX B3: Efficiency Ratio for Banks (Compute or Suppress)
Problem: Shows N/A for AXP (acceptable) but showed 12.9% for MS (wrong).

Specification:

Efficiency ratio formula:

efficiency_ratio = total_operating_expenses / net_revenue
Where:

net_revenue = the revenue figure already validated in Step 2 (the one showing as $74.1B for AXP, $68.7B for MS)
total_operating_expenses = pull from ticker.financials.loc['Operating Expense'] or 'Total Operating Expenses' or 'Selling General And Administration' + other opex lines
If the computed ratio is:

Below 30%: likely wrong denominator → show "N/A (data inconsistency)"
Between 30% and 95%: display normally
Above 95%: likely distressed or wrong → flag
If the necessary fields aren't available: show "N/A" (as you're doing for AXP — this is correct behavior).

FIX B4: Peer Processing — Cache and Deduplicate
Problem: Same peers computed 3x with identical override messages repeating

Specification:

Create a session-level cache dictionary:

_peer_cache = {}

def get_peer_data(ticker_symbol):
    if ticker_symbol in _peer_cache:
        return _peer_cache[ticker_symbol]
    data = compute_peer_data(ticker_symbol)  # expensive computation
    _peer_cache[ticker_symbol] = data
    return data
This cache should persist for the entire pipeline run. Benefits:

Eliminates 3x duplicate log messages
Reduces yfinance API calls by ~66%
Speeds up pipeline by 15-30 seconds
Removes visual noise from output
FIX B5: Precedent Transactions Sector Mapping
Problem: "Precedents Found: 0" for every company tested so far

Root Cause: The yfinance industry string doesn't map to your CapIQ file names.

Specification:

Build a complete mapping dictionary:

INDUSTRY_TO_CAPIQ_FILE = {
    # Financial Services
    "Credit Services": "financials",
    "Capital Markets": "financials",
    "Banks—Diversified": "financials",
    "Banks—Regional": "financials",
    "Insurance—Diversified": "financials",
    "Insurance—Life": "financials",
    "Asset Management": "financials",
    "Financial Data & Stock Exchanges": "financials",
    "Financial Conglomerate": "financials",
    
    # Technology
    "Internet Retail": "consumer discretionary",
    "Internet Content & Information": "communication",
    "Software—Application": "it",
    "Software—Infrastructure": "it",
    "Semiconductors": "it",
    "Information Technology Services": "it",
    "Electronic Gaming & Multimedia": "communication",
    
    # Healthcare
    "Drug Manufacturers—General": "healthcare",
    "Drug Manufacturers—Specialty": "healthcare",
    "Medical Devices": "healthcare",
    "Health Information Services": "healthcare",
    "Biotechnology": "healthcare",
    "Medical Care Facilities": "healthcare",
    
    # Consumer Discretionary
    "Auto Manufacturers": "consumer discretionary",
    "Restaurants": "consumer discretionary",
    "Apparel Manufacturing": "consumer discretionary",
    "Lodging": "consumer discretionary",
    "Luxury Goods": "consumer discretionary",
    "Home Improvement Retail": "consumer discretionary",
    "Specialty Retail": "consumer discretionary",
    
    # Consumer Staples
    "Packaged Foods": "consumer staples",
    "Beverages—Non-Alcoholic": "consumer staples",
    "Household & Personal Products": "consumer staples",
    "Tobacco": "consumer staples",
    "Grocery Stores": "consumer staples",
    
    # Industrials
    "Aerospace & Defense": "industrials",
    "Airlines": "industrials",
    "Railroads": "industrials",
    "Waste Management": "industrials",
    "Conglomerates": "industrials",
    "Engineering & Construction": "industrials",
    
    # Energy
    "Oil & Gas Integrated": "energy",
    "Oil & Gas E&P": "energy",
    "Oil & Gas Midstream": "energy",
    "Oil & Gas Refining & Marketing": "energy",
    
    # Communication Services
    "Telecom Services": "communication",
    "Entertainment": "communication",
    "Advertising Agencies": "communication",
    
    # Utilities
    "Utilities—Regulated Electric": "utilities",
    "Utilities—Diversified": "utilities",
    "Utilities—Renewable": "utilities",
    
    # Real Estate
    "REIT—Diversified": "real estate",
    "REIT—Retail": "real estate",
    "REIT—Residential": "real estate",
    "Real Estate Services": "real estate",
    
    # Materials
    "Gold": "materials",
    "Steel": "materials",
    "Specialty Chemicals": "materials",
    "Building Materials": "materials",
}
The mapped value corresponds to your file naming: global_ma_{sector}_transactions.xlsx

If ticker.info['industry'] not found in mapping, try ticker.info['sector'] directly (often maps 1:1 to your file names with lowercase).

After loading the file, filter the sub-industry column (SPTR_IQ_TARGET_PRIMARY_INDUSTRY) for closer matches. But at minimum, loading the sector-level file will return hundreds of deals rather than zero.

Fix Category C: Qualitative/Analytical Depth
FIX C1: Peer Selection Improvement
Problem: WU (Western Union) included as AXP peer despite being a remittance company, not a credit issuer. V (Visa) distorts all medians with 15.9x P/Book.

Specification:

For the bank/financial mode peer selector, use this priority logic:

Same sub-industry (Credit Services for AXP): DFS, COF, SYF
Adjacent sub-industry with similar business model (Consumer Lending): ALLY, CACC, OMF
Payment networks (Visa, Mastercard): Include as "reference peers" but EXCLUDE from median calculation — flag as "asset-light network, shown for context"
The peer table should differentiate:

PRIMARY COMPS (included in median):
AXP | 19.7x | 6.34x | 34.4%
DFS | 11.2x | 3.40x | 29.5%
COF | 12.5x | 1.50x | 13.2%
SYF | 7.7x  | 1.62x | 21.8%

REFERENCE PEERS (excluded from median):
V   | 27.8x | 15.91x | 60.3% [asset-light network]
MA  | 35.2x | 45.00x | 180%+ [asset-light network]
Peer median for valuation should use PRIMARY COMPS only.

Also: When computing justified P/Book, give more weight to peers with similar ROE. A peer with 12% ROE trading at 1.5x P/Book is not informative for valuing a 34% ROE company.

FIX C2: IC Debate Prompt — Company-Specific Risk Injection
Problem: Debate produces generic outputs. Both sides discuss "valuation" and "governance" without quantified scenarios.

Specification:

Before calling the IC debate LLM, build a risk context packet from Tavily results. Run a targeted search:

query = f"{company_full_name} risks challenges concerns 2025 2026"
Extract the top 3-5 specific risks found. Inject these into the Risk Partner's prompt:

You are the RISK PARTNER evaluating {company_name}.

SPECIFIC KNOWN RISKS (from market research):
{tavily_risk_results}

YOUR TASK: Build a quantified bear case using these specific risks.
- For each risk, estimate probability (%) and financial impact ($M or bps)
- State the scenario where this investment loses money
- Identify the "kill shot" — the single risk that would make you walk away

RULES:
- You MUST reference at least 2 of the specific risks above
- You MUST quantify your downside scenario (e.g., "If NCO rate rises to 5%, net income drops 40% to $6.7B, justifying only 10x P/E = $95/share")
- Generic statements like "market conditions could worsen" score 0 conviction
Similarly for the Deal Champion:

You are the DEAL CHAMPION arguing for {company_name}.

KEY FINANCIAL STRENGTHS:
- ROE: {roe}% (peer median: {peer_median_roe}%)
- Revenue Growth: {growth}%
- FCF Margin: {fcf_margin}%
- Management Score: {mgmt_score}/100

YOUR TASK: Build a specific, quantified bull case.
- What is the 3-year MOIC (Multiple on Invested Capital) at current entry?
- What catalysts unlock value in the next 12-18 months?
- Why is the current market price justified or undervaluing the company?

RULES:
- You MUST cite specific financial metrics, not generic statements
- You MUST estimate an exit multiple and timeline
- "Strong financial performance" without numbers scores 0 conviction
FIX C3: Forensic Score — Component Computation Logic
Problem: Score of 66 with sub-components that don't clearly derive from data, and "zero debt" hallucination in explanations.

Specification:

Compute each sub-component deterministically from data, then pass COMPUTED SCORE + DATA to the LLM for explanation (not the other way around):

Earnings Quality (0-33):

For banks/financials:
- ROE > 15%: +15 points
- ROE consistent (current vs 3-year avg within 300bps): +10 points
- Net Income growth positive: +8 points

For industrials:
- FCF / Net Income > 80%: full points
- Accruals ratio (Net Income - OCF) / Total Assets < 5%: full points
Capital Adequacy (0-33):

For banks/financials:
- Equity / Assets > 8%: +15 points
- Debt / Equity < 8x: +10 points (for banks this is looser)
- Book Value growing YoY: +8 points

For industrials:
- Net Debt / EBITDA < 2x: full points
- Interest Coverage > 5x: full points
Credit/Sector Risk (0-34):

For credit companies:
- If NCO data available: NCO < 3% → 30 points; 3-5% → 20; >5% → 10
- If not available: default 20 (neutral) with flag
- Revenue diversification (international > 20% of total): +4 points
- Single customer concentration < 10%: +4 points
After computing numerical score, pass to LLM for explanation:

"Generate a one-sentence explanation for each forensic sub-component. 
EQ score: 23/33 — computed from ROE of 34.4% (strong) but YoY inconsistency of 500bps (penalty)
CA score: 28/33 — computed from equity/assets of 10.2% (healthy) and stable book value growth
CR score: 15/34 — computed from estimated NCO rate of 2.4% (above peer median of 1.8%)

Write explanations that reference the ACTUAL data above. Do NOT invent facts."
FIX C4: Sensitivity Table — Must Reconcile with Base Case
Problem: Table center (5.53x × base ROE) shows $188.1B but Base Case Equity is $143.1B.

Specification:

The sensitivity table MUST be constructed so that the center cell equals the base case value (within 1% tolerance).

center_multiple = fair_p_book  # from Step 3 (e.g., 5.5x)
center_metric = total_book_equity  # (e.g., $35.4B)
base_equity_value = center_multiple * center_metric  # = $194.7B

# Table construction:
multiples = [center - 0.5, center - 0.25, center, center + 0.25, center + 0.5]
metrics = [center_metric * 0.8, center_metric, center_metric * 1.2]

# Verify:
assert abs(table[center_row][center_col] - base_equity_value) / base_equity_value < 0.01
If this assertion fails, something between Step 3 and the sensitivity table is modifying the inputs. Find and eliminate it.

Also: highlight the center cell (bold, asterisk, or arrow) so the reader immediately sees which cell corresponds to the base case.

FIX C5: P/E Cross-Check Valuation (Second Methodology)
Problem: Relying solely on P/Book can undervalue/overvalue depending on book value quality. PE firms always use multiple methodologies.

Specification:

For bank-mode companies, compute TWO independent valuations and show both:

Method 1: P/Book (current implementation)

fair_p_book = (ROE - g) / (CoE - g)
equity_value_1 = fair_p_book × total_book_equity
Method 2: P/E Relative

peer_median_pe = median(peer P/E ratios, excluding outliers >40x)
growth_adjustment = 1 + (target_growth - peer_median_growth) / peer_median_growth × 0.5
fair_pe = peer_median_pe × growth_adjustment
equity_value_2 = fair_pe × net_income_ttm
Blended Fair Value:

blended_equity = 0.5 × equity_value_1 + 0.5 × equity_value_2
implied_price = blended_equity / shares_outstanding
Display in report:

VALUATION CROSS-CHECK:
  P/Book Method:  $274/share (5.5x × $49.85 BV/share)
  P/E Method:     $252/share (16x × $15.80 EPS)
  Blended:        $263/share (-17% vs market)
This gives the reader confidence that the valuation isn't methodology-dependent.

FIX C6: Handle "Overvalued" Conclusion Gracefully
Problem: When model says stock is overvalued, IC reflexively rejects. But "overvalued" and "bad investment" are not the same thing — PE firms invest in premium companies all the time with a different entry strategy.

Specification:

Add a third verdict option: HOLD / MONITOR

Decision logic:

if implied_downside > -40%: REJECT (hard pass)
if implied_downside > -20% AND forensic < 50: REJECT (quality concerns)
if implied_downside > -20% AND forensic >= 50 AND management >= 60:
    HOLD — "Quality franchise, wait for pullback. Entry below ${implied_fair_value}"
if implied_downside > -10%: APPROVE WITH CAUTION
if implied_upside > 0%: APPROVE
For AXP (-17% to -27% depending on method) with forensic 66 and management 80: → HOLD: "Premium franchise trading above intrinsic value. Recommend entry on pullback below $265. Monitor credit cycle for forced selling opportunity."

This is FAR more useful to a PE reader than a binary APPROVE/REJECT for a best-in-class company.

FIX C7: Add Margin of Safety and Entry Strategy
Problem: Report gives one implied price but no strategy for HOW to invest.

Specification:

Add an "Entry Strategy" section after Actionable Valuation:

------------------------------
  ENTRY STRATEGY
------------------------------
  Fair Value:       $263/share
  Current Price:    $316/share (20% premium to fair value)
  
  Recommended Entry: Below $265 (at/below fair value)
  Aggressive Entry:  Below $284 (10% premium — accepts franchise value)
  Walk Away Above:   $350 (>33% premium — no margin of safety)
  
  Catalyst Watch:
  • Credit cycle turn (NCO spike → stock drops 15-20%, creates entry)
  • Earnings miss (any quarter below $3.50 EPS → reassess)
  • Competitor disruption (BNPL taking share above 5% of AXP volume)
This transforms the output from "academic exercise" to "actionable trade idea."

Fix Category D: Presentation and Polish
FIX D1: Report Header — Add Key Stats Inline
Problem: Reader has to scan through multiple sections to get the essential picture.

Specification:

Add a one-line executive summary at the very top:

======================================================================
  EXECUTIVE SUMMARY
  AXP | $316 | Fair Value: $263 | Upside: -17% | HOLD (Wait for Pullback)
  ROE: 34.4% | Growth: 11.6% | Forensic: 66 | Management: 80
======================================================================
This gives a PE MD the full picture in 2 seconds before they decide whether to read further.

FIX D2: Footnote on Methodology Limitations
Problem: No acknowledgment of model limitations. Every PE memo has a "Risks to Our Analysis" section.

Specification:

Add at the bottom:

MODEL LIMITATIONS & CAVEATS:
• Valuation based on P/Book and P/E relative methods; does not capture sum-of-parts value
• Forensic score computed from publicly available data only; does not substitute for full QoE engagement
• Peer set determined algorithmically; may not reflect all relevant comparables
• Management assessment based on public sources; does not include proprietary reference checks
• This is an automated screening tool, not a replacement for full due diligence
This is how real research disclaims and it actually INCREASES credibility because it shows awareness of limitations.

FIX D3: Number Formatting Consistency
Problem: Some numbers show as 17.474207 (too many decimals), some as 6.34x (clean). The raw JSON 34.419% is also showing through.

Specification:

Formatting rules for all displayed numbers:

Multiples (P/E, P/Book, EV/EBITDA): 1 decimal place + "x" → 17.5x
Percentages (ROE, growth, margins): 1 decimal place + "%" → 34.4%
Dollar values in millions: 0 decimals + "$" + "M" → $74,171M
Dollar values in billions (>$999M): 1 decimal + "$" + "B" → $143.1B
Share prices: 2 decimal places + "$" → $316.03
Ratios in sensitivity table: 2 decimal places → 5.53x
Apply formatting at the render stage (not in computation) to avoid precision loss.

FIX D4: Suppress Verbose Log Messages in Final Output
Problem: All the [FIX 7], [FIX 5], [PEERS] messages print to stdout mixed with the report.

Specification:

Route all diagnostic/debug messages to stderr or a log file. Only the final formatted report should print to stdout.

Or: Add a --verbose flag. Default mode prints only the final report. Verbose mode shows the step-by-step processing.

For hackathon demo purposes, the step headers (Step 1, Step 2, etc.) are fine to show — they demonstrate the pipeline working. But the individual [FIX 7] BS Override: Net Debt $-7,021M lines should be suppressed in demo mode.

Implementation Priority Order
Phase 1 (Fix before next run — 30 minutes):

A1: Single verdict source
A2: Format reasoning as bullets
A3: Populate memo from IC output
A5: Max entry price logic
Phase 2 (Fix next — 1 hour): 5. A4: Valuation multiple disconnect (trace why 5.5x → $143B instead of $195B) 6. B2: Pin Cost of Equity 7. C4: Sensitivity table reconciliation 8. B4: Peer computation caching

Phase 3 (Analytical depth — 1-2 hours): 9. C1: Peer selection improvement 10. C2: Debate prompt specificity 11. C5: P/E cross-check 12. C6: HOLD verdict logic

Phase 4 (Polish for demo — 30 minutes): 13. D1: Executive summary header 14. D3: Number formatting 15. D4: Log suppression 16. D2: Limitations footnote

Phase 5 (LLM Sublayer — if time permits): 17. Add SCL after Step 3 (valuation sanity check) 18. Add SCL after Step 5 (verdict consistency check) 19. Add SCL on final report (contradiction scan)

Final Note for Antigravity
The single most impactful fix is A4 (valuation multiple disconnect). If the fair P/Book of 5.5x actually flows through to equity value correctly:

5.5 × $35.4B = $194.7B → $274/share → -13% vs market
Combined with P/E cross-check (~$252/share), the blended fair value would be ~$263 vs $316 current — a -17% gap. With the HOLD verdict logic (C6), this produces:

"HOLD: Quality franchise, entry on pullback below $265"

That is a PE-grade conclusion. Everything else is formatting and polish around that core analytical output.