import os
import sys
from pathlib import Path
import chromadb

# Add project root to path
PROJECT_ROOT = Path(r"C:\Users\Moosa\Downloads\Project_Veritas")
sys.path.insert(0, str(PROJECT_ROOT))

from project_veritas.memory.rebuild_chromadb_bgem3 import BGEM3Embedding

def test_query():
    print("=" * 60)
    print("TESTING CHROMADB BGE-M3 EMBEDDINGS")
    print("=" * 60)
    
    db_path = PROJECT_ROOT / "project_veritas" / "memory" / "chroma_db"
    
    print("1. Loading BGE-M3 embedding function...")
    embedding_fn = BGEM3Embedding()
    
    print("\n2. Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=str(db_path))
    
    # Let's test a few queries that an agent might ask
    test_queries = [
        ("NVIDIA or AI semiconductor market trends", "forensic_and_credit"),
        ("How to adjust EBITDA for aggressive revenue recognition?", "valuation_methodology"),
        ("What are the key governance red flags for a tech company?", "forensic_and_credit")
    ]
    
    for query_text, collection_name in test_queries:
        print(f"\n{'-'*60}")
        print(f"QUERY: '{query_text}'")
        print(f"COLLECTION: {collection_name}")
        print(f"{'-'*60}")
        
        try:
            # Bypass ChromaDB's embedding function requirement by calculating it manually
            collection = client.get_collection(name=collection_name)
            
            query_emb = embedding_fn([query_text])
            
            results = collection.query(
                query_embeddings=query_emb,
                n_results=2
            )
            
            if not results['documents'] or not results['documents'][0]:
                print("No results found.")
                continue
                
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            )):
                source = metadata.get("source", "Unknown")
                print(f"\n[Result {i+1}] Source: {source} (Distance: {distance:.4f})")
                
                # Print preview of the chunk (max 300 chars)
                preview = doc.replace('\n', ' ').strip()
                if len(preview) > 300:
                    preview = preview[:300] + "..."
                print(f"Text: {preview}")
                
        except Exception as e:
            print(f"Error querying collection: {e}")

if __name__ == "__main__":
    test_query()
