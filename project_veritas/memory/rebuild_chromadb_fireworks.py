import os
import chromadb
import pdfplumber
import pathlib
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter
)

# ── Fireworks embedding function ───────────────────
class FireworksEmbeddingFunction:
    """
    Custom ChromaDB embedding function using 
    Fireworks AI API (nomic-embed-text-v1.5).
    1024 dimensions — significantly better than
    default sentence-transformers 384 dimensions.
    Called via API — no local GPU needed.
    """
    def __init__(self):
        import fireworks.client as fw
        fw.api_key = os.environ.get("FIREWORKS_API_KEY")
        if not fw.api_key:
            raise ValueError(
                "FIREWORKS_API_KEY not set. "
                "Run: $env:FIREWORKS_API_KEY = 'fw_...'"
            )
        self.fw = fw
        self.model = "nomic-ai/nomic-embed-text-v1.5"
        print(f"Fireworks embedding: {self.model}")
    
    def __call__(self, input: list[str]) -> list[list[float]]:
        """ChromaDB calls this automatically."""
        embeddings = []
        # Process in batches of 10 to avoid rate limits
        batch_size = 10
        for i in range(0, len(input), batch_size):
            batch = input[i:i+batch_size]
            try:
                response = self.fw.Embedding.create(
                    model=self.model,
                    input=batch
                )
                for item in response.data:
                    embeddings.append(item.embedding)
            except Exception as e:
                print(f"  Embedding batch failed: {e}")
                # Return zero vectors as fallback
                for _ in batch:
                    embeddings.append([0.0] * 1024)
        return embeddings


# ── Config ─────────────────────────────────────────
BASE = pathlib.Path(
    r"C:\Users\Moosa\Downloads\Project_Veritas"
)
CHROMA_PATH = (
    BASE / "project_veritas" / "memory" / "chroma_db"
)
KNOWLEDGE_BASE = BASE / "knowledge_base"
ICRA_FOLDER = BASE / "icra rating methodologies"

SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64
)

# Collection → source folders mapping
COLLECTION_MAP = {
    "valuation_methodology": [
        "Investment Banking - Valuation, Leveraged "
        "Buyouts, and Mergers and Acquisitions "
        "(Wiley Finance).pdf",
        "paul-pignataro-financial-modeling-and-"
        "valuation-investment-banking_compressed.pdf",
        "Business Valuation_mckinsey.pdf",
        "investment valuation guide_damodaran.pdf",
        "article_costofcapital_damodaran.pdf",
        "Return on Capital (ROC), Return on Invested "
        "Capital (ROIC)_damodaran.pdf",
        "younggrowth_startup_value_damodaran.pdf",
        "darksideyoungcos_damodaran.pdf",
        "mastering private equity only introduction.pdf",
        "The Private Equity Playbook PDF_coffey.pdf",
        "Accenture-The-Evolving-Private-Equity-Playbook.pdf",
    ],
    "forensic_and_credit": [
        "private-equity_discussion note_norges.pdf",
        "MRS_Liquidity_PE.pdf",
        "MetrickYasuda2010.pdf",
        "NVCA-Model-Term-Sheet-1.pdf",
        "Creating Private Equity Waterfall Functions "
        "in Excel.pdf",
        "financial_shenanigans_framework.txt",
        "Moody's Rating Scale and Definition.txt",
    ],
    "india_market_context": [
        "ey-the-indian-office-playbook-digital.pdf",
        "Brookfield_Building_the_Backbone_of_AI.pdf",
        "A Unified Metric Architecture for AI "
        "Infrastructure Cross-Layer.pdf",
    ]
}


def extract_text(filepath: pathlib.Path) -> str:
    """Extract text from PDF or txt file."""
    if filepath.suffix == ".txt":
        return filepath.read_text(
            encoding="utf-8", errors="ignore"
        )
    try:
        pages = []
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text and text.strip():
                    pages.append(f"[Page {i+1}]\n{text}")
        return "\n\n".join(pages)
    except Exception as e:
        print(f"  PDF extraction failed: {e}")
        return ""


def ingest_file(
    collection,
    filepath: pathlib.Path,
    subsource: str,
    sector: str = None
) -> int:
    """Chunk and ingest one file into a collection."""
    text = extract_text(filepath)
    if not text.strip():
        print(f"  WARNING: No text from {filepath.name}")
        return 0
    
    chunks = SPLITTER.split_text(text)
    ids, docs, metas = [], [], []
    
    for i, chunk in enumerate(chunks):
        chunk_id = f"{filepath.name}_fw_{i}"
        ids.append(chunk_id)
        docs.append(chunk)
        meta = {
            "source_file": filepath.name,
            "chunk_index": i,
            "subsource": subsource,
            "embedding_model": 
                "nomic-ai/nomic-embed-text-v1.5",
            "dimensions": "1024"
        }
        if sector:
            meta["sector"] = sector
        metas.append(meta)
    
    # Insert in batches of 50
    for start in range(0, len(ids), 50):
        collection.add(
            ids=ids[start:start+50],
            documents=docs[start:start+50],
            metadatas=metas[start:start+50]
        )
    
    return len(chunks)


def main():
    print("=" * 60)
    print(" CHROMADB REBUILD — Fireworks nomic-embed")
    print(" Model: nomic-ai/nomic-embed-text-v1.5")
    print(" Dimensions: 1024")
    print("=" * 60)
    
    # Init Fireworks embedding function
    embed_fn = FireworksEmbeddingFunction()
    
    # Init ChromaDB with Fireworks embeddings
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    
    # Delete existing collections
    print("\nClearing existing collections...")
    for name in ["valuation_methodology",
                 "forensic_and_credit",
                 "india_market_context",
                 "current_deal"]:
        try:
            client.delete_collection(name)
            print(f"  Deleted: {name}")
        except:
            pass
    
    grand_total = 0
    
    # Ingest each collection
    for collection_name, filenames in COLLECTION_MAP.items():
        print(f"\n{'─'*50}")
        print(f"Collection: {collection_name}")
        print(f"{'─'*50}")
        
        col = client.create_collection(
            name=collection_name,
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"}
        )
        
        col_total = 0
        for filename in filenames:
            filepath = KNOWLEDGE_BASE / filename
            if not filepath.exists():
                print(f"  MISSING: {filename}")
                continue
            
            print(f"  Ingesting: {filename}...")
            n = ingest_file(col, filepath, 
                           collection_name)
            print(f"  Chunks: {n}")
            col_total += n
        
        print(f"  Collection total: {col_total} chunks")
        grand_total += col_total
    
    # ICRA files → forensic_and_credit
    print(f"\n{'─'*50}")
    print("ICRA Rating Methodologies → forensic_and_credit")
    print(f"{'─'*50}")
    
    forensic_col = client.get_collection(
        "forensic_and_credit",
        embedding_function=embed_fn
    )
    
    sector_map = {
        "Banks": "banking",
        "Capital Protection": "structured_finance",
        "Commercial Vehicles": "automotive",
        "Hospitals": "healthcare",
        "Hotels": "hospitality",
        "Housing Finance": "housing_finance",
        "IT (Software": "technology",
        "IT-Hardware": "technology_hardware",
        "Infrastructure Investment": "infrastructure",
        "Investment Companies": "investment",
        "Mutual Funds": "asset_management",
        "NBFCs": "nbfc",
        "Retail": "retail",
        "cement": "industrials"
    }
    
    icra_total = 0
    for pdf in sorted(ICRA_FOLDER.glob("*.pdf")):
        sector = "general"
        for key, val in sector_map.items():
            if key.lower() in pdf.name.lower():
                sector = val
                break
        
        print(f"  {pdf.name[:50]}...")
        n = ingest_file(
            forensic_col, pdf,
            "icra_methodology", sector
        )
        print(f"  Chunks: {n} | Sector: {sector}")
        icra_total += n
    
    grand_total += icra_total
    
    # Create empty current_deal collection
    client.create_collection(
        "current_deal",
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"}
    )
    print("\ncurrent_deal: created (empty drop zone)")
    
    # Final summary
    print(f"\n{'='*60}")
    print(" REBUILD COMPLETE")
    print(f"{'='*60}")
    for name in ["valuation_methodology",
                 "forensic_and_credit",
                 "india_market_context"]:
        col = client.get_collection(
            name, embedding_function=embed_fn)
        print(f"  {name}: {col.count()} chunks")
    print(f"  current_deal: 0 (empty)")
    print(f"  Grand total: {grand_total} chunks")
    print(f"  Embedding model: nomic-embed-text-v1.5")
    print(f"  Dimensions: 1024")
    print(f"  Fireworks API credits used: "
          f"~{grand_total // 10} requests")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
