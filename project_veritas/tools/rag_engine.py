import chromadb
import os
from pathlib import Path
from project_veritas.memory.rebuild_chromadb_bgem3 import BGEM3Embedding

class ProjectVeritasRAG:
    """
    Institutional wrapper for ChromaDB + BGE-M3 RAG Engine.
    Prevents redundant model loads.
    """
    def __init__(self, knowledge_base_dir: str, chroma_db_dir: str):
        self.kb_dir = Path(knowledge_base_dir)
        self.db_dir = Path(chroma_db_dir)
        
        # This triggers model load
        print("    [RAG] Initializing BGE-M3 Embedding Model...")
        self.embedding_function = BGEM3Embedding()
        self.client = chromadb.PersistentClient(path=str(self.db_dir))
        
    def query(self, collection_name: str, query_text: str, n_results: int = 3):
        try:
            collection = self.client.get_collection(name=collection_name)
            query_emb = self.embedding_function([query_text])
            return collection.query(query_embeddings=query_emb, n_results=n_results)
        except Exception as e:
            print(f"    [!] RAG Query Error ({collection_name}): {e}")
            return {"documents": [[]]}
