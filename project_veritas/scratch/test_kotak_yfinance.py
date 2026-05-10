import sys
import os

# Set project path
PROJECT_ROOT = r'c:\Users\Moosa\Downloads\Project_Veritas'
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import yfinance as yf
from project_veritas.memory.market_data_loader import fetch_indian_market_data

def safe_print(text):
    """Safely print text by stripping non-ASCII characters."""
    try:
        print(text.encode('ascii', 'ignore').decode('ascii'))
    except:
        pass

def test_kotak():
    ticker = "KOTAKBANK.NS"
    
    safe_print("=" * 70)
    safe_print(f" TESTING YFINANCE - {ticker}")
    safe_print("=" * 70)
    
    # 1. Basic Stock Info (using our loader)
    data = fetch_indian_market_data(ticker)
    if data:
        safe_print("\n[BASIC INFO & OVERVIEW]")
        for k, v in data.items():
            safe_print(f"  {k:20s}: {v}")
    
    # 2. In-depth Data from Ticker object
    stock = yf.Ticker(ticker)
    
    safe_print("\n[BUSINESS SUMMARY]")
    summary = stock.info.get('longBusinessSummary', 'N/A')
    safe_print(summary[:1000] + "...")
    
    safe_print("\n[RECENT NEWS/OPINIONS]")
    news = stock.news
    if news:
        for i, item in enumerate(news[:5], 1):
            safe_print(f"  {i}. {item.get('title')}")
            safe_print(f"     Source: {item.get('publisher')}")
            safe_print(f"     Link:   {item.get('link')}")
    else:
        safe_print("  No recent news found.")
        
    safe_print("\n[ANALYST RECOMMENDATIONS]")
    try:
        recs = stock.recommendations
        if recs is not None and not recs.empty:
            safe_print(recs.tail(5).to_string())
        else:
            safe_print("  No recent analyst recommendations available for this ticker.")
    except:
        safe_print("  Could not retrieve recommendations.")

    safe_print("\n" + "=" * 70)

if __name__ == "__main__":
    test_kotak()
