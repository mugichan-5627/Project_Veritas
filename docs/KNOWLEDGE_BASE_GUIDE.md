# Knowledge Base Guide

Do not commit source PDFs to GitHub. Put local PDFs in `knowledge_base/` or the
configured raw-textbook folder and rebuild the vector store locally.

For public users, distribute only the pre-built ChromaDB export:

```powershell
python scripts/package_chromadb.py
python scripts/upload_chromadb_hf.py --repo-id YOUR_USERNAME/project-veritas-knowledge-base
```

Users should extract `chroma_db_export.zip` into `project_veritas/memory/chroma_db/`.
