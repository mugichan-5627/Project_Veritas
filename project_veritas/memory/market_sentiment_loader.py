import yfinance as yf

def fetch_analyst_sentiment(ticker: str) -> dict | None:
    """
    Fetches analyst recommendations and news using yfinance.
    """
    try:
        stock = yf.Ticker(ticker)
        recs = stock.recommendations
        
        buy = hold = sell = 0
        consensus = "Hold"
        
        if recs is not None and not recs.empty:
            # yfinance returns a dataframe with periods (0m, -1m, etc.)
            # Just take the latest row (0m usually)
            latest = recs.iloc[0]
            buy = int(latest.get('strongBuy', 0) + latest.get('buy', 0))
            hold = int(latest.get('hold', 0))
            sell = int(latest.get('sell', 0) + latest.get('strongSell', 0))
            
            if buy > hold and buy > sell:
                consensus = "Buy"
            elif sell > buy and sell > hold:
                consensus = "Sell"
                
        info = stock.info
        summary = info.get("longBusinessSummary", "")
        
        news_items = stock.news
        recent_news = [n.get("title") for n in news_items[:3]] if news_items else []
        
        return {
            "buy_count": buy,
            "hold_count": hold,
            "sell_count": sell,
            "consensus": consensus,
            "business_summary": summary,
            "recent_news": recent_news
        }
    except Exception as e:
        print(f"SENTIMENT: Failed for {ticker} — {e}")
        return None
