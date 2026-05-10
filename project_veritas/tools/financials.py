import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)
_FINANCIALS_CACHE = {}

FINANCIAL_SECTORS = ["Financial Services"]
FINANCIAL_INDUSTRIES = [
    "Banks - Diversified", "Banks - Regional", "Capital Markets",
    "Insurance - Diversified", "Insurance - Life", "Insurance - Property & Casualty",
    "Financial Data & Stock Exchanges",
    "Asset Management", "Mortgage Finance",
]

def is_financial_institution(info: dict) -> bool:
    """Detect if the target is a bank or insurance company requiring alternate valuation."""
    industry = info.get("industry", "")
    sector = info.get("sector", "")
    bank_keywords = ["Banks", "Capital Markets", "Insurance", "Financial Services", "Credit Services", "Asset Management"]
    
    # Failure 1 Fix: Explicitly check for Financial Services sector or key industries
    is_fin = any(kw in industry for kw in bank_keywords) or sector == "Financial Services"
    return is_fin

def _first_balance_sheet_value(bs: pd.DataFrame, names: List[str]) -> float:
    for name in names:
        if name in bs.index:
            vals = bs.loc[name].dropna()
            if len(vals) > 0:
                try:
                    return float(vals.iloc[0])
                except Exception:
                    continue
    return 0.0

def _sum_balance_sheet_values(bs: pd.DataFrame, names: List[str]) -> float:
    total = 0.0
    for name in names:
        total += _first_balance_sheet_value(bs, [name])
    return total

def _sector_beta_fallback(sector: str) -> float:
    return {
        "Financial Services": 1.1,
        "Technology": 1.2,
        "Healthcare": 0.9,
        "Consumer Defensive": 0.7,
        "Utilities": 0.5,
        "Energy": 1.0,
    }.get(sector, 1.0)

def calculate_cost_of_equity(beta: Optional[float], sector: str, country: str = "India") -> Dict:
    """Deterministic CAPM inputs for repeatable institutional output."""
    # Sector Beta Fallback (Damodaran 2025 normalized)
    beta_used = beta if beta is not None and 0.4 < beta < 2.5 else _sector_beta_fallback(sector)
    
    # Institutional Standards (Fixed for 2025-2026 cycle)
    if country in {"India", "IN", "NSE", "BSE"}:
        risk_free_rate = 7.10  # India 10Y Sovereign
        equity_risk_premium = 5.50
        country_risk_premium = 0.0 # Already built into India Rf
    else:
        risk_free_rate = 4.25  # US 10Y Treasury
        equity_risk_premium = 5.00
        country_risk_premium = 0.0

    coe = risk_free_rate + (beta_used * equity_risk_premium) + country_risk_premium
    return {
        "cost_of_equity_pct": round(coe, 2),
        "beta_used": round(beta_used, 3),
        "risk_free_rate_pct": risk_free_rate,
        "equity_risk_premium_pct": equity_risk_premium,
        "country_risk_premium_pct": country_risk_premium,
    }

def get_exchange_rate(from_currency: str, to_currency: str = "USD") -> float:
    """Fetch live exchange rate via yfinance."""
    if not from_currency or from_currency == to_currency:
        return 1.0
    
    ticker = f"{from_currency}{to_currency}=X"
    try:
        # Cache this if called frequently
        fx = yf.Ticker(ticker)
        rate = fx.info.get('regularMarketPrice') or fx.info.get('previousClose')
        if rate:
            return float(rate)
        
        # Fallback for common pairs if API fails
        fallbacks = {"CNYUSD": 0.14, "EURUSD": 1.08, "GBPUSD": 1.27, "INRUSD": 0.012}
        return fallbacks.get(f"{from_currency}{to_currency}", 1.0)
    except Exception as e:
        logger.warning(f"FX Fetch failed for {ticker}: {e}")
        return 1.0

def calculate_forensic_rubric(data: Dict) -> Dict:
    """
    FIX 8 & Failure 5: Programmatic Forensic Rubric with Bank Routing.
    """
    is_fin = data.get("is_financial", False)
    if is_fin:
        return calculate_bank_forensic_rubric(data)
        
    cash_score = 33
    margin_score = 33
    leverage_score = 34
    
    # 1. Cash Conversion (FCF / Net Income)
    fcf = data.get("fcf_M", 0) or 0
    ni = data.get("net_income_M", 0) or 0
    if ni > 0:
        ratio = fcf / ni
        if ratio < 0.5: 
            cash_score = 13
        elif ratio < 0.8:
            cash_score = 23
            
    # 2. Margin Safety (EBITDA Margin vs Industry)
    ebitda = data.get("ebitda_adj_M", 0) or 0
    rev = data.get("revenue_ttm_M", 0) or 0
    margin = (ebitda / rev * 100) if rev > 0 else 0
    if margin < 5:
        margin_score = 8
    elif margin < 12:
        margin_score = 23
        
    # 3. Leverage (Net Debt / EBITDA)
    debt = data.get("net_debt_M", 0) or 0
    if ebitda > 0:
        lev = debt / ebitda
        if lev > 5.0:
            leverage_score = 4
        elif lev > 3.5:
            leverage_score = 19
    elif debt > 0: 
        leverage_score = 0

    score = cash_score + margin_score + leverage_score
    details = {
        "cash_conversion": cash_score,
        "margin_safety": margin_score,
        "leverage_safety": leverage_score,
    }
    
    # Ensure mathematical parity
    total_score = sum(details.values())
    
    return {
        "score": max(0, total_score),
        "decomposition": details,
        "quality": "HIGH" if total_score > 80 else ("MODERATE" if total_score > 50 else "CRITICAL")
    }

def calculate_bank_forensic_rubric(data: Dict) -> Dict:
    """
    FAILURE 5 FIX: Forensic scoring for Financial Institutions.
    Uses Capital Adequacy and Earnings Quality instead of Leverage/Margins.
    """
    # 1. Earnings Quality (0-33): Fee vs Trading Revenue & Net Income Gap
    eq_score = 33
    ni = data.get("net_income_M", 0) or 0
    rev = data.get("revenue_ttm_M", 1) or 1
    roe = data.get("roe_pct", 10.0) or 10.0
    eff = data.get("efficiency_ratio", 65.0) or 65.0
    
    # Penalty if earnings seem unsustainably high or accounting is aggressive
    if roe > 30: eq_score -= 10
    if eff > 75: eq_score -= 10
    if eff < 30: eq_score -= 5 # Possibly distorted/incomplete data
    
    # 2. Capital Adequacy (0-33) - Proxy for CET1
    # For major banks, price_to_book < 0.6 often indicates asset quality concerns
    ca_score = 33
    pb = data.get("price_to_book", 1.0) or 1.0
    if pb < 0.5: ca_score = 10
    elif pb < 0.8: ca_score = 20
    elif pb > 4.0: ca_score -= 5 # Overvaluation risk
        
    # 3. Cost Discipline (0-34)
    # Bank Efficiency Ratio = Non-Interest Expense / Revenue. Lower is better.
    cd_score = 34
    if eff < 55: cd_score = 34
    elif eff < 65: cd_score = 28
    elif eff < 75: cd_score = 15
    else: cd_score = 5

    total = eq_score + ca_score + cd_score
    return {
        "score": total,
        "decomposition": {"earnings_quality": eq_score, "capital_adequacy": ca_score, "cost_discipline": cd_score},
        "quality": "HIGH" if total > 80 else ("MODERATE" if total > 50 else "CRITICAL")
    }

def get_sector_tier(data: Dict) -> int:
    """
    Classifies company into evaluation tiers:
    Tier 1: Banks/Insurance (P/B, ROE)
    Tier 2: Asset-Light/Networks (High Margin, Low CapEx)
    Tier 3: Tech/Growth (Rule of 40, High SBC)
    Tier 4: General Industrial (Standard EV/EBITDA)
    """
    is_fin = data.get("is_financial", False)
    gross_margin = data.get("gross_margin_pct", 0) or 0
    rev_growth = data.get("revenue_growth_pct", 0) or 0
    fcf_margin = data.get("fcf_margin_pct", 0) or 0
    sbc_rev = 0
    if data.get("sbc_M") and data.get("revenue_ttm_M") and data["revenue_ttm_M"] > 0:
        sbc_rev = (data["sbc_M"] / data["revenue_ttm_M"]) * 100

    # Tier 2: Asset Light Networks / High Quality (e.g. Visa, MA, Adobe)
    if gross_margin > 60 and fcf_margin > 20:
        return 2

    # Tier 1: Traditional Financials
    if is_fin:
        return 1

    # Tier 3: Growth / SBC Intensive (e.g. Palantir, Crowdstrike, NVDA)
    if rev_growth > 25 or sbc_rev > 8:
        return 3

    return 4

def get_quarterly_sum(df: pd.DataFrame, possible_names: list, quarters: int = 4) -> Optional[float]:
    """Helper to sum the last N quarters for a given metric."""
    if df.empty:
        return None
    for name in possible_names:
        if name in df.index:
            series = df.loc[name].dropna()
            if len(series) >= quarters:
                return float(series.iloc[:quarters].sum())
            elif len(series) > 0: # Handle newly IPO'd or missing data
                return float(series.sum() * (4.0 / len(series))) # Annualize
    return None

def get_ttm_revenue_and_growth(stock: yf.Ticker) -> Tuple[Optional[float], Optional[float]]:
    try:
        q_fin = stock.quarterly_financials
        if q_fin.empty:
            q_fin = stock.quarterly_income_stmt
        
        possible_names = [
            "Total Revenue Net of Interest Expense",
            "Total Revenue", 
            "Operating Revenue", 
            "Revenue", 
            "Total Operating Income", 
            "Net Interest Income", 
            "Interest Income"
        ]
        
        ttm_rev = get_quarterly_sum(q_fin, possible_names, 4)
        
        # Growth calculation from the previous 4 quarters
        prior_rev = None
        for name in possible_names:
            if name in q_fin.index:
                series = q_fin.loc[name].dropna()
                if len(series) >= 8:
                    prior_rev = float(series.iloc[4:8].sum())
                break
        
        growth = None
        if ttm_rev and prior_rev and prior_rev > 0:
            growth = ((ttm_rev - prior_rev) / prior_rev) * 100
            
        return ttm_rev, growth
    except Exception as e:
        print(f"    [WARNING] Error fetching revenue from yfinance: {e}")
        return None, None

def get_ttm_ebitda(stock: yf.Ticker) -> Optional[float]:
    try:
        q_fin = stock.quarterly_financials
        if q_fin.empty:
            q_fin = stock.quarterly_income_stmt
        return get_quarterly_sum(q_fin, ["EBITDA", "Normalized EBITDA"], 4)
    except:
        return None

def get_ttm_net_income(stock: yf.Ticker) -> Optional[float]:
    try:
        q_fin = stock.quarterly_financials
        if q_fin.empty:
            q_fin = stock.quarterly_income_stmt
        return get_quarterly_sum(q_fin, ["Net Income", "Net Income Common Stockholders"], 4)
    except:
        return None

def get_ttm_sbc(stock: yf.Ticker, ttm_rev_M: float = 0, mkt_cap_M: float = 0) -> float:
    """
    FIX 5: Robust SBC Extraction.
    Priority 1: Cash Flow Statement (Corrected sum logic)
    Priority 2: Income Statement (SG&A sub-item)
    Priority 3: Sector Floor Estimate (0.5% Rev) for Large Caps
    """
    sbc_val = 0.0
    try:
        # CF Statement Check
        q_cf = stock.quarterly_cashflow
        if not q_cf.empty:
            cf_names = ["Stock Based Compensation", "Share Based Compensation", "Stock-Based Compensation", "Common Stock Issuance"]
            sbc_val = get_quarterly_sum(q_cf, cf_names, 4) or 0.0
        
        # IS Statement Check if CF failed
        if sbc_val <= 0:
            q_is = stock.quarterly_income_stmt
            if not q_is.empty:
                is_names = ["Share Based Compensation", "Stock Based Compensation"]
                sbc_val = get_quarterly_sum(q_is, is_names, 4) or 0.0
            
    except Exception as e:
        logger.debug(f"SBC extraction error: {e}")

    # Sanity Check for Large Caps (Fix 5 specification)
    # If Large Cap (> $20B) and sbc is suspiciously low (< 0.1% of rev), apply floor
    if mkt_cap_M > 20000:
        floor = (ttm_rev_M * 1e6) * 0.005 
        if sbc_val < floor * 0.1:
            sbc_val = floor
            logger.info(f"[FIX 5] SBC suspiciously low for Large Cap. Applying 0.5% Rev Floor: ${sbc_val/1e6:,.1f}M")
        
    return sbc_val

def get_ttm_fcf_and_margin(stock: yf.Ticker, ttm_rev: float) -> Tuple[Optional[float], Optional[float]]:
    try:
        q_cf = stock.quarterly_cashflow
        ocf = get_quarterly_sum(q_cf, ["Operating Cash Flow", "Total Cash From Operating Activities", "Cash Flow From Continuing Operating Activities"], 4)
        capex = get_quarterly_sum(q_cf, ["Capital Expenditure", "Capital Expenditures"], 4)
        
        if ocf is not None and capex is not None:
            # Note: capex is usually negative in yfinance
            fcf = ocf + capex if capex < 0 else ocf - capex
            margin = (fcf / ttm_rev) * 100 if ttm_rev and ttm_rev > 0 else None
            return fcf, margin
        return None, None
    except:
        return None, None

def get_financials_summary(ticker: str) -> Dict:
    """
    FIX 1: Currency Normalization.
    Detects financialCurrency vs trading currency and normalizes all to USD.
    """
    cache_key = ticker.upper()
    if cache_key in _FINANCIALS_CACHE:
        return dict(_FINANCIALS_CACHE[cache_key])

    stock = yf.Ticker(ticker)
    info = stock.info
    if not info or ('symbol' not in info and 'ticker' not in info):
        logger.error(f"yfinance returned no data for ticker {ticker}")
        return {}
    
    # 1. Currency Detection & FX Rate
    reporting_curr = info.get("financialCurrency", "USD")
    trading_curr = info.get("currency", "USD")
    fx_rate = 1.0
    
    if reporting_curr != "USD":
        fx_rate = get_exchange_rate(reporting_curr, "USD")
        logger.info(f"[FIX 1] Normalizing {reporting_curr} to USD (Rate: {fx_rate:.4f})")

    # 2. Extract Base Data (All yfinance fundamentals are usually in reporting_curr)
    ttm_rev, growth = get_ttm_revenue_and_growth(stock)
    ebitda = get_ttm_ebitda(stock)
    net_income = get_ttm_net_income(stock)
    market_cap = info.get('marketCap') # MC is usually in trading_curr
    
    # Adjust MC if trading_curr is not USD
    if trading_curr != "USD":
        mc_fx = get_exchange_rate(trading_curr, "USD")
        if market_cap: market_cap *= mc_fx

    market_cap_M = market_cap / 1e6 if market_cap else 0
    sbc = get_ttm_sbc(stock, ttm_rev_M=(ttm_rev/1e6 if ttm_rev else 0), mkt_cap_M=market_cap_M)
    
    if not ttm_rev:
        ttm_rev = info.get('totalRevenue')
    if not ebitda:
        ebitda = info.get('ebitda')
        
    # FIX 16: Growth Rate Computation Hardening
    if not growth:
        raw_growth = info.get('revenueGrowth')
        growth = raw_growth * 100 if raw_growth else None
        
    fcf, fcf_margin = None, None
    if ttm_rev:
        fcf, fcf_margin = get_ttm_fcf_and_margin(stock, ttm_rev)
    
    # Fallback fcf
    if not fcf:
        fcf = info.get('freeCashflow')
        if fcf and ttm_rev:
            fcf_margin = (fcf / ttm_rev) * 100
            
    # 3. Apply FX Normalization to Reporting Currency items
    if fx_rate != 1.0:
        if ttm_rev: ttm_rev *= fx_rate
        if ebitda: ebitda *= fx_rate
        if net_income: net_income *= fx_rate
        if sbc: sbc *= fx_rate
        if fcf: fcf *= fx_rate

    adj_ebitda = None
    if ebitda is not None:
        adj_ebitda = ebitda - sbc
        
    ev = info.get('enterpriseValue')
    # FIX 1 Hardening: For foreign ADRs like BABA, EV is often in financialCurrency (CNY)
    # even if Market Cap is in USD.
    if ev and reporting_curr != "USD" and ev > market_cap * 3:
        logger.info(f"[FIX 1] Detected EV in {reporting_curr}. Normalizing to USD.")
        ev *= fx_rate
    elif trading_curr != "USD" and ev:
        ev *= mc_fx 
        
    long_name = info.get('longName', ticker)
    
    # Deriving Net Debt
    net_debt = 0.0
    if ev is not None and market_cap is not None:
        net_debt = ev - market_cap
    
    # Calculate Gross Margin
    gross_margin_pct = None
    if ttm_rev and ttm_rev > 0:
        gross_profit = info.get('grossProfits')
        if gross_profit and fx_rate != 1.0: gross_profit *= fx_rate
        
        if not gross_profit:
             try:
                q_fin = stock.quarterly_financials
                if q_fin.empty: q_fin = stock.quarterly_income_stmt
                gp = get_quarterly_sum(q_fin, ["Gross Profit"], 4)
                if gp: 
                    gp *= fx_rate
                    gross_margin_pct = (gp / ttm_rev) * 100
             except:
                pass
        else:
            gross_margin_pct = (gross_profit / ttm_rev) * 100
    
    industry = info.get('industry', 'default')
    sector = info.get('sector', 'default')
    is_fin = is_financial_institution(info)

    # FIX 7/B1: Comprehensive debt override, with financial-institution fields.
    total_debt_M = None
    total_liabilities_M = None
    debt_data_gap = False
    try:
        bs = stock.balance_sheet
        if not bs.empty:
            debt_fields = [
                "Total Debt",
                "Long Term Debt",
                "Short Long Term Debt",
                "Short Term Borrowings",
                "Current Debt",
                "Current Long Term Debt",
                "Long Term Debt And Capital Lease Obligation",
                "Long Term Debt And Finance Lease Obligation",
                "Commercial Paper",
                "Other Borrowed Funds",
                "Federal Funds Purchased And Securities Sold Under Agreement To Repurchase",
            ]
            total_debt = _first_balance_sheet_value(bs, ["Total Debt"])
            if total_debt <= 0:
                total_debt = _sum_balance_sheet_values(bs, debt_fields[1:])
            
            cash = _first_balance_sheet_value(bs, [
                "Cash And Cash Equivalents",
                "Cash Cash Equivalents And Short Term Investments",
            ])
            total_assets = _first_balance_sheet_value(bs, ["Total Assets"])
            total_equity = _first_balance_sheet_value(bs, [
                "Stockholders Equity",
                "Total Equity Gross Minority Interest",
                "Common Stock Equity",
            ])
            total_liabilities = _first_balance_sheet_value(bs, ["Total Liabilities Net Minority Interest"])
            if total_liabilities <= 0 and total_assets > 0 and total_equity > 0:
                total_liabilities = total_assets - total_equity
            total_debt_M = (total_debt * fx_rate) / 1e6 if total_debt else 0.0
            total_liabilities_M = (total_liabilities * fx_rate) / 1e6 if total_liabilities else 0.0
            if is_fin and total_debt_M <= 0:
                debt_data_gap = True
            
            bs_net_debt = (total_debt - cash) * fx_rate
            if not is_fin and (bs_net_debt > net_debt * 1.1 or net_debt == 0):
                logger.info(f"[FIX 7] BS Override: Net Debt ${bs_net_debt/1e6:,.0f}M (vs EV-derived ${net_debt/1e6:,.0f}M)")
                net_debt = bs_net_debt
                if market_cap: ev = market_cap + net_debt
    except Exception as e:
        logger.warning(f"Failed to calculate comprehensive Net Debt: {e}")
        
    shares = info.get('impliedSharesOutstanding') or info.get('sharesOutstanding')
    price = info.get('currentPrice') or info.get('regularMarketPrice')
    # Price is in trading currency, convert to USD
    if trading_curr != "USD" and price:
        price *= mc_fx

    # Financial-specific metrics
    pe_ratio = info.get('trailingPE')
    price_to_book = info.get('priceToBook')
    roe = info.get('returnOnEquity')
    div_yield = info.get('dividendYield')
    book_value = info.get('bookValue')
    beta = info.get('beta')
    coe_details = calculate_cost_of_equity(beta, sector, info.get("country", "United States"))
    if book_value and fx_rate != 1.0: book_value *= fx_rate
    
    ev = info.get('enterpriseValue') or 0
    market_cap = info.get('marketCap') or 0
    
    # ADR Guardrail: yfinance sometimes reports EV in local currency while Market Cap is USD
    # If EV is > 5x Market Cap for a non-USD currency or known ADR, force re-computation
    if ev > 5 * market_cap and market_cap > 0:
        logger.warning(f"Suspect EV detected for {ticker}. Re-computing from Market Cap + Net Debt.")
        ev = market_cap + net_debt

    # Failure 5 Fix: Proper Efficiency Ratio for Banks
    efficiency_ratio = None
    if is_fin:
        try:
            total_rev = ttm_rev or info.get('totalRevenue') or 1
            q_fin = stock.quarterly_financials
            if q_fin.empty:
                q_fin = stock.quarterly_income_stmt
            
            # Banking Standard: Efficiency Ratio = Non-Interest Expense / (Net Interest Income + Non-Interest Income)
            # yfinance 'Total Revenue' for banks is often already Net of Interest Expense.
            non_int_exp_names = [
                "Non Interest Expense",
                "Operating Expense",
                "Total Operating Expenses",
                "Selling General And Administration",
            ]
            op_exp = get_quarterly_sum(q_fin, non_int_exp_names, 4) or \
                     info.get('totalOperatingExpenses') or \
                     info.get('nonInterestExpense') or \
                     info.get('sellingGeneralAdministrative') or 0
            
            if op_exp > 0 and total_rev > 0:
                efficiency_ratio = (op_exp / total_rev) * 100
                # Sanity check: Efficiency ratios typically range from 45% to 75% for healthy banks
                if efficiency_ratio < 20 or efficiency_ratio > 110:
                    efficiency_ratio = None 
        except Exception as e:
            logger.warning(f"Efficiency Ratio calculation failed: {e}")
            
    # Failure 1 Fix: Suppress EV/EBITDA and Net Debt for Banks
    if is_fin:
        ev = None
        net_debt = None
        ebitda = None
        adj_ebitda = None

    summary = {
        "ticker": ticker,
        "is_financial": is_fin,
        "revenue_ttm_M": ttm_rev / 1e6 if ttm_rev else None,
        "revenue_growth_pct": growth,
        "ebitda_reported_M": ebitda / 1e6 if ebitda else None,
        "ebitda_adj_M": adj_ebitda / 1e6 if adj_ebitda else None,
        "sbc_M": sbc / 1e6,
        "fcf_M": fcf / 1e6 if fcf else None,
        "fcf_margin_pct": fcf_margin,
        "market_cap_M": market_cap / 1e6 if market_cap else None,
        "enterprise_value_M": ev / 1e6 if ev else None,
        "net_debt_M": net_debt / 1e6 if net_debt else 0.0,
        "ev_ebitda": (ev / adj_ebitda) if (ev and adj_ebitda and adj_ebitda > 0) else None,
        "shares_outstanding_M": shares / 1e6 if shares else None,
        "current_price": price,
        "industry": industry,
        "sector": sector,
        "net_income_M": net_income / 1e6 if net_income else None,
        "long_name": long_name,
        "ev_rev": (ev / ttm_rev) if (ev and ttm_rev and ttm_rev > 0) else None,
        "pe_ratio": pe_ratio,
        "price_to_book": price_to_book,
        "roe_pct": roe * 100 if (roe and abs(roe) < 1.0) else (roe if roe else None),
        "div_yield_pct": div_yield if div_yield else None,
        "beta": beta,
        "cost_of_equity_pct": coe_details["cost_of_equity_pct"],
        "cost_of_equity_components": coe_details,
        "book_value_ps": book_value,
        "efficiency_ratio": efficiency_ratio,
        "total_debt_M": total_debt_M,
        "total_liabilities_M": total_liabilities_M,
        "debt_data_gap": debt_data_gap,
        "gross_margin_pct": gross_margin_pct,
        "currency": "USD"
    }

    # Add Forensic Rubric
    rubric = calculate_forensic_rubric(summary)
    summary["forensic_score"] = rubric["score"]
    summary["forensic_decomposition"] = rubric["decomposition"]
    summary["quality_of_earnings"] = rubric["quality"]

    _FINANCIALS_CACHE[cache_key] = dict(summary)
    return summary
