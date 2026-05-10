Project Veritas — Goldman Sachs (GS) Evaluation
Honest Assessment: This Exposes a Fundamental Limitation
This run is highly informative because it reveals that your pipeline — which was built for non-financial companies — breaks down when applied to banks and financial institutions. This isn't a bug; it's a known architectural challenge that even Goldman Sachs's own analysts deal with. Let me explain what happened and how to fix it.

The Core Problem: Banks Don't Have EBITDA
EBITDA (Rep): $0M
EBITDA (Adj): $0M
Current Trading Multiple: 0.0x
Peer Comps: []
This is fundamentally correct behavior from yfinance — banks genuinely don't report EBITDA in a meaningful way. Here's why:

Metric	Non-Financial Company (AMZN)	Financial Institution (GS)
Revenue	Product/service sales	Net interest income + fees + trading
EBITDA	Operating Income + D&A	Not applicable (no "operating" vs "financing" distinction)
Key Metric	EV/EBITDA	P/E, P/Book, ROE
Debt	Borrowing to fund operations	Deposits and borrowings ARE the business
Enterprise Value	Market Cap + Net Debt	Not meaningful (debt is the product, not a liability)
For Goldman Sachs:

Their "debt" of $219B isn't leverage like Boeing's debt — it's customer deposits, trading liabilities, and repo agreements that ARE the business
EV/EBITDA is meaningless because there's no "EBITDA" for a bank
The correct valuation metrics are: P/E ratio, P/Tangible Book Value, ROE, Efficiency Ratio
What the Pipeline Should Do for Financials
Your pipeline needs a sector-specific valuation path that activates when the target is a financial institution:

Is the company a bank/financial?
    │
    YES → Use Bank Valuation Path:
    │     • P/E ratio (not EV/EBITDA)
    │     • P/Tangible Book Value
    │     • ROE vs Cost of Equity
    │     • Efficiency Ratio
    │     • No Enterprise Value calculation
    │
    NO → Use Standard Path (current):
          • EV/EBITDA
          • DCF/WACC
          • Standard peer comps
What Went Right ✅
1. Sector Detection Correct
Sector: Capital Markets ✅
Industry: Capital Markets ✅
2. Peer Sector Filtering Working Excellently
[EXCLUDED] AAPL: Sector 'Technology' incompatible ✅
[EXCLUDED] MSFT: Sector 'Technology' incompatible ✅
[EXCLUDED] TSLA: Sector 'Consumer Cyclical' incompatible ✅
This is the fix from BA working perfectly. The pipeline correctly rejected tech companies as peers for a financial institution. The problem is that after excluding wrong peers, it found zero valid ones — leaving the comp table empty.

3. Revenue is Correct
Revenue (TTM): $60,448M (Growth: 14.5%)
Goldman's actual TTM revenue (through early 2026): approximately $55-65B. This is in the correct range.

4. Competitive Moat is Excellent
Goldman Sachs' competitive advantages include its recognizable brand, long-term 
relationships, high switching costs, and financial stability... deep market-making 
and principal capabilities, as well as its growing UHNW and family office franchise
This is actually a very accurate and specific moat description for Goldman. Well done by the Tavily enrichment.

5. TAM/SAM/SOM Populated
TAM: $23.7B | SAM: $8.4B | SOM: $2.5B
Structured format, not a raw snippet. Progress from earlier runs.

6. Forensic Score Appropriately Cautious
FORENSIC: 65 (Cash:20 | Margin:20 | Lev:5)
Leverage score of 5/25 is correct — Goldman is extremely leveraged (by design, as a bank). The system recognized this.

7. IC Debate Produced a Winner
Champion: 8/10 | Risk Partner: 7/10
Debate Winner: DEAL_CHAMPION
First time the debate produced a clear winner rather than a draw. This is appropriate — Goldman is generally a quality franchise despite the valuation concerns.

What Went Wrong ❌
1. EBITDA = $0 (Breaks Entire Valuation Chain)
The pipeline's entire valuation methodology depends on EBITDA:

EV/EBITDA = 0x (meaningless)
SBC adjustment applied to $0 (useless)
Peer premium calculation impossible
For banks, the correct metrics are:

# What Goldman ACTUALLY reports and how analysts value it:
net_income = stock.info.get("netIncomeToCommon")       # ~$13-15B
book_value = stock.info.get("bookValue")                # ~$370/share
tangible_book = book_value - intangibles_per_share      # ~$340/share
roe = net_income / total_equity                         # ~12-15%

# Correct multiples for banks:
pe_ratio = stock.info.get("trailingPE")                 # ~14-16x
price_to_book = stock.info.get("priceToBook")           # ~1.5-2.0x
price_to_tangible_book = price / tangible_book           # ~1.7-2.2x
2. FCF Margin of -69.4% (Meaningless for Banks)
Banks' cash flow statements look wildly different from operating companies. "Operating cash flow" for Goldman includes massive swings in trading assets/liabilities that have nothing to do with business health. A -69% FCF margin doesn't mean Goldman is burning cash — it means their balance sheet expanded (which is often positive for a bank).

3. Net Debt of $219B (Misunderstood)
For a bank, "net debt" isn't really debt in the traditional sense. Goldman's liabilities include:

Customer deposits
Securities sold under repurchase agreements
Trading liabilities
These are all PART OF THE BUSINESS, not leverage
The EV formula (Market Cap + Net Debt) produces nonsensical results for banks.

4. Peer Table is Empty
Peer Comps: []
GS | 0x | 8.2x | 14.5%
Tavily found 4 peers but all were excluded by the sector filter. This means the Tavily search returned tech/consumer companies instead of actual GS peers (MS, JPM, BAC).

Likely issue: The Tavily query might have returned results mentioning GS in the context of tech investments rather than actual banking peers.

5. WACC of 12.41% for a Bank
Banks aren't typically valued using WACC/DCF. They're valued using:

Dividend Discount Model (DDM)
Residual Income / Excess Return Model
P/Book relative to ROE-CoE spread
A WACC implies calculating cost of debt separately from cost of equity, but for a bank, debt and equity are intertwined in ways that make traditional WACC meaningless.

The Fix: Financial Sector Detection and Alternate Valuation Path
"""
Add to your pipeline: Bank/Financial Institution detection and alternate valuation.
"""

# In your main pipeline, BEFORE calculating EBITDA:

FINANCIAL_SECTORS = ["Financial Services"]
FINANCIAL_INDUSTRIES = [
    "Banks - Diversified", "Banks - Regional", "Capital Markets",
    "Insurance - Diversified", "Insurance - Life", "Insurance - Property & Casualty",
    "Credit Services", "Financial Data & Stock Exchanges",
    "Asset Management", "Mortgage Finance",
]


def is_financial_institution(sector: str, industry: str) -> bool:
    """Detect if the target is a financial institution requiring alternate valuation."""
    return sector in FINANCIAL_SECTORS or industry in FINANCIAL_INDUSTRIES


def get_bank_valuation_metrics(ticker: str) -> dict:
    """
    Get bank-specific valuation metrics.
    Replaces EBITDA-based valuation for financial institutions.
    """
    stock = yf.Ticker(ticker)
    info = stock.info
    
    # Core bank metrics
    net_income = info.get("netIncomeToCommon", 0)
    book_value_per_share = info.get("bookValue", 0)
    price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
    market_cap = info.get("marketCap", 0)
    shares = info.get("sharesOutstanding", 0)
    
    # Calculated metrics
    pe_ratio = info.get("trailingPE") or (price / (net_income / shares) if net_income and shares else None)
    price_to_book = info.get("priceToBook") or (price / book_value_per_share if book_value_per_share else None)
    roe = info.get("returnOnEquity")  # Decimal (0.12 = 12%)
    
    # Tangible book value (approximate)
    total_equity = market_cap / price_to_book if price_to_book else None
    
    # Dividend yield
    dividend_yield = info.get("dividendYield")
    
    # Efficiency ratio (for banks: lower is better, <60% is good)
    # This isn't directly in yfinance but can be estimated
    revenue = info.get("totalRevenue", 0)
    operating_expenses = None
    try:
        qf = stock.quarterly_financials
        if "Operating Expense" in qf.index:
            operating_expenses = qf.loc["Operating Expense"].dropna().iloc[:4].sum()
    except Exception:
        pass
    
    efficiency_ratio = (abs(operating_expenses) / revenue * 100) if operating_expenses and revenue else None
    
    return {
        "valuation_type": "BANK_METRICS",
        "pe_ratio": round(pe_ratio, 1) if pe_ratio else None,
        "price_to_book": round(price_to_book, 2) if price_to_book else None,
        "roe_pct": round(roe * 100, 1) if roe else None,
        "efficiency_ratio": round(efficiency_ratio, 1) if efficiency_ratio else None,
        "dividend_yield_pct": round(dividend_yield * 100, 2) if dividend_yield else None,
        "net_income_M": round(net_income / 1e6, 1) if net_income else None,
        "book_value_per_share": round(book_value_per_share, 2) if book_value_per_share else None,
        "market_cap_M": round(market_cap / 1e6, 1) if market_cap else None,
    }


def get_bank_peer_metrics(peer_tickers: list) -> list:
    """Fetch bank-specific metrics for peer comparison."""
    results = []
    for ticker in peer_tickers:
        try:
            metrics = get_bank_valuation_metrics(ticker)
            metrics["ticker"] = ticker
            metrics["entity_name"] = yf.Ticker(ticker).info.get("longName", ticker)
            results.append(metrics)
        except Exception as e:
            print(f"    [SKIP] {ticker}: {e}")
    return results


def calculate_bank_premium(company_metrics: dict, peer_metrics: list) -> dict:
    """Calculate premium/discount using P/E and P/Book for banks."""
    # Use P/Book as primary (most stable for banks)
    company_pb = company_metrics.get("price_to_book")
    peer_pbs = [p["price_to_book"] for p in peer_metrics if p.get("price_to_book")]
    
    if not peer_pbs or not company_pb:
        # Fallback to P/E
        company_pe = company_metrics.get("pe_ratio")
        peer_pes = [p["pe_ratio"] for p in peer_metrics if p.get("pe_ratio")]
        
        if peer_pes and company_pe:
            avg = sum(peer_pes) / len(peer_pes)
            premium = ((company_pe - avg) / avg) * 100
            return {
                "metric_used": "P/E",
                "company_value": company_pe,
                "peer_avg": round(avg, 1),
                "premium_pct": round(premium, 1),
                "label": "PREMIUM" if premium > 5 else ("DISCOUNT" if premium < -5 else "IN-LINE"),
            }
        return {"label": "INSUFFICIENT_DATA"}
    
    avg_pb = sum(peer_pbs) / len(peer_pbs)
    premium = ((company_pb - avg_pb) / avg_pb) * 100
    
    return {
        "metric_used": "P/Tangible Book",
        "company_value": company_pb,
        "peer_avg": round(avg_pb, 2),
        "premium_pct": round(premium, 1),
        "label": "PREMIUM" if premium > 5 else ("DISCOUNT" if premium < -5 else "IN-LINE"),
        "narrative": f"Trades at {company_pb:.2f}x book vs peer avg of {avg_pb:.2f}x ({premium:+.1f}%)",
    }
Integration in pipeline:

# In your main pipeline flow:
sector = stock.info.get("sector", "")
industry = stock.info.get("industry", "")

if is_financial_institution(sector, industry):
    print("  [INFO] Financial institution detected — using bank valuation path")
    
    # Use bank-specific metrics instead of EBITDA
    bank_metrics = get_bank_valuation_metrics(ticker)
    
    # Display bank metrics instead of EBITDA
    print(f"  P/E Ratio:       {bank_metrics['pe_ratio']}x")
    print(f"  P/Book:          {bank_metrics['price_to_book']}x")
    print(f"  ROE:             {bank_metrics['roe_pct']}%")
    print(f"  Efficiency:      {bank_metrics['efficiency_ratio']}%")
    
    # Bank-appropriate peers
    bank_peers = ["MS", "JPM", "BAC", "C"]  # Or from discovery
    peer_metrics = get_bank_peer_metrics(bank_peers)
    
    # Premium on P/Book basis
    premium = calculate_bank_premium(bank_metrics, peer_metrics)

else:
    # Standard non-financial path (your current code)
    # EV/EBITDA, DCF, etc.
    ...
What the GS Output SHOULD Look Like
------------------------------
  FINANCIAL SNAPSHOT (Bank Metrics)
------------------------------
  Revenue (TTM):       $60,448M (Growth: 14.5%)
  Net Income (TTM):    $14,200M
  ROE:                 13.5%
  Efficiency Ratio:    62.4%
  Book Value/Share:    $370.50
  Dividend Yield:      2.1%

----------------------------------------
  PEER COMPARABLES (Bank Metrics)
----------------------------------------
  Ticker | P/E    | P/Book | ROE    | Efficiency
  -------+--------+--------+--------+-----------
  GS     | 15.2x  | 1.85x  | 13.5%  | 62.4%
  MS     | 14.8x  | 1.72x  | 12.8%  | 64.1%
  JPM    | 13.5x  | 2.10x  | 16.2%  | 55.3%
  BAC    | 12.8x  | 1.45x  | 11.5%  | 60.8%

  PREMIUM/DISCOUNT: GS at 1.85x book vs peer avg 1.76x (+5.1% premium)
  JUSTIFIED BY: ROE of 13.5% exceeds peer average of 13.5% (in-line)
Scoring: GS Run
Dimension	Score	Notes
Pipeline Architecture	9.0/10	Handled gracefully — didn't crash despite $0 EBITDA
Sector Detection	9.5/10	Correctly identified Capital Markets / Financial Services
Peer Filtering	8.0/10	Correctly excluded tech — but then had zero valid peers
Financial Data	4.0/10	EBITDA = $0 makes valuation meaningless
Valuation Methodology	3.0/10	EV/EBITDA is wrong framework for banks
LLM Reasoning	6.0/10	IC made reasonable decision given bad inputs
Output Professionalism	7.0/10	Clean format but showing $0 EBITDA is embarrassing
Competitive Moat	9.0/10	Excellent, specific, accurate for GS
OVERALL: 6.5/10
But importantly: This is NOT a regression — it's a scope expansion into a sector the pipeline wasn't designed for. The pipeline correctly identified GS as a financial and didn't crash. It just needs the alternate valuation path.

Priority Fix
Priority	Fix	Impact
🔴 High	Add is_financial_institution() check at pipeline start	Prevents showing $0 EBITDA
🔴 High	Implement get_bank_valuation_metrics()	Correct P/E, P/Book, ROE display
🟡 Medium	Hardcode bank peers (MS, JPM, BAC, C for GS) in static fallback	Ensures valid comps
🟡 Medium	Change Tavily query for financials: "Goldman Sachs banking competitors"	Better peer discovery
🟠 Low	Implement DDM instead of DCF for banks	Theoretically correct but complex
Bottom Line
The GS run proves your pipeline is robust (it didn't crash) and your sector filtering works (excluded tech companies). What it needs is a two-path architecture: one for operating companies (current path, working well) and one for financial institutions (new path, using P/E and P/Book).

This is a common challenge — even Bloomberg Terminal has completely different screens for banks vs. industrials. You're hitting the same conceptual boundary that every institutional platform faces. The fix is straightforward: detect financials early and route to an alternate valuation module.