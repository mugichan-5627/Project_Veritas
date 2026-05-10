"""
clean_capiq_transactions.py
Project Veritas — CapIQ Transaction Data Cleaner

Reads all 11 raw global transaction xlsx files from:
  data/capiq/precedent_transactions/global_transactions/

Cleans each file:
  - Parses CapIQ's multi-row header structure (rows 1-5)
  - Drops rows with no EV/EBITDA multiple
  - Removes outliers (<0 or >50x)
  - Standardises column names
  - Saves clean CSVs to:
  data/capiq/precedent_transactions/clean/

Author: Moosa (Project Veritas)
Date: May 2026
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(r"C:\Users\Moosa\Downloads\Project_Veritas\data\capiq")
RAW_DIR = BASE_DIR / "precedent_transactions" / "global_transactions"
CLEAN_DIR = BASE_DIR / "precedent_transactions" / "clean"

# ============================================================
# RAW FILES — exact names confirmed by Moosa
# ============================================================

RAW_FILES = [
    "global_ma_energy_transactions.xlsx",
    "global_ma_materials_transactions.xlsx",
    "global_ma_industrials_transactions.xlsx",
    "global_ma_consumer discretionary_transactions.xlsx",
    "global_ma_consumer staples_transactions.xlsx",
    "global_ma_healthcare_transactions.xlsx",
    "global_ma_financials_transactions.xlsx",
    "global_ma_it_transactions.xlsx",
    "global_ma_communication_transactions.xlsx",
    "global_ma_utilities_transactions.xlsx",
    "global_ma_real estate_transactions.xlsx",
]

# ============================================================
# COLUMN NAME STANDARDISATION
# Maps whatever CapIQ exports to clean internal names
# Based on field codes confirmed in session checkpoint
# ============================================================

COLUMN_RENAMES = {
    # Target company
    "target/issuer name":           "target_name",
    "target name":                  "target_name",

    # Deal identifiers
    "mi transaction id":            "transaction_id",
    "announced date":               "announced_date",
    "transaction type":             "transaction_type",
    "transaction status":           "transaction_status",

    # Deal values
    "total transaction value ($m)": "transaction_value_usd_m",
    "total transaction value":      "transaction_value_usd_m",

    # Parties
    "buyers/investors name":        "buyer_name",
    "sellers name":                 "seller_name",

    # Classification
    "transaction industry (ciq/gics)": "gics_industry",
    "transaction industry":            "gics_industry",

    # Ownership
    "ownership acquired (%)":       "pct_equity_acquired",
    "percent of equity ownership acquired (%)": "pct_equity_acquired",

    # THE KEY MULTIPLE — field code sptr_tv_to_ebitda
    "transaction value / ebitda (x) [announcement]": "ev_ebitda_multiple",
    "transaction value / ebitda (x)":                "ev_ebitda_multiple",
    "transaction value/ ebitda (x) [announcement]":  "ev_ebitda_multiple",
    "transaction value/ ebitda (x)":                 "ev_ebitda_multiple",
    "transaction value/ ebitda(x)":                  "ev_ebitda_multiple",
    "tv/ebitda":                                     "ev_ebitda_multiple",

    # Revenue multiple
    "implied enterprise value / total revenue (x) [announcement]": "ev_revenue_multiple",
    "implied enterprise value / total revenue (x)":                 "ev_revenue_multiple",

    # Target financials
    "target: ebitda ($m)":          "target_ebitda_usd_m",
    "target ebitda ($m)":           "target_ebitda_usd_m",

    # Geography
    "transaction geography":        "geography",
    "company type (target/issuer)": "target_company_type",
    "company type (buyer/investor)":"buyer_company_type",

    # Control
    "change in control? yes/no":    "change_in_control",
    "change in control":            "change_in_control",
}


def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns using COLUMN_RENAMES map (case-insensitive)."""
    rename_map = {}
    for col in df.columns:
        col_str = str(col).strip().lower()
        col_clean1 = col_str.replace("\n", "")
        col_clean2 = col_str.replace("\n", " ")
        if col_str in COLUMN_RENAMES:
            rename_map[col] = COLUMN_RENAMES[col_str]
        elif col_clean1 in COLUMN_RENAMES:
            rename_map[col] = COLUMN_RENAMES[col_clean1]
        elif col_clean2 in COLUMN_RENAMES:
            rename_map[col] = COLUMN_RENAMES[col_clean2]
    df = df.rename(columns=rename_map)
    return df


def _parse_capiq_xlsx(filepath: Path) -> pd.DataFrame:
    """
    Parse CapIQ xlsx with multi-row header structure:
      Row 1: Blank
      Row 2: Blank
      Row 3: Human-readable column headers  ← USE THIS AS HEADER
      Row 4: Internal CapIQ field codes
      Row 5: Sub-headers (Announcement, LTM, etc.)
      Row 6+: Data

    We use row 3 (index 2) as the header and skip rows 4-5.
    """
    # Read with row 3 as header (0-indexed = 2)
    df = pd.read_excel(filepath, header=2, engine='openpyxl')

    # Drop the field codes row and sub-headers row (now rows 0 and 1 of the dataframe)
    df = df.iloc[2:].reset_index(drop=True)

    # Drop completely empty rows
    df = df.dropna(how='all')

    return df


def clean_transaction_file(raw_path: Path, clean_dir: Path) -> dict:
    """
    Clean one transaction file.
    Returns a summary dict with counts for reporting.
    """
    sector_name = raw_path.stem.replace("global_ma_", "").replace("_transactions", "")
    print(f"\n{'='*60}")
    print(f"Processing: {raw_path.name}")
    print(f"Sector: {sector_name}")

    # --- Parse ---
    try:
        df = _parse_capiq_xlsx(raw_path)
    except Exception as e:
        print(f"  ERROR reading file: {e}")
        return {"sector": sector_name, "status": "ERROR", "error": str(e)}

    raw_count = len(df)
    print(f"  Raw rows after header parse: {raw_count}")

    # --- Standardise columns ---
    df = _standardise_columns(df)

    # --- Check EV/EBITDA column exists ---
    if "ev_ebitda_multiple" not in df.columns:
        # Try to find it with partial match as fallback
        ebitda_cols = [c for c in df.columns if "ebitda" in str(c).lower()]
        print(f"  WARNING: ev_ebitda_multiple not found. EBITDA-related cols: {ebitda_cols}")
        if ebitda_cols:
            df = df.rename(columns={ebitda_cols[0]: "ev_ebitda_multiple"})
            print(f"  Using '{ebitda_cols[0]}' as ev_ebitda_multiple")
        else:
            print(f"  FATAL: No EV/EBITDA column found. Skipping.")
            return {"sector": sector_name, "status": "NO_EBITDA_COL", "raw": raw_count}

    # --- Convert EV/EBITDA to numeric ---
    df["ev_ebitda_multiple"] = pd.to_numeric(
        df["ev_ebitda_multiple"].astype(str).str.replace("x", "").str.replace(",", ""),
        errors="coerce"
    )

    # --- Drop rows with no multiple (expected: ~60-70%) ---
    before_drop = len(df)
    df_with_multiple = df[df["ev_ebitda_multiple"].notna()].copy()
    after_drop = len(df_with_multiple)
    print(f"  Rows with EV/EBITDA: {after_drop} / {before_drop} ({round(after_drop/before_drop*100, 1)}% yield)")

    if after_drop == 0:
        print(f"  WARNING: Zero rows with multiples. Check column mapping.")
        return {"sector": sector_name, "status": "ZERO_MULTIPLES", "raw": raw_count}

    # --- Remove outliers: <0 or >50x ---
    before_outlier = len(df_with_multiple)
    df_clean = df_with_multiple[
        (df_with_multiple["ev_ebitda_multiple"] > 0) &
        (df_with_multiple["ev_ebitda_multiple"] <= 50)
    ].copy()
    after_outlier = len(df_clean)
    removed_outliers = before_outlier - after_outlier
    print(f"  After outlier removal (0-50x): {after_outlier} rows ({removed_outliers} outliers removed)")

    # --- Convert announced_date to datetime ---
    if "announced_date" in df_clean.columns:
        df_clean["announced_date"] = pd.to_datetime(
            df_clean["announced_date"], errors="coerce", format="%m/%d/%Y"
        )

    # --- Convert numeric columns ---
    for col in ["transaction_value_usd_m", "target_ebitda_usd_m",
                "pct_equity_acquired", "ev_revenue_multiple"]:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(
                df_clean[col].astype(str).str.replace(",", ""),
                errors="coerce"
            )

    # --- Add sector tag ---
    df_clean["sector_tag"] = sector_name

    # --- Summary stats ---
    series = df_clean["ev_ebitda_multiple"]
    print(f"  EV/EBITDA stats:")
    print(f"    Median: {series.median():.1f}x")
    print(f"    Mean:   {series.mean():.1f}x")
    print(f"    P25:    {series.quantile(0.25):.1f}x")
    print(f"    P75:    {series.quantile(0.75):.1f}x")
    print(f"    Min:    {series.min():.1f}x  |  Max: {series.max():.1f}x")

    # --- Save clean CSV ---
    clean_filename = f"clean_global_{sector_name}_transactions.csv"
    clean_path = clean_dir / clean_filename
    df_clean.to_csv(clean_path, index=False)
    print(f"  Saved: {clean_path.name}")

    return {
        "sector": sector_name,
        "status": "OK",
        "raw_rows": raw_count,
        "rows_with_multiple": after_drop,
        "rows_after_outlier": after_outlier,
        "yield_pct": round(after_drop / before_drop * 100, 1),
        "median_ev_ebitda": round(series.median(), 2),
        "saved_to": clean_filename
    }


def run_cleanup():
    """Main entry point — cleans all 11 transaction files."""

    # Create clean directory if it doesn't exist
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {CLEAN_DIR}")

    results = []
    errors = []

    for filename in RAW_FILES:
        raw_path = RAW_DIR / filename

        if not raw_path.exists():
            print(f"\nWARNING: File not found — {filename}")
            errors.append(filename)
            continue

        result = clean_transaction_file(raw_path, CLEAN_DIR)
        results.append(result)

    # ============================================================
    # FINAL SUMMARY
    # ============================================================
    print(f"\n{'='*60}")
    print("CLEANUP COMPLETE — SUMMARY")
    print(f"{'='*60}")
    print(f"{'Sector':<35} {'Raw':>6} {'Clean':>7} {'Yield':>7} {'Median':>8}")
    print("-" * 65)

    total_raw = 0
    total_clean = 0

    for r in results:
        if r["status"] == "OK":
            total_raw += r["raw_rows"]
            total_clean += r["rows_after_outlier"]
            print(
                f"{r['sector']:<35} "
                f"{r['raw_rows']:>6} "
                f"{r['rows_after_outlier']:>7} "
                f"{r['yield_pct']:>6.1f}% "
                f"{r['median_ev_ebitda']:>7.1f}x"
            )
        else:
            print(f"{r['sector']:<35} {'ERROR':>6} — status: {r['status']}")

    print("-" * 65)
    print(f"{'TOTAL':<35} {total_raw:>6} {total_clean:>7}")

    if errors:
        print(f"\nMissing files ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")

    print(f"\nClean CSVs saved to: {CLEAN_DIR}")
    print("Ready for capiq_loader.py to read from clean/ directory.")


if __name__ == "__main__":
    run_cleanup()
