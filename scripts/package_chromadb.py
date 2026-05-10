from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHROMA = PROJECT_ROOT / "project_veritas" / "memory" / "chroma_db"


def main():
    parser = argparse.ArgumentParser(description="Package Project Veritas ChromaDB for Hugging Face distribution.")
    parser.add_argument("--source", type=Path, default=DEFAULT_CHROMA)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "chroma_db_export.zip")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"ChromaDB directory not found: {args.source}")
    if args.output.exists():
        args.output.unlink()

    archive_base = args.output.with_suffix("")
    shutil.make_archive(str(archive_base), "zip", root_dir=args.source)
    print(f"Created {args.output}")


if __name__ == "__main__":
    main()
