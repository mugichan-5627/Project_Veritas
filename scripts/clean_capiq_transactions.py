"""
clean_capiq_transactions.py
Project Veritas — CapIQ Precedent Transaction Cleanup (CORRECTED)

Based on actual file structure observed:
- Row 0-1: Blank
- Row 2: Human-readable column headers
- Row 3: CapIQ field codes  
- Row 4: Sub-headers (Announcement, LTM, etc.)
- Row 5+: Data

Author: Moosa (Project Veritas)
Date: May 2026
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

RAW_DIR = Path(r"C:\Users\Moosa\Downloads\Project_Veritas\data\capiq\precedent_transactions\global_transactions")
CLEAN_DIR = Path(r"C:\Users\Moosa\Downloads\Project_Veritas\data\capiq\precedent_transactions\clean")
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# Outlier thresholds
MIN_MULTIPLE = 0.0
MAX_MULTIPLE = 50.0
MIN_DEAL_VALUE = 50  # USD millions (global)

# ============================================================
# PROCESSING
# ============================================================

def clean_transaction_file(filepath: Path, min_deal_val: float = 50) -> pd.DataFrame:
    """Read and clean a single CapIQ transaction export."""
    
    print(f"\n{'='*60}")
    print(f"Processing: {filepath.name}")
    print(f"{'='*60}")
    
    try:
        # Row 2 has human-readable headers
        df = pd.read_excel(filepath, header=2, engine='openpyxl')
    except Exception as e:
        print(f"  ERROR reading file: {e}")
        return pd.DataFrame()
    
    print(f"  Raw rows (including field code/sub-header): {len(df)}")
    
    # Drop first 2 rows which are field codes (row 3) and sub-headers (row 4)
    df = df.iloc[2:].reset_index(drop=True)
    print(f"  Data rows: {len(df)}")
    
    # --- Identify key columns ---
    # Find EV/EBITDA column (Transaction Value / EBITDA)
    ebitda_col = None
    for col in df.columns:
        col_str = str(col).lower()
        if 'transaction value' in col_str and 'ebitda' in col_str:
            ebitda_col = col
            break
    
    if ebitda_col is None:
        # Fallback: look for any column with ebitda and (x)
        for col in df.columns:
            col_str = str(col).lower()
            if 'ebitda' in col_str and '(x)' in col_str:
                ebitda_col = col
                break
    
    if ebitda_col is None:
        print(f"  WARNING: No EV/EBITDA column found!")
        print(f"  Columns: {list(df.columns)}")
        return pd.DataFrame()
    
    print(f"  EV/EBITDA column: '{ebitda_col}'")
    
    # Find transaction value column
    value_col = None
    for col in df.columns:
        col_str = str(col).lower()
        if 'total transaction value' in col_str and 'include' not in col_str:
            value_col = col
            break
    
    # Find EV/Revenue column
    rev_multiple_col = None
    for col in df.columns:
        col_str = str(col).lower()
        if 'implied enterprise value' in col_str and 'revenue' in col_str:
            rev_multiple_col = col
            break
    
    # Find announced date column
    date_col = None
    for col in df.columns:
        col_str = str(col).lower()
        if 'announced date' in col_str:
            date_col = col
            break
    
    # Find geography column
    geo_col = None
    for col in df.columns:
        col_str = str(col).lower()
        if 'transaction geography' in col_str or 'geography' in col_str:
            geo_col = col
            break

    # --- Convert to numeric ---
    df[ebitda_col] = pd.to_numeric(df[ebitda_col], errors='coerce')
    
    if value_col:
        df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
    
    if rev_multiple_col:
        df[rev_multiple_col] = pd.to_numeric(df[rev_multiple_col], errors='coerce')
    
    # --- FILTERING ---
    total_rows = len(df)
    
    # Drop NA multiples
    df = df.dropna(subset=[ebitda_col])
    print(f"  After dropping NA EV/EBITDA: {len(df)} ({len(df)/max(total_rows,1)*100:.1f}% yield)")
    
    # Remove outliers
    df = df[(df[ebitda_col] > MIN_MULTIPLE) & (df[ebitda_col] <= MAX_MULTIPLE)]
    print(f"  After outlier removal (0-{MAX_MULTIPLE}x): {len(df)}")
    
    # Min deal size
    if value_col and value_col in df.columns:
        valid_values = df[value_col].notna()
        df = df[~valid_values | (df[value_col] >= min_deal_val)]
        print(f"  After min deal size (${min_deal_val}M+): {len(df)}")
    
    # Parse date
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce', format='mixed')
        df = df.sort_values(date_col, ascending=False).reset_index(drop=True)
    
    # --- Stats ---
    if len(df) > 0:
        print(f"  FINAL clean rows: {len(df)}")
        print(f"  Median EV/EBITDA: {df[ebitda_col].median():.1f}x")
        print(f"  Mean EV/EBITDA: {df[ebitda_col].mean():.1f}x")
        print(f"  25th pctl: {df[ebitda_col].quantile(0.25):.1f}x")
        print(f"  75th pctl: {df[ebitda_col].quantile(0.75):.1f}x")
    
    return df


def main():
    print("=" * 70)
    print("PROJECT VERITAS — CapIQ Transaction Cleanup")
    print("=" * 70)
    
    # Process all directories
    sources = [
        ("global", RAW_DIR, MIN_DEAL_VALUE),
    ]
    
    summary = []
    
    for label, raw_dir, min_val in sources:
        if not raw_dir.exists():
            print(f"\nSkipping {label}: {raw_dir} not found")
            continue
            
        xlsx_files = list(raw_dir.glob("*.xlsx"))
        if not xlsx_files:
            print(f"\nSkipping {label}: no .xlsx files")
            continue
            
        print(f"\n{'#'*70}")
        print(f"# {label.upper()} — {len(xlsx_files)} files (min deal: ${min_val}M)")
        print(f"{'#'*70}")
        
        for filepath in sorted(xlsx_files):
            df_clean = clean_transaction_file(filepath, min_deal_val=min_val)
            
            if df_clean.empty:
                summary.append({"label": label, "sector": filepath.stem, "clean_rows": 0, "status": "FAILED/EMPTY"})
                continue
            
            # Extract sector name from filename
            sector_name = filepath.stem
            for prefix in ["global_ma_", "india_ma_", "india_ma_transactions_", "india_"]:
                sector_name = sector_name.replace(prefix, "")
            sector_name = sector_name.replace("_transactions", "").replace("_pe_buyouts", "").strip()
            
            output_path = CLEAN_DIR / f"clean_{label}_{sector_name}_transactions.csv"
            df_clean.to_csv(output_path, index=False)
            
            summary.append({"label": label, "sector": sector_name, "clean_rows": len(df_clean), "status": "OK"})
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total = 0
    for s in summary:
        label = s["label"]
        sector = s.get("sector", "unknown")
        print(f"  [{label:>10}] {sector:<30} {s['clean_rows']:>6} deals  [{s['status']}]")
        total += s["clean_rows"]
    print(f"  {'':>10}  {'TOTAL':<30} {total:>6}")
    print(f"\nClean files saved to: {CLEAN_DIR}")


if __name__ == "__main__":
    main()
