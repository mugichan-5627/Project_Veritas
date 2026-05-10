import argparse
import os
import shutil
import chromadb
from pathlib import Path
from project_veritas.memory.rebuild_chromadb_bgem3 import BGEM3Embedding
from project_veritas.memory import config

DEMO_DATA = {
    "valuation_methodology": [
        "Internet Retail: Add back SBC to EBITDA. Levered Beta typically 1.2. Cost of Debt 6.5%.",
        "Software—Infrastructure: High gross margins but heavy R&D and SBC. Adjusted EBITDA should remove SBC for conservative PE valuation.",
        "Semiconductors: Highly cyclical. Focus on Cash Conversion and Capex cycles. WACC typically 10-12%.",
        "Banks and financial institutions should be valued using Price to Book (P/B) relative to Return on Equity (ROE). A bank with ROE > Cost of Equity should trade above 1.0x Book value. Use Excess Returns Model for intrinsic value: Value = Equity Capital + PV of (ROE - Ke) * Equity.",
        "Insurance companies are best valued using P/B and P/E. Key metrics include Combined Ratio (underwriting profitability) and Investment Yield.",
        "For financial firms, Enterprise Value (EV) and EBITDA are often misleading due to interest expense being a core operating item. Always use P/E, P/B, and Net Income instead.",
        "Efficiency Ratio for banks: (Non-interest Expense / Total Revenue). Lower is better. Best-in-class banks operate below 60%."
    ],
    "forensic_and_credit": [
        "Look out for SBC that exceeds 10% of revenue—this is a massive red flag.",
        "If Free Cash Flow margin is negative but EBITDA is highly positive, check Capital Expenditures.",
        "A sudden drop in gross margins in hardware can indicate severe pricing power loss."
    ]
}

def build_db(demo=False):
    db_path = config.CHROMA_DB_PATH
    
    if os.path.exists(db_path):
        print(f"[!] Clearing existing ChromaDB at {db_path}...")
        shutil.rmtree(db_path)
        
    os.makedirs(db_path, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_path))
    embedding_fn = BGEM3Embedding()
    
    print("\n" + "="*50)
    print(f"  PROJECT VERITAS - VECTOR DB BUILDER")
    print(f"  Mode: {'DEMO' if demo else 'PRODUCTION'}")
    print("="*50)

    for coll_name in config.COLLECTIONS:
        print(f"  Building collection: {coll_name}")
        collection = client.create_collection(name=coll_name)
        
        texts_to_embed = []
        if demo:
            texts_to_embed = DEMO_DATA.get(coll_name, [])
        else:
            raw_dir = config.RAW_DATA_DIR / coll_name
            if raw_dir.exists():
                for file_path in raw_dir.glob("*.txt"):
                    with open(file_path, "r", encoding="utf-8") as f:
                        texts_to_embed.append(f.read())
            else:
                print(f"    [WARN] No raw data found for {coll_name} at {raw_dir}")
        
        if not texts_to_embed:
            print(f"    [WARN] Skipping empty collection: {coll_name}")
            continue
            
        print(f"    Embedding {len(texts_to_embed)} chunks...")
        embeddings = embedding_fn(texts_to_embed)
        
        ids = [f"{coll_name}_{i}" for i in range(len(texts_to_embed))]
        metadatas = [{"source": "demo" if demo else "local_file"} for _ in range(len(texts_to_embed))]
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts_to_embed,
            metadatas=metadatas
        )
        print(f"    [OK] Collection {coll_name} built successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build ChromaDB vector store for Project Veritas")
    parser.add_argument("--demo", action="store_true", help="Build DB using hardcoded demo texts instead of local textbooks")
    args = parser.parse_args()
    
    build_db(demo=args.demo)
