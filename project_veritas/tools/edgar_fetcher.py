import os
import requests
import json
from datetime import datetime

# The SEC requires a User-Agent in the format: "Your Name (your@email.com)"
SEC_HEADERS = {
    "User-Agent": "ProjectVeritas_ResearchAgent (research@projectveritas.ai)"
}

class EdgarFetcher:
    def __init__(self):
        self.ticker_to_cik = {}
        self._load_tickers()

    def _load_tickers(self):
        """Loads the SEC mapping of Tickers to CIKs."""
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers=SEC_HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for key, val in data.items():
                    # SEC CIKs must be 10 digits zero-padded for the companyfacts endpoint
                    self.ticker_to_cik[val['ticker'].upper()] = str(val['cik_str']).zfill(10)
        except Exception as e:
            print(f"[!] EDGAR Fetcher Initialization failed: {e}")

    def get_cik(self, ticker: str) -> str:
        return self.ticker_to_cik.get(ticker.upper())

    def fetch_company_facts(self, ticker: str) -> dict:
        """Fetches the massive JSON block of all XBRL facts ever reported by the company."""
        cik = self.get_cik(ticker)
        if not cik:
            return None

        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        try:
            response = requests.get(url, headers=SEC_HEADERS, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def get_latest_annual_financials(self, ticker: str) -> dict:
        """
        Attempts to extract the most recent 10-K (Annual) financial metrics from the SEC.
        Returns USD Millions.
        """
        facts = self.fetch_company_facts(ticker)
        if not facts:
            return None

        try:
            us_gaap = facts.get("facts", {}).get("us-gaap", {})
            
            def get_latest_10k_value(tag_name):
                # Safely search for the XBRL tag
                if tag_name not in us_gaap:
                    return None
                
                units = us_gaap[tag_name].get("units", {})
                if "USD" not in units:
                    return None
                
                # Filter for annual filings (10-K) and get the most recent one. Frame must be strictly 6 chars (e.g. CY2024)
                reports = units["USD"]
                annuals = [r for r in reports if r.get("form") == "10-K" and r.get("frame", "").startswith("CY") and len(r.get("frame", "")) == 6]
                if not annuals:
                    # Fallback to the most recent 10-K value that represents a full year (usually ends with Q4)
                    annuals = [r for r in reports if r.get("form") == "10-K"]
                
                if not annuals:
                    return None
                    
                # Sort by end date
                annuals.sort(key=lambda x: x.get("end", ""), reverse=True)
                latest = annuals[0]
                
                # Convert to millions
                val = latest.get("val", 0)
                return val / 1000000.0

            # SEC XBRL tags vary, so we check multiple common tags
            revenue = get_latest_10k_value("Revenues") or get_latest_10k_value("SalesRevenueNet") or get_latest_10k_value("RevenueFromContractWithCustomerExcludingAssessedTax")
            net_income = get_latest_10k_value("NetIncomeLoss")
            assets = get_latest_10k_value("Assets")
            liabilities = get_latest_10k_value("Liabilities")
            operating_income = get_latest_10k_value("OperatingIncomeLoss")
            
            # Stock-based compensation
            sbc = get_latest_10k_value("ShareBasedCompensation") or get_latest_10k_value("AllocatedShareBasedCompensationExpense") or 0.0

            if revenue is None:
                return None # Failed to find core metrics
                
            return {
                "source": "SEC EDGAR (10-K)",
                "revenue_m": revenue,
                "net_income_m": net_income,
                "total_assets_m": assets,
                "total_liabilities_m": liabilities,
                "operating_income_m": operating_income,
                "sbc_expense_m": sbc
            }
        except Exception as e:
            print(f"[!] Error parsing SEC EDGAR JSON: {e}")
            return None

if __name__ == "__main__":
    fetcher = EdgarFetcher()
    print("Testing EDGAR Fetcher with AAPL...")
    data = fetcher.get_latest_annual_financials("AAPL")
    if data:
        print("Success! Latest 10-K Data:")
        for k, v in data.items():
            print(f"  {k}: {v}")
    else:
        print("Failed to fetch data.")
