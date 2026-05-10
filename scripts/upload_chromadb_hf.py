from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import HfApi, create_repo


def main():
    parser = argparse.ArgumentParser(description="Upload ChromaDB zip to a Hugging Face dataset repo.")
    parser.add_argument("--repo-id", required=True, help="Example: username/project-veritas-knowledge-base")
    parser.add_argument("--zip", type=Path, default=Path("chroma_db_export.zip"))
    args = parser.parse_args()

    if not args.zip.exists():
        raise SystemExit(f"Zip file not found: {args.zip}")

    create_repo(args.repo_id, repo_type="dataset", exist_ok=True)
    api = HfApi()
    api.upload_file(
        path_or_fileobj=str(args.zip),
        path_in_repo=args.zip.name,
        repo_id=args.repo_id,
        repo_type="dataset",
    )
    readme = """---
license: mit
task_categories:
  - text-retrieval
language:
  - en
tags:
  - finance
  - private-equity
  - due-diligence
  - embeddings
  - bge-m3
---

# Project Veritas Knowledge Base

Pre-built ChromaDB vector store for Project Veritas.

## Usage

1. Download `chroma_db_export.zip`.
2. Extract it to `project_veritas/memory/chroma_db/`.
3. Run `python scripts/verify_setup.py`.

The original source PDFs are not included.
"""
    api.upload_file(
        path_or_fileobj=readme.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=args.repo_id,
        repo_type="dataset",
    )
    print(f"Uploaded {args.zip} to https://huggingface.co/datasets/{args.repo_id}")


if __name__ == "__main__":
    main()
