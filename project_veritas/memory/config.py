import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = PROJECT_ROOT / "project_veritas" / "memory"
CHROMA_DB_PATH = MEMORY_DIR / "chroma_db"
RAW_DATA_DIR = MEMORY_DIR / "raw_textbooks"

# Embedding Model
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"

# Collection Names
COLLECTIONS = [
    "valuation_methodology",
    "forensic_and_credit"
]
