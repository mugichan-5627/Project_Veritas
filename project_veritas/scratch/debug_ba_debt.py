import yfinance as yf
ticker = "BA"
stock = yf.Ticker(ticker)
info = stock.info
print(f"Ticker: {ticker}")
print(f"Market Cap: {info.get('marketCap')}")
print(f"Enterprise Value: {info.get('enterpriseValue')}")
print(f"Total Debt: {info.get('totalDebt')}")
print(f"Total Cash: {info.get('totalCash')}")
print(f"EV - Market Cap: {info.get('enterpriseValue') - info.get('marketCap') if info.get('enterpriseValue') and info.get('marketCap') else 'N/A'}")
print(f"Debt - Cash: {info.get('totalDebt') - info.get('totalCash') if info.get('totalDebt') and info.get('totalCash') else 'N/A'}")
