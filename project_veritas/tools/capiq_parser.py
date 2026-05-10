import os
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Mapping yfinance sectors to the CapIQ filename suffix
SECTOR_TO_CAPIQ_FILE = {
    "Technology": "it",
    "Healthcare": "healthcare",
    "Financial Services": "financials",
    "Consumer Cyclical": "consumer discretionary",
    "Consumer Defensive": "consumer staples",
    "Energy": "energy",
    "Industrials": "industrials",
    "Basic Materials": "materials",
    "Real Estate": "real estate",
    "Utilities": "utilities",
    "Communication Services": "communication"
}

INDUSTRY_TO_CAPIQ_FILE = {
    "Credit Services": "financials",
    "Capital Markets": "financials",
    "Banks - Diversified": "financials",
    "Banks - Regional": "financials",
    "Banks—Diversified": "financials",
    "Banks—Regional": "financials",
    "Insurance - Diversified": "financials",
    "Insurance - Life": "financials",
    "Asset Management": "financials",
    "Financial Data & Stock Exchanges": "financials",
    "Internet Retail": "consumer discretionary",
    "Internet Content & Information": "communication",
    "Software - Application": "it",
    "Software - Infrastructure": "it",
    "Software—Application": "it",
    "Software—Infrastructure": "it",
    "Semiconductors": "it",
    "Information Technology Services": "it",
    "Electronic Gaming & Multimedia": "communication",
    "Drug Manufacturers - General": "healthcare",
    "Drug Manufacturers—General": "healthcare",
    "Medical Devices": "healthcare",
    "Health Information Services": "healthcare",
    "Biotechnology": "healthcare",
    "Auto Manufacturers": "consumer discretionary",
    "Restaurants": "consumer discretionary",
    "Specialty Retail": "consumer discretionary",
    "Packaged Foods": "consumer staples",
    "Beverages - Non-Alcoholic": "consumer staples",
    "Aerospace & Defense": "industrials",
    "Airlines": "industrials",
    "Railroads": "industrials",
    "Oil & Gas Integrated": "energy",
    "Oil & Gas E&P": "energy",
    "Telecom Services": "communication",
    "Entertainment": "communication",
    "Utilities - Regulated Electric": "utilities",
    "REIT - Diversified": "real estate",
    "Real Estate Services": "real estate",
    "Gold": "materials",
    "Steel": "materials",
    "Specialty Chemicals": "materials",
}

class CapIQParser:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.public_comps_dir = self.data_dir / "capiq" / "public_comps" / "global_peers"
        self.transactions_dir = self.data_dir / "capiq" / "precedent_transactions" / "global_transactions"

    def _get_file_for_sector(self, sector: str, mode: str = "comps") -> Path:
        """Resolves the correct CapIQ file based on sector and mode."""
        suffix = INDUSTRY_TO_CAPIQ_FILE.get(sector) or SECTOR_TO_CAPIQ_FILE.get(sector)
        if not suffix:
            normalized = str(sector).replace("—", "-").lower()
            suffix = SECTOR_TO_CAPIQ_FILE.get(str(sector).title())
            if not suffix:
                suffix = normalized if normalized in {
                    "financials", "it", "healthcare", "health care", "consumer discretionary",
                    "consumer staples", "industrials", "energy", "communication", "utilities",
                    "real estate", "materials"
                } else "it"
        if suffix == "health care":
            suffix = "healthcare"
        if mode == "comps":
            return self.public_comps_dir / f"global_{suffix}_peers.xlsx"
        else:
            return self.transactions_dir / f"global_ma_{suffix}_transactions.xlsx"

    def get_peer_comps(self, sector: str, limit: int = 10) -> list:
        """
        FIX 10: CapIQ Trading Comps.
        """
        file_path = self._get_file_for_sector(sector, "comps")
        if not file_path.exists():
            logger.warning(f"CapIQ file not found: {file_path}")
            return []

        try:
            df = pd.read_excel(file_path, header=2)
            df.columns = [str(c).strip().replace('\n', ' ') for c in df.columns]
            
            comps = []
            if 'Entity Name' in df.columns:
                df = df.dropna(subset=['Entity Name'])
                
                # Use LTM multiples if available
                mult_col = 'Total Enterprise Value/ LTM EBITDA (x)'
                if mult_col not in df.columns:
                    mult_col = 'Total Enterprise Value/ EBITDA (x)'
                
                # Market Cap col for sorting
                mcap_col = 'Market Capitalization ($M)'
                if mcap_col in df.columns:
                    df[mcap_col] = pd.to_numeric(df[mcap_col], errors='coerce')
                    df = df.sort_values(by=mcap_col, ascending=False)

                for _, row in df.iterrows():
                    if len(comps) >= limit: break
                    
                    val = row.get(mult_col)
                    if pd.notna(val) and isinstance(val, (int, float)) and val > 0:
                        comps.append({
                            "ticker": str(row.get('Ticker', row.get('Entity Name', ''))).split(':')[-1].upper(),
                            "entity_name": row.get('Entity Name'),
                            "ev_ebitda": f"{round(val, 1)}x",
                            "raw_ev_ebitda": float(val),
                            "market_cap": row.get(mcap_col, 0)
                        })
            return comps
        except Exception as e:
            logger.error(f"Error parsing CapIQ Comps: {e}")
            return []

    def get_precedent_transactions(self, sector: str, limit: int = 10) -> list:
        """
        FIX 10: CapIQ Precedent Transactions.
        """
        file_path = self._get_file_for_sector(sector, "transactions")
        if not file_path.exists():
            logger.warning(f"CapIQ Transactions file not found: {file_path}")
            return []

        try:
            df = pd.read_excel(file_path, header=2)
            df.columns = [str(c).strip().replace('\n', ' ') for c in df.columns]
            
            txns = []
            # CapIQ Transaction headers
            target_col = next((c for c in df.columns if "Target" in c and ("Name" in c or "Issuer" in c)), None)
            date_col = next((c for c in df.columns if "Announced Date" in c), "Announced Date")
            value_col = next((c for c in df.columns if "Transaction Value" in c and "($M)" in c), None)
            mult_col = next((c for c in df.columns if "EBITDA" in c and "(x)" in c), None)
            
            if target_col in df.columns:
                df = df.dropna(subset=[target_col])
                df = df[~df[target_col].astype(str).str.startswith("SPTR_", na=False)]
                
                # Relevance Filter (P0 Fix 1): Simple keyword inclusion if possible
                # We can use the sector/industry name to prioritize
                target_keywords = str(sector).lower().split(' ')
                
                # Prioritization: Transactions with disclosed multiples first
                df['has_multiple'] = df[mult_col].notna() if mult_col else False
                if not df['has_multiple'].any():
                    # Check for P/BV if EV/EBITDA is missing (Financials)
                    pbv_col = next((c for c in df.columns if "Price/ Book Value" in c or "P/BV" in c), None)
                    if pbv_col:
                        df['has_multiple'] = df[pbv_col].notna()
                        mult_col = pbv_col
                
                # Sort by has_multiple (True first), then Date
                sort_cols = ['has_multiple']
                if date_col in df.columns:
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                    sort_cols.append(date_col)
                
                df = df.sort_values(by=sort_cols, ascending=[False, False])

                for _, row in df.iterrows():
                    if len(txns) >= limit: break
                    
                    val = row.get(mult_col) if mult_col else None
                    value_m = row.get(value_col, 0) if value_col else 0
                    
                    # Multiple Label
                    mult_label = "EV/EBITDA"
                    if mult_col and "Book" in mult_col:
                        mult_label = "P/Book"
                    
                    if pd.notna(row.get(target_col)):
                        txns.append({
                            "target": row.get(target_col),
                            "acquirer": row.get('Acquirer Name') or row.get('Buyers/Investors Name', 'Undisclosed'),
                            "date": row.get(date_col).strftime('%Y-%m-%d') if pd.notna(row.get(date_col)) else 'N/A',
                            "ev_ebitda": f"{round(float(val), 1)}x" if pd.notna(val) and isinstance(val, (int, float)) and val > 0 else "N/A",
                            "raw_ev_ebitda": float(val) if pd.notna(val) and isinstance(val, (int, float)) else None,
                            "value_M": float(value_m) if pd.notna(value_m) and isinstance(value_m, (int, float)) else 0,
                            "mult_label": mult_label
                        })
            return txns
        except Exception as e:
            logger.error(f"Error parsing CapIQ Transactions: {e}")
            return []

if __name__ == "__main__":
    # Test the parser
    # Assume script is run from project root
    parser = CapIQParser(data_dir="data")
    print("Testing CapIQ Parser for 'Technology' sector...")
    comps = parser.get_peer_comps("Technology", limit=3)
    for c in comps:
        print(f"  {c['entity_name']}: EV/EBITDA = {c['ev_ebitda']}")
