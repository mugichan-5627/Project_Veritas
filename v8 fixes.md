
Project Veritas — Definitive Fix Specifications for Antigravity
I understand. You want to give Antigravity precise, unambiguous instructions that produce results the first time, not vague guidance that requires 10 follow-up prompts. Here are the fixes written as exact behavioral specifications — what the system MUST do, with the logic spelled out so clearly that any code editor can implement it without interpretation.

FIX 1: The Peer Engine Must Never Return Empty
The Problem: When the LLM fails to infer peers or CapIQ doesn't have a match, the pipeline runs with peers = [] and produces a comp table with only the target company. This makes the entire valuation groundless.

The Specification:

PEER DISCOVERY LOGIC (ordered fallback chain):

Step 1: Ask LLM to suggest 8-10 peers based on company description and sector.
Step 2: For each suggested peer, pull it from yfinance. If it exists and has valid financials, keep it.
Step 3: Score each surviving peer using similarity function (defined below).
Step 4: Take top 5 by score.

IF after Step 4, fewer than 3 peers survive:
  Step 5: Use SECTOR_FALLBACK_MAP (hardcoded dictionary, defined below).
  
IF after Step 5, still fewer than 3 peers:
  Step 6: Broaden to adjacent GICS sub-industries. Retail -> Consumer Staples -> Consumer Discretionary.

NEVER proceed to valuation with fewer than 3 peers. If all fallbacks fail, print:
  "[CRITICAL] Unable to establish peer set. Valuation unreliable. Manual peer input required."
  Set confidence to LOW. Do not calculate Fair Value Multiple from comps.

SECTOR_FALLBACK_MAP = {
    "Discount Stores": ["COST", "TGT", "DG", "DLTR", "BJ"],
    "Credit Services": ["MA", "FIS", "FISV", "GPN", "PYPL"],
    "Semiconductors": ["AVGO", "QCOM", "TXN", "AMD", "INTC"],
    "Aerospace & Defense": ["LMT", "NOC", "RTX", "GD", "BA"],
    "Software - Infrastructure": ["MSFT", "ORCL", "CRM", "NOW", "ADBE"],
    "Software - Application": ["ADBE", "INTU", "CDNS", "SNPS", "ANSS"],
    "Banks - Diversified": ["JPM", "BAC", "WFC", "C", "GS"],
    "Insurance - Diversified": ["BRK-B", "AIG", "MET", "PRU", "ALL"],
    "Internet Content & Information": ["GOOGL", "META", "SNAP", "PINS", "TTD"],
    "Drug Manufacturers": ["JNJ", "LLY", "PFE", "MRK", "ABBV"],
    "Oil & Gas Integrated": ["XOM", "CVX", "SHEL", "TTE", "BP"],
    "Consumer Electronics": ["AAPL", "SONY", "HPQ", "DELL"],
    "Restaurants": ["MCD", "SBUX", "CMG", "YUM", "DPZ"],
    "Specialty Retail": ["HD", "LOW", "TJX", "ROST", "BBY"],
    "Beverages": ["KO", "PEP", "MNST", "STZ", "BF-B"],
    "Household Products": ["PG", "CL", "KMB", "CHD", "CLX"],
    "REITs": ["PLD", "AMT", "EQIX", "SPG", "O"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP"],
    "Telecom": ["T", "VZ", "TMUS", "CMCSA", "CHTR"],
    "Auto Manufacturers": ["TM", "F", "GM", "TSLA", "HMC"],
    "Medical Devices": ["MDT", "SYK", "ABT", "BSX", "ISRG"],
    "Capital Markets": ["GS", "MS", "SCHW", "BLK", "ICE"],
    "Exchanges": ["ICE", "CME", "NDAQ", "CBOE", "SPGI"],
    "Payments/Networks": ["V", "MA", "FIS", "FISV", "GPN"],
}

SIMILARITY SCORING (for ranking peers after discovery):

def score_peer(target, peer):
    margin_diff = abs(target.ebitda_margin - peer.ebitda_margin) / target.ebitda_margin
    growth_diff = abs(target.revenue_growth - peer.revenue_growth) / max(target.revenue_growth, 0.01)
    capex_intensity_target = target.capex / target.revenue
    capex_intensity_peer = peer.capex / peer.revenue
    capex_diff = abs(capex_intensity_target - capex_intensity_peer) / max(capex_intensity_target, 0.01)
    size_diff = abs(log(target.market_cap) - log(peer.market_cap)) / log(target.market_cap)
    
    score = 1.0 - (0.30 * margin_diff + 0.30 * growth_diff + 0.20 * capex_diff + 0.20 * size_diff)
    return max(score, 0)  # clamp to 0-1

Take top 5 peers by score. Display all in report with their scores.
FIX 2: Dynamic RAG Queries Based on Target Company
The Problem: The system always queries the RAG with the same hardcoded test strings ("How to value a high-growth tech company with no debt?" / "What are governance red flags in semiconductor companies?") regardless of what company is being analyzed. This means the RAG returns irrelevant chunks.

The Specification:

BEFORE querying ChromaDB, dynamically construct queries based on the target's actual attributes:

INPUTS AVAILABLE AT QUERY TIME:
- ticker
- sector (e.g., "Discount Stores")
- tier (1, 2, 3, or 4)
- revenue_growth (e.g., 5.6%)
- ebitda_margin (e.g., 6.5%)
- has_debt (boolean)

QUERY GENERATION LOGIC:

query_valuation = f"How to value a {get_growth_descriptor(revenue_growth)} {sector} company with {get_leverage_descriptor(has_debt, debt_to_ebitda)}?"

query_forensic = f"What are accounting red flags and forensic risks in {sector} or {get_broader_industry(sector)} companies?"

query_methodology = f"What valuation multiples and methods are appropriate for Tier {tier} companies in {sector}?"

HELPER FUNCTIONS:

def get_growth_descriptor(growth):
    if growth > 25: return "high-growth"
    elif growth > 10: return "moderate-growth"
    elif growth > 0: return "low-growth mature"
    else: return "declining"

def get_leverage_descriptor(has_debt, debt_to_ebitda):
    if not has_debt or debt_to_ebitda < 0.5: return "minimal debt"
    elif debt_to_ebitda < 2.5: return "moderate leverage"
    elif debt_to_ebitda < 4.0: return "significant leverage"
    else: return "high leverage"

def get_broader_industry(sector):
    mapping = {
        "Discount Stores": "retail and consumer",
        "Credit Services": "financial technology and payments",
        "Semiconductors": "hardware and technology",
        "Aerospace & Defense": "industrial and government contracting",
        "Software - Infrastructure": "technology and SaaS",
        ... (expand for all sectors you support)
    }
    return mapping.get(sector, "general business")

ALSO: Query the CapIQ collections dynamically:

query_precedent = f"Precedent transactions in {sector} or {get_broader_industry(sector)} above $1B enterprise value in the last 5 years"

query_comps = f"Comparable company trading multiples for {sector} companies with revenue above ${revenue_bucket}B"

RESULT: The RAG now returns chunks RELEVANT to the actual target, not generic software/semiconductor content.
FIX 3: Fair Value Multiple Must Be Independently Derived, Not Circular
The Problem: Both Visa and Walmart showed approximately -5% implied downside. This suggests the fair value multiple is being calculated as current_multiple × some_fixed_discount rather than independently derived. This is circular — you're just saying "it's worth 5% less than it trades" for every company.

The Specification:

FAIR VALUE MULTIPLE MUST BE DERIVED FROM ONE OF THREE INDEPENDENT METHODS:

Method A: Peer Median (Primary, when peers exist)
  fair_value_multiple = median(peer_ev_ebitda_multiples) × quality_adjustment

  quality_adjustment logic:
    - If target growth > peer_median_growth by >5pp: multiply by 1.15 (growth premium)
    - If target growth < peer_median_growth by >5pp: multiply by 0.85 (growth discount)
    - If target ROIC > peer_median_ROIC by >5pp: multiply by 1.10 (quality premium)
    - If target FCF_margin > peer_median_FCF by >5pp: multiply by 1.10 (cash premium)
    - Cap total adjustment between 0.75x and 1.35x of peer median

Method B: DCF-Implied Multiple (Secondary, always calculate for cross-check)
  Step 1: Project FCF for 5 years using revenue_growth declining linearly to terminal_growth
  Step 2: Terminal Value = Year5_FCF × (1 + terminal_growth) / (WACC - terminal_growth)
  Step 3: Total EV = sum of discounted FCFs + discounted Terminal Value
  Step 4: implied_multiple = Total EV / current_EBITDA
  
  terminal_growth RULES:
    - Default: 3.0% (approximate nominal GDP)
    - If sector is high-growth tech and current growth > 20%: 4.0%
    - If sector is mature/declining: 2.0%
    - HARD CAP: terminal_growth must NEVER exceed 5.0%
    - HARD FLOOR: terminal_growth must NEVER be below 1.5%

Method C: Historical Range (Tertiary, for context)
  Use the target's own 5-year average EV/EBITDA multiple from CapIQ or yfinance history.
  Note where current trading sits relative to its own history (percentile).

FINAL FAIR VALUE LOGIC:
  If peers exist (≥3):
    fair_value_multiple = average(Method_A, Method_B), weighted 60% A / 40% B
  If peers do NOT exist:
    fair_value_multiple = Method_B only
    Flag: "Peer-based valuation unavailable. DCF-only estimate. Lower confidence."

  REPORT MUST SHOW:
    "Peer-Implied Multiple: X.Xx | DCF-Implied Multiple: X.Xx | Blended Fair Value: X.Xx"
    "Target currently trades at: X.Xx | Premium/Discount to Fair Value: +/-X%"

NEVER calculate fair_value as current_multiple × 0.95 or any fixed transformation of the current price.
The entire point is that fair value is INDEPENDENT of current market price.
FIX 4: Forensic Scoring Must Be Sector-Relative
The Problem: Walmart got a leverage score of 5/100 despite having only 1.26x Net Debt/EBITDA, which is conservative for retail. The scoring is using absolute thresholds instead of sector-relative benchmarks.

The Specification:

FORENSIC SCORING SYSTEM (Revised):

Total Score: 100 points across 5 sub-scores (20 each)

SUB-SCORE 1: CASH QUALITY (0-20)
  Measure: Operating Cash Flow / Net Income (cash conversion)
  Scoring:
    > 1.2 = 20 (excellent cash conversion)
    1.0 - 1.2 = 15
    0.8 - 1.0 = 10
    0.5 - 0.8 = 5
    < 0.5 = 0 (earnings not backed by cash — red flag)

SUB-SCORE 2: MARGIN STABILITY (0-20)
  Measure: Standard deviation of gross margin over last 4-8 quarters (if available)
  If not available: Use single-period gross margin vs sector norm
  Scoring:
    Std dev < 1pp OR margin within 5pp of sector norm = 20
    Std dev 1-3pp = 15
    Std dev 3-5pp = 10
    Std dev > 5pp = 5
    Margin declining for 3+ consecutive quarters = 0

SUB-SCORE 3: LEVERAGE HEALTH (0-20) — SECTOR RELATIVE
  Measure: Net Debt / EBITDA relative to SECTOR NORM

  SECTOR NORMS (Net Debt / EBITDA):
    Technology/Software: 0.0 - 1.0x (many are net cash)
    Payments/Networks: 0.5 - 1.5x
    Retail/Consumer: 1.0 - 3.0x
    Industrials: 1.5 - 3.5x
    Utilities/REITs: 3.0 - 6.0x
    Banks: Use Tier 1 Capital Ratio instead (>12% = good)
    Telecom: 2.5 - 4.5x
    Healthcare: 1.0 - 3.0x
    Oil & Gas: 1.0 - 2.5x

  Scoring:
    Below sector norm midpoint = 20 (conservatively levered)
    At sector norm midpoint = 15
    Above midpoint but within norm range = 10
    Above sector norm upper bound by <1x = 5
    Above sector norm upper bound by >1x = 0 (dangerously levered)

  EXAMPLE: WMT at 1.26x, Retail norm midpoint = 2.0x → SCORE = 20 (not 5!)

SUB-SCORE 4: SBC BURDEN (0-20)
  Measure: SBC / Revenue
  Scoring:
    < 1% = 20 (negligible)
    1-3% = 15
    3-5% = 10
    5-10% = 5
    > 10% = 0 (massive dilution concern)
  
  IF SBC data is missing (returns 0 for large company): Score = 10 and flag "SBC data unavailable"

SUB-SCORE 5: REVENUE QUALITY (0-20)
  Measure: Revenue growth consistency + customer concentration signals
  Scoring:
    Positive growth for 4+ consecutive quarters AND growth > sector avg = 20
    Positive growth but below sector avg = 15
    Flat (0-2% growth) = 10
    Declining 1-2 quarters = 5
    Declining 3+ quarters = 0

TOTAL FORENSIC SCORE = Sum of all 5 sub-scores

REPORT DISPLAY:
  "FORENSIC: 82/100 (Cash: 15 | Margin: 20 | Leverage: 20 | SBC: 20 | RevQuality: 7)"
  Plus one-line explanation for any sub-score below 10.
FIX 5: SBC Data Validation and Fallback
The Problem: Walmart showed SBC = $0 which is factually wrong. yfinance sometimes returns None/0 for this field.

The Specification:

SBC DATA PULL LOGIC:

Step 1: Try yfinance income statement field "Stock Based Compensation" or "Share Based Compensation"
Step 2: If result is None, 0, or NaN:
  Step 2a: Try yfinance cash flow statement "Stock Based Compensation" (it often appears here even when missing from income statement)
  Step 2b: If still None/0: Try calculating from (Operating Cash Flow - Net Income - Depreciation - Working Capital Changes). This is imprecise but gives a floor estimate.
  Step 2c: If still unavailable: Set SBC = "UNAVAILABLE" (not zero)

SANITY CHECK:
  If company revenue > $10B AND SBC == 0:
    Flag: "[WARN] SBC reported as $0 for a large-cap company. Data likely missing from source."
    Set SBC_status = "UNVERIFIED"
    In the report, note: "SBC data unavailable from automated source. Manual verification required."
    Do NOT subtract $0 and call it "Adjusted EBITDA" — instead, label it "EBITDA (Unadjusted — SBC data missing)"

  If SBC / Revenue > 25%:
    Flag: "[WARN] SBC/Revenue ratio unusually high. Verify data accuracy."

REPORT DISPLAY:
  If SBC is valid: "SBC Haircut: -$X,XXXM (X.X% of revenue)"
  If SBC is missing: "SBC Haircut: DATA UNAVAILABLE — EBITDA shown is unadjusted. Manual verification needed."
FIX 6: Full Debate Text Must Appear in Report
The Problem: Only headlines show. The plan said full text would be included. It wasn't.

The Specification:

DEBATE OUTPUT STRUCTURE:

During the debate, store the FULL response text from each agent in a list:

debate_transcript = []

For each round:
  champion_response = call_llm(champion_prompt)  # This is the full text
  risk_response = call_llm(risk_prompt)  # This is the full text
  
  debate_transcript.append({
      "round": round_number,
      "champion": {
          "headline": extract_headline(champion_response),
          "full_argument": champion_response,  # STORE THE FULL TEXT
          "conviction": extract_conviction(champion_response)
      },
      "risk_partner": {
          "headline": extract_headline(risk_response),
          "full_argument": risk_response,  # STORE THE FULL TEXT
          "conviction": extract_conviction(risk_response)
      }
  })

IN THE FINAL REPORT, add a section:

======================================================================
  FULL DEBATE TRANSCRIPT
======================================================================

--- ROUND 1 ---

[DEAL CHAMPION] (Conviction: X/10)
{full text of champion argument, round 1}

[RISK PARTNER] (Conviction: X/10)
{full text of risk partner argument, round 1}

--- ROUND 2 ---

[DEAL CHAMPION] (Conviction: X/10)
{full text of champion argument, round 2}

[RISK PARTNER] (Conviction: X/10)
{full text of risk partner argument, round 2}

======================================================================

This section goes AFTER the Executive Investment Memo but BEFORE Data Provenance.

THE DEBATE PROMPT ITSELF should instruct agents to structure their arguments as:

"You must address: (1) Your core thesis in 2-3 sentences, (2) The specific financial evidence supporting it, (3) The quantified impact — state dollar amounts or percentages, (4) What specific event or metric would BREAK your argument."
FIX 7: Sensitivity Table Must Be Calculated and Displayed
The Problem: No sensitivity analysis is shown. The "CONVERGENCE SPREAD" field shows $0 (a bug). PE firms require a WACC vs. Growth matrix.

The Specification:

SENSITIVITY MATRIX CALCULATION:

After calculating base WACC and terminal growth (g):

wacc_range = [WACC - 1.5%, WACC - 0.75%, WACC, WACC + 0.75%, WACC + 1.5%]
growth_range = [g - 1.0%, g - 0.5%, g, g + 0.5%, g + 1.0%]

For each combination of (wacc_i, growth_j):
  Calculate implied EV using the DCF formula:
    TV = FCF_year5 × (1 + growth_j) / (wacc_i - growth_j)
    EV = sum(discounted_FCFs) + discounted_TV
  
  Convert to implied price per share:
    implied_price = (EV - net_debt + cash) / shares_outstanding

Store results in a 5×5 matrix.

DISPLAY IN REPORT:

------------------------------
  SENSITIVITY: IMPLIED SHARE PRICE
  (Rows = WACC, Columns = Terminal Growth)
------------------------------
              |  2.0%  |  2.5%  |  3.0%  |  3.5%  |  4.0%  |
  ---------------------------------------------------------
  5.8%        | $XXX   | $XXX   | $XXX   | $XXX   | $XXX   |
  6.6%        | $XXX   | $XXX   | $XXX   | $XXX   | $XXX   |
  7.3% (Base) | $XXX   | $XXX   | $XXX   | $XXX   | $XXX   |
  8.1%        | $XXX   | $XXX   | $XXX   | $XXX   | $XXX   |
  8.8%        | $XXX   | $XXX   | $XXX   | $XXX   | $XXX   |
  ---------------------------------------------------------
  Current Price: $130.95 | Base Case: $124.03

ALSO FIX CONVERGENCE SPREAD:
  convergence_spread = bull_case_ev - base_case_ev
  convergence_pct = (bull_case_ev - base_case_ev) / base_case_ev × 100
  Display: f"CONVERGENCE SPREAD (Bull vs Base): ${convergence_spread:,.0f}M ({convergence_pct:.1f}% buffer)"

  For WMT this should show: "$275,568M (26.3% buffer)" — NOT "$0M (0%)"
FIX 8: IC Decision Must Be Logically Consistent With Valuation
The Problem: In v7, the system APPROVED Visa despite negative implied upside. In v8, the system somewhat accidentally got this right by rejecting WMT. But the logic should be EXPLICIT, not accidental.

The Specification:

IC DECISION RULES (Hard Logic Gates — applied BEFORE LLM deliberation):

RULE 1: AUTOMATIC REJECT
  IF implied_upside < -15%: AUTO_REJECT
  Reason: "Target trades more than 15% above our fair value estimate."

RULE 2: VALUATION CAUTION FLAG
  IF implied_upside is between -15% and 0%:
  Set flag: OVERVALUATION_FLAG = True
  The IC LLM MUST address this flag explicitly in its reasoning.
  It may still approve IF it articulates WHY the fair value will grow (e.g., "Revenue acceleration in coming quarters will push fair value above current price within 12 months")
  If it cannot articulate this: REJECT.

RULE 3: AUTOMATIC APPROVE CANDIDATE
  IF implied_upside > +20% AND forensic_score > 60 AND debate_winner == "DEAL_CHAMPION":
  Set as STRONG_APPROVE candidate. IC LLM confirms.

RULE 4: PEER VALIDATION REQUIRED
  IF peers == [] or len(peers) < 3:
  IC CANNOT issue APPROVE or CONDITIONAL_APPROVE.
  Maximum possible verdict: "INSUFFICIENT_DATA — peer validation required before investment decision."

RULE 5: FORENSIC GATE
  IF forensic_score < 30:
  Auto-add condition: "Independent forensic accounting review required before commitment."
  Cannot be STRONG_APPROVE regardless of other factors.

RULE 6: CONSISTENCY CHECK
  After IC LLM generates its decision, programmatically verify:
  - If verdict == APPROVE and implied_upside < 0: CONTRADICTION → force LLM to re-reason with explicit prompt: "You approved an investment trading above fair value. Explain what catalyst will close this gap within your hold period, or change your decision to REJECT."
  - If verdict == REJECT and implied_upside > 30: CONTRADICTION → force re-reason: "You rejected an investment trading 30%+ below fair value. Explain what specific risk justifies passing on this margin of safety, or change your decision to CONDITIONAL_APPROVE."

These rules are PROGRAMMATIC (Python if-statements). They run BEFORE and AFTER the LLM call. The LLM provides qualitative reasoning; the code enforces logical consistency.
FIX 9: Tavily Intelligence Must Be Date-Verified
The Problem: The IC memo referenced a "DOJ investigation" for Walmart that may be a 2022 settled case presented as ongoing. LLM cannot distinguish old news from current news without dates.

The Specification:

TAVILY SEARCH ENHANCEMENT:

When calling Tavily for business intelligence:

Step 1: Set search parameters to prioritize RECENT results:
  - search_depth: "advanced"
  - include_dates: True (or filter to last 12 months)
  - topic: "news" for risk/legal queries

Step 2: For EACH piece of intelligence returned, extract or infer the date.

Step 3: In the LLM prompt that processes Tavily results, include this instruction:

  "You are analyzing search results about {company}. For any legal, regulatory, or risk-related finding:
   1. State the DATE of the event or article.
   2. State whether this is ONGOING or RESOLVED.
   3. If resolved, state the resolution (settlement amount, dismissal, etc.).
   4. Do NOT present resolved matters as current risks unless there is evidence of ongoing exposure.
   
   If you cannot determine whether a matter is resolved or ongoing, state: 'Status: UNVERIFIED — requires manual confirmation.'"

Step 4: In the final report, any risk cited from Tavily must include:
  - Source date
  - Status (Ongoing / Resolved / Unverified)
  
  Example correct output:
    "DOJ Opioid Investigation — RESOLVED (Nov 2022, $3.1B settlement). No ongoing material legal exposure identified."
  
  Example of what to PREVENT:
    "Ongoing DOJ investigation poses risk" (with no date, no status, no specifics)
FIX 10: CapIQ Data Must Actually Be Used and Shown
The Problem: You have premium CapIQ data (precedent transactions, comparable companies for 16 years, global coverage) but the output shows no evidence of it being retrieved or displayed. The RAG returns "demo" chunks, suggesting the CapIQ data may not be properly ingested or the queries don't match.

The Specification:

CAPIQ DATA INTEGRATION:

ASSUMPTION: You have CapIQ CSVs/Excel files containing:
  - Precedent transactions (date, target, acquirer, EV, EV/EBITDA, EV/Revenue, sector)
  - Comparable companies (ticker, sector, multiples, margins, growth)

INGESTION INTO CHROMADB:

Each precedent transaction should be chunked as ONE document with this format:
  "{date} | {acquirer} acquired {target} | Sector: {sector} | EV: ${X}B | EV/EBITDA: {X}x | EV/Revenue: {X}x | Premium: {X}% | Deal Type: {type}"

  Metadata fields: {source: "CapIQ", type: "precedent_transaction", sector: "{sector}", year: {year}, ev_ebitda: {float}}

Each comparable company entry should be:
  "{ticker} | {company_name} | Sector: {sector} | Market Cap: ${X}B | EV/EBITDA: {X}x | Revenue Growth: {X}% | EBITDA Margin: {X}%"

  Metadata fields: {source: "CapIQ", type: "comparable_company", sector: "{sector}", ticker: "{ticker}"}

COLLECTIONS:
  - "capiq_precedent_transactions" — all M&A deals
  - "capiq_comparable_companies" — all trading comps

QUERY AT RUNTIME:

  After sector/tier is determined:
  
  query_precedent = f"Acquisitions in {sector} with enterprise value above $5 billion in the last 5 years"
  results_precedent = chroma_collection_precedent.query(query_texts=[query_precedent], n_results=10)
  
  query_comps = f"{sector} companies with revenue growth between {target_growth - 10}% and {target_growth + 10}% and EBITDA margin between {target_margin - 10}% and {target_margin + 10}%"
  results_comps = chroma_collection_comps.query(query_texts=[query_comps], n_results=10)

DISPLAY IN REPORT:

  ----------------------------------------
    PRECEDENT TRANSACTIONS (from CapIQ)
  ----------------------------------------
    Date       | Target        | Acquirer    | EV/EBITDA | EV/Rev
    -----------------------------------------------------------
    2023-04    | Target Co A   | Acquirer X  | 18.5x    | 3.2x
    2022-11    | Target Co B   | Acquirer Y  | 15.2x    | 2.8x
    ... (show top 5 most relevant)
    
    Median Precedent EV/EBITDA: X.Xx
    
  This median feeds into the Fair Value Multiple calculation as an additional data point:
    fair_value_multiple = weighted_average(peer_median: 40%, dcf_implied: 35%, precedent_median: 25%)
Summary: What To Tell Antigravity
Give it these 10 fixes as sequential implementation tasks. The order matters:

Fix 1 (Peer engine) — without peers, nothing downstream works
Fix 10 (CapIQ ingestion) — your most valuable data asset isn't being used
Fix 2 (Dynamic RAG queries) — makes the knowledge base actually relevant
Fix 3 (Fair value methodology) — eliminates the circular "-5% always" problem
Fix 4 (Forensic recalibration) — stops wrong scores from driving wrong decisions
Fix 5 (SBC validation) — data quality gate
Fix 7 (Sensitivity table) — PE firms require this, and it replaces the broken Convergence Spread
Fix 8 (IC consistency logic) — prevents approve-above-fair-value contradiction
Fix 6 (Full debate text) — transparency requirement
Fix 9 (Tavily date verification) — prevents hallucinated/stale risk claims
Each fix is self-contained — you can implement and test them independently. After all 10, run your regression suite (V, WMT, GS, NVDA) and every output should be dramatically more credible.