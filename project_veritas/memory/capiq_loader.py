"""
capiq_loader.py
Project Veritas — CapIQ Data Interface for Agents

Loads cleaned transaction CSVs and raw public comp xlsx files via Pandas.
Agents call this module for all valuation data.

Global files only — India-only files removed (May 2026).
India adjustment applied via Damodaran country risk premium (15% discount).

Author: Moosa (Project Veritas)
Date: May 2026
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(r"C:\Users\Moosa\Downloads\Project_Veritas\data\capiq")
TRANSACTIONS_CLEAN_DIR = BASE_DIR / "precedent_transactions" / "clean"
PUBLIC_COMPS_DIR = BASE_DIR / "public_comps"

# Country risk discount for India (Damodaran ctrypremJuly25 derived)
# Applied when returning India-adjusted multiples
INDIA_DISCOUNT = 0.15  # 15%

# ============================================================
# SECTOR MAPPING
# Maps user/agent input → file naming convention
# ============================================================

SECTOR_MAP = {
    "energy": "energy",
    "oil": "energy",
    "oil & gas": "energy",
    "materials": "materials",
    "chemicals": "materials",
    "metals": "materials",
    "industrials": "industrials",
    "industrial": "industrials",
    "manufacturing": "industrials",
    "consumer discretionary": "consumer discretionary",
    "retail": "consumer discretionary",
    "auto": "consumer discretionary",
    "consumer staples": "consumer staples",
    "fmcg": "consumer staples",
    "food": "consumer staples",
    "healthcare": "healthcare",
    "health care": "healthcare",
    "pharma": "healthcare",
    "pharmaceuticals": "healthcare",
    "hospital": "healthcare",
    "financials": "financials",
    "banking": "financials",
    "insurance": "financials",
    "nbfc": "financials",
    "it": "it",
    "information technology": "it",
    "technology": "it",
    "software": "it",
    "communication": "communication",
    "communication services": "communication",
    "telecom": "communication",
    "media": "communication",
    "utilities": "utilities",
    "power": "utilities",
    "electricity": "utilities",
    "real estate": "real estate",
    "realty": "real estate",
    "property": "real estate",
    "hotels": "consumer discretionary",
    "hospitality": "consumer discretionary",
}


def _resolve_sector(sector_input: str) -> str:
    """Map flexible user input to file naming convention."""
    cleaned = sector_input.lower().strip()
    return SECTOR_MAP.get(cleaned, cleaned)


def _find_col(df: pd.DataFrame, pattern: str) -> Optional[str]:
    """Find a column by partial name match (case-insensitive)."""
    for col in df.columns:
        if pattern.lower() in str(col).lower():
            return col
    return None


# ============================================================
# PRECEDENT TRANSACTIONS
# ============================================================

def get_precedent_transactions(sector: str, geography: str = None) -> pd.DataFrame:
    """
    Load cleaned precedent transactions for a sector.

    Files are global (all geographies). geography param filters rows.

    Args:
        sector:    Sector name — mapped via SECTOR_MAP
        geography: Optional row-level filter e.g. 'Asia-Pacific', 'India'

    Returns:
        DataFrame of clean deals. Empty DataFrame if not found.

    Three-tier fallback logic (as per architectural decision):
        Tier 1: India geography filter
        Tier 2: Asia-Pacific filter
        Tier 3: All global deals
    """
    sector_key = _resolve_sector(sector)

    if not TRANSACTIONS_CLEAN_DIR.exists():
        print(
            f"WARNING: Clean directory not found at {TRANSACTIONS_CLEAN_DIR}\n"
            f"Run clean_capiq_transactions.py first."
        )
        return pd.DataFrame()

    # Build glob pattern for clean files
    # Files saved as: clean_global_{sector}_transactions.csv
    sector_slug = sector_key.replace(" ", "_")
    pattern = f"clean_global_*{sector_slug}*transactions.csv"
    matches = list(TRANSACTIONS_CLEAN_DIR.glob(pattern))

    # Fuzzy fallback if exact pattern misses
    if not matches:
        all_csvs = list(TRANSACTIONS_CLEAN_DIR.glob("*.csv"))
        sector_nospace = sector_key.replace(" ", "")
        matches = [
            f for f in all_csvs
            if sector_nospace in f.stem.lower().replace(" ", "").replace("_", "")
        ]

    if not matches:
        print(f"WARNING: No clean transaction file for sector '{sector}' (resolved: '{sector_key}')")
        return pd.DataFrame()

    df = pd.read_csv(matches[0])

    # Apply geography row filter if specified
    if geography:
        geo_col = _find_col(df, "geography") or _find_col(df, "region")
        if geo_col:
            filtered = df[df[geo_col].astype(str).str.contains(geography, case=False, na=False)]
            if not filtered.empty:
                df = filtered
            else:
                print(
                    f"  NOTE: geography filter '{geography}' returned 0 rows. "
                    f"Using all geographies (Tier 3 fallback)."
                )

    return df


def get_transaction_stats(
    sector: str,
    geography: str = None,
    apply_india_adjustment: bool = False
) -> Dict:
    """
    Summary statistics for precedent transaction multiples.

    Args:
        sector:                  Sector name
        geography:               Optional geography filter
        apply_india_adjustment:  If True, applies 15% India country discount

    Returns:
        Dict with median, mean, P25, P75, min, max EV/EBITDA
    """
    df = get_precedent_transactions(sector, geography)

    if df.empty:
        return {"error": f"No data for sector '{sector}'"}

    # Find EV/EBITDA column — standardised as ev_ebitda_multiple by cleanup script
    ebitda_col = "ev_ebitda_multiple"
    if ebitda_col not in df.columns:
        # Try partial match fallback
        for col in df.columns:
            if "ebitda" in col.lower():
                ebitda_col = col
                break
        else:
            return {"error": "EV/EBITDA column not found"}

    series = pd.to_numeric(df[ebitda_col], errors="coerce").dropna()
    series = series[(series > 0) & (series <= 50)]

    if len(series) == 0:
        return {"error": "No valid multiples after filtering"}

    result = {
        "sector": sector,
        "geography": geography or "Global (all)",
        "deal_count": len(series),
        "median_ev_ebitda": round(series.median(), 2),
        "mean_ev_ebitda": round(series.mean(), 2),
        "percentile_25": round(series.quantile(0.25), 2),
        "percentile_75": round(series.quantile(0.75), 2),
        "min": round(series.min(), 2),
        "max": round(series.max(), 2),
        "india_adjusted": False,
    }

    if apply_india_adjustment:
        for key in ["median_ev_ebitda", "mean_ev_ebitda", "percentile_25", "percentile_75"]:
            result[key] = round(result[key] * (1 - INDIA_DISCOUNT), 2)
        result["india_adjusted"] = True
        result["india_discount_applied"] = f"{int(INDIA_DISCOUNT * 100)}%"

    return result


# ============================================================
# PUBLIC COMPS
# ============================================================

def get_public_comps(sector: str, geography: str = None) -> pd.DataFrame:
    """
    Load public comps for a sector from global xlsx files.

    Self-computes EV/EBITDA where CapIQ pre-computed column is NA.
    Cross-checks: flags if pre-computed and self-computed differ >10%.

    Args:
        sector:    Sector name
        geography: Filter by Global Region column e.g. 'Asia-Pacific'

    File naming: global_{sector}_peers.xlsx
    Header structure:
        Row 1: Blank
        Row 2: Blank
        Row 3: Human-readable column headers  ← header row
        Row 4: CapIQ field codes
        Row 5: Sub-headers
        Row 6+: Data
    """
    sector_key = _resolve_sector(sector)

    if not PUBLIC_COMPS_DIR.exists():
        print(f"WARNING: Public comps directory not found at {PUBLIC_COMPS_DIR}")
        return pd.DataFrame()

    # Search for global_{sector}_peers.xlsx
    # Handles spaces in names like "global_real estate_peers.xlsx"
    sector_slug = sector_key.replace(" ", "_")
    pattern = f"global_*{sector_slug}*peers*.xlsx"
    matches = list(PUBLIC_COMPS_DIR.glob(pattern))

    # Try rglob in case file is in a subdirectory
    if not matches:
        matches = list(PUBLIC_COMPS_DIR.rglob(f"global_*{sector_slug}*peers*.xlsx"))

    # Fuzzy fallback
    if not matches:
        all_xlsx = list(PUBLIC_COMPS_DIR.rglob("*.xlsx"))
        sector_nospace = sector_key.replace(" ", "")
        matches = [
            f for f in all_xlsx
            if sector_nospace in f.stem.lower().replace(" ", "").replace("_", "")
            and "global" in f.stem.lower()
        ]

    if not matches:
        print(f"WARNING: No public comps file found for sector '{sector}' (resolved: '{sector_key}')")
        return pd.DataFrame()

    chosen_file = matches[0]
    print(f"  Loading comps from: {chosen_file.name}")

    # Parse header structure — row 3 (index 2) is the header
    df = pd.read_excel(chosen_file, header=2, engine="openpyxl")

    # Drop field codes row (row 0) and sub-headers row (row 1)
    df = df.iloc[2:].reset_index(drop=True)

    # Drop completely empty rows
    df = df.dropna(how="all")

    # Convert numeric columns
    numeric_patterns = [
        "market capitalization",
        "total revenue",
        "ebitda",
        "total debt",
        "cash and cash",
        "total enterprise value",
        "enterprise value",
        "ebitda margin",
        "interest expense",
        "net income",
        "total assets",
        "total equity",
    ]

    for col in df.columns:
        col_lower = str(col).lower()
        if any(p in col_lower for p in numeric_patterns):
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "").str.replace("(", "-").str.replace(")", ""),
                errors="coerce"
            )

    # Identify key columns
    mkt_cap_col   = _find_col(df, "market capitalization")
    tev_snl_col   = _find_col(df, "total enterprise value (snl)")
    rev_col       = _find_col(df, "total revenue")
    debt_col      = _find_col(df, "total debt")
    cash_col      = _find_col(df, "cash and cash")
    ebitda_col    = _find_col(df, "ebitda latest")     # prefer LFY over LTM
    if not ebitda_col:
        ebitda_col = _find_col(df, "ebitda")
    precomp_col   = _find_col(df, "total enterprise value/ ebitda")
    geo_col       = _find_col(df, "global region") or _find_col(df, "geography")

    # Self-compute EV and EV/EBITDA
    if mkt_cap_col and debt_col and cash_col and ebitda_col:
        ev_self = (
            df[mkt_cap_col].fillna(0)
            + df[debt_col].fillna(0)
            - df[cash_col].fillna(0)
        )
        ev_ebitda_self = (ev_self / df[ebitda_col]).replace([np.inf, -np.inf], np.nan)

        # Cross-check against pre-computed column
        if precomp_col:
            # Flag where both exist and differ by >10%
            both_exist = df[precomp_col].notna() & ev_ebitda_self.notna()
            if both_exist.any():
                pct_diff = (
                    (df.loc[both_exist, precomp_col] - ev_ebitda_self[both_exist]).abs()
                    / df.loc[both_exist, precomp_col].abs()
                )
                large_diff = pct_diff > 0.10
                if large_diff.any():
                    print(
                        f"  NOTE: {large_diff.sum()} companies have >10% difference "
                        f"between CapIQ pre-computed and self-computed EV/EBITDA. "
                        f"Using pre-computed where available."
                    )

            df["ev_ebitda_final"] = df[precomp_col].combine_first(ev_ebitda_self)
        else:
            df["ev_ebitda_final"] = ev_ebitda_self

        # EV/Revenue
        if rev_col:
            df["ev_revenue_final"] = (ev_self / df[rev_col]).replace([np.inf, -np.inf], np.nan)

        # Store self-computed TEV for reference
        df["tev_self_computed_usd_m"] = ev_self

    # Apply geography filter
    if geography and geo_col:
        filtered = df[df[geo_col].astype(str).str.contains(geography, case=False, na=False)]
        if not filtered.empty:
            df = filtered
        else:
            print(
                f"  NOTE: geography filter '{geography}' returned 0 rows. "
                f"Returning all geographies."
            )

    return df


def get_comp_stats(
    sector: str,
    geography: str = None,
    apply_india_adjustment: bool = False
) -> Dict:
    """
    Public comp valuation statistics.

    Args:
        sector:                  Sector name
        geography:               Optional geography filter (e.g. 'Asia-Pacific')
        apply_india_adjustment:  Apply 15% India country discount

    Returns:
        Dict with median, P25, P75 for EV/EBITDA and EV/Revenue
    """
    df = get_public_comps(sector, geography)

    if df.empty or "ev_ebitda_final" not in df.columns:
        return {"error": f"No comp data for '{sector}'"}

    series = df["ev_ebitda_final"].dropna()
    # Remove negatives and extreme outliers
    series = series[(series > 0) & (series < 100)]

    if len(series) == 0:
        return {"error": "No valid EV/EBITDA after filtering"}

    result = {
        "sector": sector,
        "geography": geography or "Global (all)",
        "comp_count": len(series),
        "median_ev_ebitda": round(series.median(), 2),
        "mean_ev_ebitda": round(series.mean(), 2),
        "percentile_25": round(series.quantile(0.25), 2),
        "percentile_75": round(series.quantile(0.75), 2),
        "india_adjusted": False,
    }

    # EV/Revenue if available
    if "ev_revenue_final" in df.columns:
        rev_s = df["ev_revenue_final"].dropna()
        rev_s = rev_s[(rev_s > 0) & (rev_s < 100)]
        if len(rev_s) > 0:
            result["median_ev_revenue"] = round(rev_s.median(), 2)

    if apply_india_adjustment:
        for key in ["median_ev_ebitda", "mean_ev_ebitda", "percentile_25", "percentile_75"]:
            result[key] = round(result[key] * (1 - INDIA_DISCOUNT), 2)
        result["india_adjusted"] = True
        result["india_discount_applied"] = f"{int(INDIA_DISCOUNT * 100)}%"

    return result


def apply_india_discount(global_multiple: float) -> float:
    """Apply Damodaran country risk discount for India valuation."""
    return round(global_multiple * (1 - INDIA_DISCOUNT), 2)


# ============================================================
# LEGACY COMPATIBILITY — used by valuation_agent.py
# ============================================================

def load_peers_from_capiq(
    sector: str,
    target_revenue_usd_m: float,
    n_peers: int = 5,
    geography: str = None,
    apply_india_adjustment: bool = True
) -> List[Dict]:
    """
    Returns top n peers closest by revenue with EV/EBITDA multiples.

    Called by valuation_agent.py — signature preserved for compatibility.
    India adjustment now applied by default since all files are global.

    Args:
        sector:                  Sector name
        target_revenue_usd_m:    Target company revenue in USD millions
        n_peers:                 Number of peers to return
        geography:               Optional geography filter
        apply_india_adjustment:  Apply 15% India discount (default True)
    """
    df = get_public_comps(sector, geography)

    if df.empty or "ev_ebitda_final" not in df.columns:
        return []

    name_col = (
        _find_col(df, "entity name")
        or _find_col(df, "company name")
        or _find_col(df, "company")
        or _find_col(df, "name")
    )
    rev_col = _find_col(df, "total revenue")

    if not name_col or not rev_col:
        print(f"WARNING: Could not find name or revenue column in comps file")
        return []

    peers = []
    for _, row in df.iterrows():
        name = row.get(name_col)
        if pd.isna(name):
            continue

        ev_ebitda = row.get("ev_ebitda_final")
        if pd.isna(ev_ebitda) or ev_ebitda <= 0 or ev_ebitda > 100:
            continue

        rev_raw = row.get(rev_col, 0)
        if pd.isna(rev_raw) or rev_raw <= 0:
            continue

        ev_rev = row.get("ev_revenue_final")

        # Apply India discount at peer level if requested
        if apply_india_adjustment:
            ev_ebitda = round(ev_ebitda * (1 - INDIA_DISCOUNT), 2)
            if pd.notna(ev_rev):
                ev_rev = round(float(ev_rev) * (1 - INDIA_DISCOUNT), 2)

        peers.append({
            "name": str(name),
            "revenue_usd_m": float(rev_raw),
            "ev_ebitda": float(ev_ebitda),
            "ev_revenue": float(ev_rev) if pd.notna(ev_rev) else None,
            "india_adjusted": apply_india_adjustment,
        })

    # Sort by closest revenue to target
    peers.sort(key=lambda x: abs(x["revenue_usd_m"] - target_revenue_usd_m))
    selected = peers[:n_peers]

    # Return format compatible with valuation_agent.py
    return [
        {
            "name": p["name"],
            "ev_ebitda": p["ev_ebitda"],
            "ev_revenue": p["ev_revenue"],
            "india_adjusted": p["india_adjusted"],
        }
        for p in selected
    ]


# ============================================================
# QUICK TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CAPIQ LOADER — Quick Test (Global Files)")
    print("=" * 60)

    # Test transactions
    print("\n--- Transaction Stats (Healthcare, Global) ---")
    stats = get_transaction_stats("healthcare", apply_india_adjustment=False)
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n--- Transaction Stats (Healthcare, India-adjusted) ---")
    stats_india = get_transaction_stats("healthcare", apply_india_adjustment=True)
    for k, v in stats_india.items():
        print(f"  {k}: {v}")

    # Test public comps
    print("\n--- Public Comp Stats (Healthcare, Global) ---")
    comp_stats = get_comp_stats("healthcare", apply_india_adjustment=False)
    for k, v in comp_stats.items():
        print(f"  {k}: {v}")

    print("\n--- Public Comp Stats (Healthcare, Asia-Pacific) ---")
    comp_apac = get_comp_stats("healthcare", geography="Asia-Pacific")
    for k, v in comp_apac.items():
        print(f"  {k}: {v}")

    # Test legacy peer loading (India-adjusted by default)
    print("\n--- Legacy Peer Load (Healthcare, target revenue $3000M) ---")
    peers = load_peers_from_capiq("healthcare", 3000, n_peers=3)
    for p in peers:
        adj = "(India-adj)" if p.get("india_adjusted") else ""
        print(f"  {p['name']}: EV/EBITDA={p['ev_ebitda']:.1f}x {adj}")

    print("\nDone.")
