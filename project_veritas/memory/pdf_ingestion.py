import os
import sys
import argparse
import chromadb
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Paths
KNOWLEDGE_BASE_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")
ICRA_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "icra_methodologies")
CURRENT_DEAL_DIR = os.path.join(PROJECT_ROOT, "data", "current_deal")
CHROMA_DB_DIR = os.path.join(PROJECT_ROOT, "project_veritas", "memory", "chroma_db")

# Dynamically build collections by scanning KNOWLEDGE_BASE_DIR
COLLECTIONS = {
    "valuation_methodology": [],
    "forensic_and_credit": [],
    "india_market_context": [],
    "macro_pe_industry": []  # New collection for general PE reports
}

if os.path.exists(KNOWLEDGE_BASE_DIR):
    for f in os.listdir(KNOWLEDGE_BASE_DIR):
        file_path = os.path.join(KNOWLEDGE_BASE_DIR, f)
        if not os.path.isfile(file_path):
            continue
            
        f_lower = f.lower()
        
        # Categorization logic based on keywords
        if any(kw in f_lower for kw in ["valuation", "capital", "model", "dcf", "waterfall"]):
            COLLECTIONS["valuation_methodology"].append(file_path)
        elif any(kw in f_lower for kw in ["shenanigan", "credit", "rating", "liquidity", "term sheet"]):
            COLLECTIONS["forensic_and_credit"].append(file_path)
        elif any(kw in f_lower for kw in ["india", "ai"]):
            COLLECTIONS["india_market_context"].append(file_path)
        else:
            # Everything else goes to macro PE/industry
            COLLECTIONS["macro_pe_industry"].append(file_path)

if os.path.exists(ICRA_DIR):
    COLLECTIONS["forensic_and_credit"].extend([
        os.path.join(ICRA_DIR, f) for f in os.listdir(ICRA_DIR) if f.endswith('.pdf')
    ])

def extract_text_from_file(file_path: str) -> list[dict]:
    """
    Extracts text page by page from a PDF, or line by line for TXT.
    Returns a list of dicts: [{"page": 1, "text": "..."}, ...]
    """
    if not os.path.exists(file_path):
        print(f"  [!] File not found: {os.path.basename(file_path)}")
        return []
        
    try:
        if file_path.lower().endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            return [{"page": 1, "text": text}]
            
        elif file_path.lower().endswith('.pdf'):
            reader = PdfReader(file_path)
            pages = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append({"page": i + 1, "text": text})
            return pages
        else:
            print(f"  [!] Unsupported file type: {os.path.basename(file_path)}")
            return []
    except Exception as e:
        print(f"  [!] Failed to read {os.path.basename(file_path)}: {e}")
        return []

def chunk_text(pages: list[dict], filename: str, collection_name: str) -> list[dict]:
    """
    Splits text into 512-token chunks with 64-token overlap using LangChain.
    Preserves page estimation and adds strict metadata.
    """
    # Using characters roughly equivalent to tokens for the text splitter (4 chars ≈ 1 token)
    # 512 tokens ≈ 2000 chars. 64 tokens ≈ 250 chars.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000, 
        chunk_overlap=250,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = []
    chunk_index = 0
    
    for p in pages:
        page_chunks = splitter.split_text(p["text"])
        for chunk_text in page_chunks:
            # Skip very small useless chunks
            if len(chunk_text.strip()) < 20:
                continue
                
            chunks.append({
                "content": chunk_text,
                "metadata": {
                    "source_file": filename,
                    "chunk_index": chunk_index,
                    "page_estimate": p["page"],
                    "collection": collection_name
                }
            })
            chunk_index += 1
            
    return chunks

def ingest_collection(client: chromadb.Client, collection_name: str, file_paths: list[str], clear_first: bool = False) -> tuple[int, int]:
    """
    Ingests a list of PDFs into a specific ChromaDB collection.
    Handles extraction, chunking, and database insertion.
    """
    if clear_first:
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass # Collection might not exist yet
            
    collection = client.get_or_create_collection(name=collection_name)
    
    total_chunks = 0
    successful_files = 0
    
    for pdf_path in file_paths:
        filename = os.path.basename(pdf_path)
        print(f"Ingesting: {filename}...")
        
        pages = extract_text_from_file(pdf_path)
        if not pages:
            continue
            
        print(f"  Text extracted: {len(pages)} pages")
        
        chunks = chunk_text(pages, filename, collection_name)
        if not chunks:
            continue
            
        print(f"  Chunks created: {len(chunks)}")
        
        # Prepare for ChromaDB insertion
        ids = [f"{filename}_chunk_{c['metadata']['chunk_index']}" for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        
        # ChromaDB limits batch sizes to 41666, we'll use 5000 to be safe and avoid memory spikes
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            collection.add(
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )
            
        print(f"  Stored in: {collection_name}")
        sample_text = documents[0][:100].encode('ascii', 'replace').decode('ascii')
        print(f"  Sample chunk [0]: '{sample_text}...'")
        
        total_chunks += len(chunks)
        successful_files += 1
        
    return total_chunks, successful_files

def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs into ChromaDB for Project Veritas RAG.")
    parser.add_argument("--collection", type=str, help="Specify a single collection to ingest (e.g., current_deal)")
    parser.add_argument("--clear-first", action="store_true", help="Wipe previous data for the collection before ingesting")
    args = parser.parse_args()

    # Initialize persistent ChromaDB client
    os.makedirs(CHROMA_DB_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    
    summary = {}

    if args.collection == "current_deal":
        # Handle dynamic current_deal ingestion
        if not os.path.exists(CURRENT_DEAL_DIR):
            os.makedirs(CURRENT_DEAL_DIR, exist_ok=True)
            
        deal_files = [os.path.join(CURRENT_DEAL_DIR, f) for f in os.listdir(CURRENT_DEAL_DIR) if f.endswith('.pdf')]
        chunks, files = ingest_collection(client, "current_deal", deal_files, clear_first=args.clear_first)
        summary["current_deal"] = (chunks, files)
        
    elif args.collection:
        # Handle a specific standard collection
        if args.collection in COLLECTIONS:
            chunks, files = ingest_collection(client, args.collection, COLLECTIONS[args.collection], clear_first=args.clear_first)
            summary[args.collection] = (chunks, files)
        else:
            print(f"Unknown collection: {args.collection}")
            sys.exit(1)
            
    else:
        # Run standard ingestion for all base collections
        for coll_name, file_paths in COLLECTIONS.items():
            chunks, files = ingest_collection(client, coll_name, file_paths, clear_first=args.clear_first)
            summary[coll_name] = (chunks, files)
            
        # Ensure current_deal exists but leave it empty by default
        client.get_or_create_collection(name="current_deal")
        summary["current_deal"] = (0, 0)

    # Print Final Summary
    print("\n" + "=" * 39)
    print(" INGESTION COMPLETE")
    
    total_chunks = 0
    total_files = 0
    for coll_name in ["valuation_methodology", "forensic_and_credit", "india_market_context", "macro_pe_industry", "current_deal"]:
        if coll_name in summary:
            chunks, files = summary[coll_name]
            if coll_name == "current_deal" and chunks == 0:
                print(f" {coll_name:<22} -> {chunks} chunks (empty — drop zone)")
            else:
                print(f" {coll_name:<22} -> {chunks} chunks from {files} PDFs")
            total_chunks += chunks
            total_files += files

    print(f" Total: {total_chunks} chunks from {total_files} documents")
    print(f" ChromaDB persisted to: memory/chroma_db/")
    print("=" * 39)

if __name__ == "__main__":
    main()
