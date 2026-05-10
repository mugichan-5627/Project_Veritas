
Perfect. I have everything I need. Three things to note before I write the scripts:

Important observations:

Your ChromaDB already has a macro_pe_industry collection (1491 chunks) that wasn't in the original checkpoint — so you already did a partial rebuild at some point
forensic_and_credit only has 99 chunks — that's suspiciously low, the original had 711. The new PDFs you added are governance/PE focused so they will bulk this up significantly
All new PDFs go into forensic_and_credit — confirmed
Script 1: Transaction Cleanup
Save as C:\Users\Moosa\Downloads\Project_Veritas\project_veritas\memory\clean_capiq_transactions.py

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
        col_lower = str(col).strip().lower()
        if col_lower in COLUMN_RENAMES:
            rename_map[col] = COLUMN_RENAMES[col_lower]
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
Script 2: BGE-M3 ChromaDB Migration
Save as C:\Users\Moosa\Downloads\Project_Veritas\project_veritas\memory\rebuild_chromadb_bgem3.py

"""
rebuild_chromadb_bgem3.py
Project Veritas — Full ChromaDB Rebuild with BGE-M3 Embeddings

Deletes all existing collections and rebuilds from scratch using
BAAI/bge-m3 as the embedding function instead of ChromaDB's default.

Collections rebuilt:
  - valuation_methodology     (valuation textbooks + Damodaran)
  - forensic_and_credit       (forensics + governance + PE industry + ICRA)
  - india_market_context      (EY India, Brookfield, market PDFs)
  - macro_pe_industry         (PE reports, market reviews — already existed)
  - current_deal              (empty — drop zone for company PDFs)

Author: Moosa (Project Veritas)
Date: May 2026
"""

import os
import shutil
import time
from pathlib import Path
from typing import List, Optional
import numpy as np

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(r"C:\Users\Moosa\Downloads\Project_Veritas")
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
ICRA_DIR = BASE_DIR / "icra rating methodologies"
CHROMA_DB_DIR = BASE_DIR / "project_veritas" / "memory" / "chroma_db"

# ============================================================
# PDF TO COLLECTION MAPPING
# Every file in knowledge_base/ assigned to exactly one collection
# ============================================================

# valuation_methodology — textbooks, DCF, LBO, PE mechanics
VALUATION_PDFS = [
    "Rosenbaum & Pearl IB textbook",         # exact filename may vary — use glob
    "McKinsey Business Valuation",
    "Damodaran",                              # all Damodaran PDFs
    "Paul Pignataro",
    "Zeisberger",
    "Reinard",
    "Coffey",
    "Accenture",
    "Metrick",
    "Creating PE Waterfall",
    "NVCA",
]

# forensic_and_credit — forensics + governance + ALL new PDFs added May 2026
FORENSIC_PDFS = [
    # Existing
    "financial_shenanigans_framework.txt",
    "Moody",
    "Norges",
    # NEW governance PDFs added May 2026
    "private-equity-understanding-conduct-risk-and-responsible-investing",
    "blackrock-investment-stewardship-benchmark-global-principles",
    "policy-survey-summary-2025",
    "SSRN-id593423",
    "rf-v2005-n1-3930-pdf",
    "A_GUIDE_TO_BOARD_EVALUATION",
    "An_evaluation_of_the_use_of_professional_judgement",
    "Evaluating Corporate Governance_updated",
    "g20_wef_corpgov",
    "cfa_corp_gov",
    "RiskManual_damodaran",
    "CorpGovernance_damodaran",
    # NEW PE industry reports added May 2026
    "mckinsey-global-private-markets-review-2024",
    "gpmr2026-private-equity-clearer-view-tougher-terrain_final_v10",
    "Private-equity-exit-excellence-Getting-the-story-right-VF2",
    "bcg-icapital-the-future-is-private",
    "executive-perspectives-ai-first-companies-private-equity",
    "vencap",
    "Venture-Capital-Fund-Toolkit",
    "bain-report_global-private-equity-report-2026",
    "private-equity",
    "economics-of-private-equity",
    "Private-Equity-Primer",
    "ey-private-equity-and-venture-capital-trendbook-2025-v1",
    "18 private equity demystified",
    "privateequity",
]

# india_market_context — India-specific market and regulatory docs
INDIA_PDFS = [
    "EY India",
    "Brookfield",
    "Unified",
]

# ============================================================
# BGE-M3 EMBEDDING FUNCTION FOR CHROMADB
# ============================================================

class BGEM3Embedding:
    """
    ChromaDB-compatible embedding function using BAAI/bge-m3.
    
    BGE-M3 outputs dense vectors of dimension 1024.
    We use only dense vectors here (sufficient for our use case).
    ChromaDB expects a callable that takes List[str] and returns List[List[float]].
    """

    def __init__(self):
        print("Loading BGE-M3 model (BAAI/bge-m3)...")
        from FlagEmbedding import BGEM3FlagModel
        self.model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
        print("BGE-M3 loaded. Embedding dimension: 1024")

    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        ChromaDB calls this with a list of strings.
        Returns list of 1024-dim float vectors.
        """
        # BGE-M3 has a max sequence length — batch in chunks of 32 to avoid OOM
        all_embeddings = []
        batch_size = 32

        for i in range(0, len(input), batch_size):
            batch = input[i: i + batch_size]
            result = self.model.encode(
                batch,
                batch_size=min(batch_size, len(batch)),
                max_length=512,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False
            )
            dense = result["dense_vecs"]
            # Convert numpy array to list of lists for ChromaDB
            all_embeddings.extend(dense.tolist())

        return all_embeddings


# ============================================================
# PDF READER
# ============================================================

def read_pdf_text(filepath: Path) -> str:
    """
    Extract text from PDF using pdfplumber (better than pypdf2 for tables).
    Falls back to pypdf2 if pdfplumber fails.
    Falls back to reading as plain text if .txt file.
    """
    if filepath.suffix.lower() == ".txt":
        return filepath.read_text(encoding="utf-8", errors="ignore")

    # Try pdfplumber first
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        text = "\n".join(text_parts)
        if len(text.strip()) > 100:
            return text
    except Exception as e:
        print(f"    pdfplumber failed: {e}")

    # Fallback: pypdf2
    try:
        import PyPDF2
        text_parts = []
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        print(f"    pypdf2 also failed: {e}")
        return ""


# ============================================================
# TEXT CHUNKER
# ============================================================

def chunk_text(text: str, chunk_size: int = 512, chunk_overlap: int = 64) -> List[str]:
    """
    RecursiveCharacterTextSplitter logic in pure Python.
    Tries to split at paragraph → sentence → word boundaries.
    
    Same parameters as Phase 2: chunk_size=512, overlap=64.
    """
    if not text or len(text.strip()) < 50:
        return []

    # Clean up excessive whitespace
    import re
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    chunks = []
    separators = ["\n\n", "\n", ". ", " ", ""]

    def split_recursive(text: str, separators: List[str]) -> List[str]:
        if len(text) <= chunk_size:
            if text.strip():
                return [text.strip()]
            return []

        separator = separators[0] if separators else ""
        remaining_separators = separators[1:]

        splits = text.split(separator) if separator else list(text)

        result = []
        current_chunk = ""

        for split in splits:
            test = (current_chunk + separator + split).strip() if current_chunk else split.strip()

            if len(test) <= chunk_size:
                current_chunk = test
            else:
                if current_chunk:
                    result.append(current_chunk)
                    # Overlap: carry last `chunk_overlap` chars into next chunk
                    overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else current_chunk
                    current_chunk = (overlap_text + separator + split).strip() if overlap_text else split.strip()
                else:
                    # Single split is too long — recurse with finer separator
                    if remaining_separators:
                        result.extend(split_recursive(split, remaining_separators))
                    else:
                        # Force split at chunk_size
                        for j in range(0, len(split), chunk_size - chunk_overlap):
                            result.append(split[j: j + chunk_size])

        if current_chunk:
            result.append(current_chunk)

        return [c for c in result if c.strip()]

    return split_recursive(text, separators)


# ============================================================
# COLLECTION BUILDER
# ============================================================

def ingest_files_into_collection(
    collection,
    files: List[Path],
    collection_name: str,
    embedding_fn: BGEM3Embedding
):
    """
    Reads each file, chunks it, and adds to the ChromaDB collection.
    Prints progress per file.
    """
    total_chunks = 0
    skipped = 0

    for filepath in files:
        if not filepath.exists():
            print(f"    MISSING: {filepath.name}")
            skipped += 1
            continue

        print(f"  Reading: {filepath.name}")
        text = read_pdf_text(filepath)

        if not text or len(text.strip()) < 100:
            print(f"    WARNING: No text extracted from {filepath.name} (possibly scanned)")
            skipped += 1
            continue

        chunks = chunk_text(text, chunk_size=512, chunk_overlap=64)
        if not chunks:
            print(f"    WARNING: Zero chunks from {filepath.name}")
            skipped += 1
            continue

        print(f"    {len(chunks)} chunks → ingesting into '{collection_name}'")

        # Add in batches of 50 to avoid memory issues with BGE-M3
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            ids = [f"{filepath.stem}_{i + j}" for j in range(len(batch))]
            metadatas = [
                {
                    "source": filepath.name,
                    "collection": collection_name,
                    "chunk_index": i + j
                }
                for j in range(len(batch))
            ]

            try:
                collection.add(
                    documents=batch,
                    ids=ids,
                    metadatas=metadatas
                )
            except Exception as e:
                print(f"    ERROR adding batch {i}-{i+len(batch)}: {e}")
                continue

        total_chunks += len(chunks)
        print(f"    Done. Running total for this collection: {total_chunks} chunks")

    return total_chunks, skipped


# ============================================================
# MAIN REBUILD FUNCTION
# ============================================================

def rebuild_all(dry_run: bool = False):
    """
    Full ChromaDB rebuild with BGE-M3.
    
    dry_run=True: shows what would be ingested without touching ChromaDB.
    dry_run=False: deletes everything and rebuilds.
    """

    print("=" * 70)
    print("PROJECT VERITAS — ChromaDB BGE-M3 Rebuild")
    print("=" * 70)

    # ---- Discover all files ----
    all_kb_files = list(KNOWLEDGE_BASE_DIR.glob("*.pdf")) + \
                   list(KNOWLEDGE_BASE_DIR.glob("*.txt"))
    all_icra_files = list(ICRA_DIR.glob("*.pdf"))

    print(f"\nKnowledge base files found: {len(all_kb_files)}")
    print(f"ICRA files found: {len(all_icra_files)}")

    # ---- Route files to collections ----
    # Logic: check if any keyword from the collection's list appears in filename

    def matches_any(filename: str, keywords: List[str]) -> bool:
        fn_lower = filename.lower()
        return any(kw.lower() in fn_lower for kw in keywords)

    valuation_files = []
    forensic_files = []
    india_files = []
    unrouted = []

    for f in all_kb_files:
        if matches_any(f.name, VALUATION_PDFS):
            valuation_files.append(f)
        elif matches_any(f.name, FORENSIC_PDFS):
            forensic_files.append(f)
        elif matches_any(f.name, INDIA_PDFS):
            india_files.append(f)
        else:
            unrouted.append(f)

    # ICRA always goes to forensic_and_credit
    forensic_files.extend(all_icra_files)

    # ---- Report routing ----
    print(f"\n{'='*50}")
    print("FILE ROUTING PLAN")
    print(f"{'='*50}")

    print(f"\nvaluation_methodology ({len(valuation_files)} files):")
    for f in valuation_files:
        print(f"  ✓ {f.name}")

    print(f"\nforensic_and_credit ({len(forensic_files)} files):")
    for f in forensic_files:
        print(f"  ✓ {f.name}")

    print(f"\nindia_market_context ({len(india_files)} files):")
    for f in india_files:
        print(f"  ✓ {f.name}")

    if unrouted:
        print(f"\nUNROUTED — will NOT be ingested ({len(unrouted)} files):")
        for f in unrouted:
            print(f"  ? {f.name}")
        print("\nIf any of these should be ingested, add their name pattern")
        print("to the appropriate list at the top of this script and rerun.")

    if dry_run:
        print("\nDRY RUN complete — no changes made to ChromaDB.")
        return

    # ---- Confirm before deleting ----
    print(f"\n{'='*50}")
    print("WARNING: About to DELETE all ChromaDB collections and rebuild.")
    print(f"ChromaDB path: {CHROMA_DB_DIR}")
    confirm = input("Type YES to continue: ").strip()
    if confirm != "YES":
        print("Aborted.")
        return

    # ---- Load BGE-M3 (expensive — do once) ----
    embedding_fn = BGEM3Embedding()

    # ---- Delete existing ChromaDB ----
    print(f"\nDeleting existing ChromaDB at {CHROMA_DB_DIR}...")
    if CHROMA_DB_DIR.exists():
        shutil.rmtree(CHROMA_DB_DIR)
        print("Deleted.")
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Create new client and collections ----
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

    collections = {
        "valuation_methodology": client.create_collection(
            name="valuation_methodology",
            embedding_function=embedding_fn,
            metadata={"description": "Valuation textbooks, DCF, LBO, PE mechanics"}
        ),
        "forensic_and_credit": client.create_collection(
            name="forensic_and_credit",
            embedding_function=embedding_fn,
            metadata={"description": "Forensics, governance, credit, PE industry, ICRA"}
        ),
        "india_market_context": client.create_collection(
            name="india_market_context",
            embedding_function=embedding_fn,
            metadata={"description": "India PE market, regulatory, macro"}
        ),
        "macro_pe_industry": client.create_collection(
            name="macro_pe_industry",
            embedding_function=embedding_fn,
            metadata={"description": "Global PE industry reports and macro data"}
        ),
        "current_deal": client.create_collection(
            name="current_deal",
            embedding_function=embedding_fn,
            metadata={"description": "Drop zone for company annual reports"}
        ),
    }

    # ---- Ingest ----
    results = {}

    print(f"\n{'='*50}")
    print("INGESTING: valuation_methodology")
    print(f"{'='*50}")
    chunks, skipped = ingest_files_into_collection(
        collections["valuation_methodology"], valuation_files, "valuation_methodology", embedding_fn
    )
    results["valuation_methodology"] = {"chunks": chunks, "skipped": skipped}

    print(f"\n{'='*50}")
    print("INGESTING: forensic_and_credit")
    print(f"{'='*50}")
    chunks, skipped = ingest_files_into_collection(
        collections["forensic_and_credit"], forensic_files, "forensic_and_credit", embedding_fn
    )
    results["forensic_and_credit"] = {"chunks": chunks, "skipped": skipped}

    print(f"\n{'='*50}")
    print("INGESTING: india_market_context")
    print(f"{'='*50}")
    chunks, skipped = ingest_files_into_collection(
        collections["india_market_context"], india_files, "india_market_context", embedding_fn
    )
    results["india_market_context"] = {"chunks": chunks, "skipped": skipped}

    # macro_pe_industry — currently empty in new structure
    # Files that were in this collection previously may now be routed to forensic_and_credit
    # Add filenames here if you want to keep this collection populated
    results["macro_pe_industry"] = {"chunks": 0, "skipped": 0}

    # ---- Final verification ----
    print(f"\n{'='*70}")
    print("REBUILD COMPLETE — VERIFICATION")
    print(f"{'='*70}")
    print(f"\n{'Collection':<30} {'Chunks':>8} {'Skipped':>9}")
    print("-" * 50)

    total_chunks = 0
    for name, col in collections.items():
        count = col.count()
        skipped = results.get(name, {}).get("skipped", 0)
        total_chunks += count
        print(f"{name:<30} {count:>8} {skipped:>9}")

    print("-" * 50)
    print(f"{'TOTAL':<30} {total_chunks:>8}")

    print(f"\nPrevious totals for reference:")
    print(f"  valuation_methodology: 5172 chunks")
    print(f"  forensic_and_credit:    99 chunks (was 711 — needs rebuild)")
    print(f"  india_market_context:  374 chunks")
    print(f"  macro_pe_industry:    1491 chunks")
    print(f"\nExpected: all counts should be HIGHER than before due to new PDFs.")
    print(f"\nChromaDB path: {CHROMA_DB_DIR}")


# ============================================================
# ENTRY POINTS
# ============================================================

if __name__ == "__main__":
    import sys

    if "--dry-run" in sys.argv:
        print("DRY RUN MODE — no changes to ChromaDB\n")
        rebuild_all(dry_run=True)
    else:
        rebuild_all(dry_run=False)
Script 3: capiq_loader.py Update
The existing capiq_loader.py is actually already well-structured for the new global files. It needs three targeted changes:

The get_public_comps header parsing needs to match the actual CapIQ structure (row 3 as header, skip rows 4-5) — same as transactions
The load_peers_from_capiq function needs to apply the India discount when returning peers
The file glob pattern needs to match the new global_*_peers.xlsx naming
Replace the entire file with this:

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
How to Run All Three
Run in this exact order:

$env:PYTHONPATH = "C:\Users\Moosa\Downloads\Project_Veritas"

# Step 1 — Transaction cleanup (fast, ~2 minutes)
py "C:\Users\Moosa\Downloads\Project_Veritas\project_veritas\memory\clean_capiq_transactions.py"

# Step 2 — ChromaDB rebuild (slow, 30-60 minutes on CPU due to BGE-M3)
# Run dry-run first to verify file routing before deleting anything
py "C:\Users\Moosa\Downloads\Project_Veritas\project_veritas\memory\rebuild_chromadb_bgem3.py" --dry-run

# If routing looks correct, run the real rebuild
py "C:\Users\Moosa\Downloads\Project_Veritas\project_veritas\memory\rebuild_chromadb_bgem3.py"

# Step 3 — Test the loader
py "C:\Users\Moosa\Downloads\Project_Veritas\project_veritas\memory\capiq_loader.py"
Run the dry-run before the real rebuild. It will print exactly which file goes into which collection so you can catch any misrouted PDFs before anything gets deleted.