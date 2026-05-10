import time
import sys
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

from project_veritas.tools.rag_engine import ProjectVeritasRAG

def test_init():
    print("Starting RAG Init Test...")
    start = time.time()
    
    kb_path = PROJECT_ROOT / "knowledge_base"
    db_path = PROJECT_ROOT / "project_veritas" / "memory" / "chroma_db"
    
    try:
        rag = ProjectVeritasRAG(str(kb_path), str(db_path))
        end = time.time()
        print(f"RAG Initialized in {end - start:.2f} seconds.")
        
        print("Testing Query...")
        res = rag.query("valuation_methodology", "How to value a bank?")
        print(f"Query successful. Found {len(res.get('documents', [[]])[0])} results.")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_init()
