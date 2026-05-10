from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_PATH = PROJECT_ROOT / "project_veritas" / "memory" / "chroma_db"
REPORTS_DIR = PROJECT_ROOT / "reports"


def llm_backend() -> str:
    if os.getenv("FIREWORKS_API_KEY"):
        return "Fireworks AI"
    if os.getenv("NVIDIA_API_KEY"):
        return "NVIDIA NIM"
    return "offline"


def llm_model() -> str:
    if os.getenv("FIREWORKS_API_KEY"):
        return os.getenv("FIREWORKS_MODEL", "accounts/fireworks/models/llama-v3p3-70b-instruct")
    return os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
