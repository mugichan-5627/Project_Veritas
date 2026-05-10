import yfinance as yf
ticker = "BA"
stock = yf.Ticker(ticker)
bs = stock.balance_sheet
print(bs.index)
print(bs.iloc[:, 0]) # Last quarter
