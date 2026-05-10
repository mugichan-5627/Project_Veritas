"""
rebuild_chromadb_bgem3.py
Project Veritas - Full ChromaDB Rebuild with BGE-M3 Embeddings

Deletes all existing collections and rebuilds from scratch using
BAAI/bge-m3 as the embedding function instead of ChromaDB's default.

Collections rebuilt:
  - valuation_methodology     (valuation textbooks + Damodaran)
  - forensic_and_credit       (forensics + governance + PE industry + ICRA)
  - india_market_context      (EY India, Brookfield, market PDFs)
  - macro_pe_industry         (PE reports, market reviews - already existed)
  - current_deal              (empty - drop zone for company PDFs)

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

# valuation_methodology - textbooks, DCF, LBO, PE mechanics
VALUATION_PDFS = [
    "Rosenbaum & Pearl IB textbook",         # exact filename may vary - use glob
    "McKinsey Business Valuation",
    "Business Valuation_mckinsey",
    "Damodaran",                              # all Damodaran PDFs
    "Paul Pignataro",
    "paul-pignataro",
    "Zeisberger",
    "Reinard",
    "Coffey",
    "Accenture",
    "Metrick",
    "Creating PE Waterfall",
    "Creating Private Equity Waterfall",
    "NVCA",
    "Investment Banking - Valuation",
    "mastering private equity",
]

# forensic_and_credit - forensics + governance + ALL new PDFs added May 2026
FORENSIC_PDFS = [
    # Existing
    "financial_shenanigans_framework.txt",
    "financial shenanigans",
    "Moody",
    "Norges",
    "MRS_Liquidity",
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

# india_market_context - India-specific market and regulatory docs
INDIA_PDFS = [
    "EY India",
    "ey-the-indian",
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
        # BGE-M3 has a max sequence length - batch in chunks of 32 to avoid OOM
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
    Tries to split at paragraph -> sentence -> word boundaries.
    
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
                    # Single split is too long - recurse with finer separator
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

        print(f"    {len(chunks)} chunks -> ingesting into '{collection_name}'")

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
    print("PROJECT VERITAS - ChromaDB BGE-M3 Rebuild")
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
        print(f"  - {f.name}")

    print(f"\nforensic_and_credit ({len(forensic_files)} files):")
    for f in forensic_files:
        print(f"  - {f.name}")

    print(f"\nindia_market_context ({len(india_files)} files):")
    for f in india_files:
        print(f"  - {f.name}")

    if unrouted:
        print(f"\nUNROUTED - will NOT be ingested ({len(unrouted)} files):")
        for f in unrouted:
            print(f"  - {f.name}")
        print("\nIf any of these should be ingested, add their name pattern")
        print("to the appropriate list at the top of this script and rerun.")

    if dry_run:
        print("\nDRY RUN complete - no changes made to ChromaDB.")
        return

    # ---- Confirm before deleting ----
    print(f"\n{'='*50}")
    print("WARNING: About to DELETE all ChromaDB collections and rebuild.")
    print(f"ChromaDB path: {CHROMA_DB_DIR}")
    confirm = input("Type YES to continue: ").strip()
    if confirm != "YES":
        print("Aborted.")
        return

    # ---- Load BGE-M3 (expensive - do once) ----
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

    # macro_pe_industry - currently empty in new structure
    # Files that were in this collection previously may now be routed to forensic_and_credit
    # Add filenames here if you want to keep this collection populated
    results["macro_pe_industry"] = {"chunks": 0, "skipped": 0}

    # ---- Final verification ----
    print(f"\n{'='*70}")
    print("REBUILD COMPLETE - VERIFICATION")
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
    print(f"  forensic_and_credit:    99 chunks (was 711 - needs rebuild)")
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
        print("DRY RUN MODE - no changes to ChromaDB\n")
        rebuild_all(dry_run=True)
    else:
        rebuild_all(dry_run=False)
