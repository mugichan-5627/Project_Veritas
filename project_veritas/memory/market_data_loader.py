def fetch_indian_market_data(ticker: str) -> dict | None:
    """
    Fetches real-time market data for Indian listed companies
    using yfinance (Yahoo Finance).
    
    Ticker format:
      NSE: "MANKIND.NS"
      BSE: "MANKIND.BO"
    
    Use case: fills market cap and current price gaps
    when CapIQ data is stale or unavailable.
    No API key required.
    """
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or info.get("regularMarketPrice") is None:
            print(f"YFINANCE: No data for {ticker}")
            return None
        
        # Convert to Rs Crores where applicable
        # Yahoo returns absolute numbers in Rs
        market_cap_cr = (
            info.get("marketCap", 0) / 10_000_000
        )  # Rs to Rs Crores
        
        result = {
            "name":           info.get("longName"),
            "sector":         info.get("sector"),
            "industry":       info.get("industry"),
            "current_price":  info.get("regularMarketPrice"),
            "market_cap_cr":  round(market_cap_cr, 2),
            "pe_ratio":       info.get("trailingPE"),
            "ev_ebitda":      info.get("enterpriseToEbitda"),
            "ev_revenue":     info.get("enterpriseToRevenue"),
            "beta":           info.get("beta"),
            "52_week_high":   info.get("fiftyTwoWeekHigh"),
            "52_week_low":    info.get("fiftyTwoWeekLow"),
            "revenue_ttm_cr": round(
                info.get("totalRevenue", 0) / 10_000_000, 2
            ),
            "ebitda_cr":      round(
                info.get("ebitda", 0) / 10_000_000, 2
            ) if info.get("ebitda") else None
        }
        
        # Remove None values
        result = {k: v for k, v in result.items() 
                  if v is not None}
        
        print(f"YFINANCE: {result.get('name','Unknown')} [OK]")
        print(f"  Market Cap: Rs {result.get('market_cap_cr','N/A')} Cr")
        print(f"  EV/EBITDA:  {result.get('ev_ebitda','N/A')}x")
        print(f"  Beta:       {result.get('beta','N/A')}")
        
        return result
        
    except Exception as e:
        print(f"YFINANCE: Failed for {ticker} — {e}")
        return None
