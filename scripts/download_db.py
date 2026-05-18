import os
import sys
from huggingface_hub import snapshot_download

def download_db():
    """
    Downloads the institutional ChromaDB embeddings from Hugging Face.
    Ensure you have 'huggingface_hub' installed: pip install huggingface_hub
    """
    repo_id = "yoruzuya/project-veritas-knowledge-base"  # Actual repository
    local_dir = "project_veritas/memory/chroma_db"
    
    print(f"[START] Downloading institutional embeddings from Hugging Face ({repo_id})...")
    
    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            repo_type="dataset", # Or "model" / "space" depending on where you uploaded it
            endpoint="https://huggingface.co"
        )
        print(f"[SUCCESS] Embeddings are located at: {local_dir}")
    except Exception as e:
        print(f"[ERROR] Error downloading from Hugging Face: {e}")
        print("\nManual Fallback:")
        print(f"1. Visit: https://huggingface.co/datasets/{repo_id}")
        print(f"2. Download the contents and place them in: {local_dir}")

if __name__ == "__main__":
    download_db()
