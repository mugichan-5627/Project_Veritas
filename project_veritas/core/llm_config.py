import os
import sys
from pathlib import Path

# Add project root to sys.path if not already there
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_EMBEDDING_MODEL_CACHE = None

def get_nvidia_model():
    """Returns the correct model based on which API key is active at runtime."""
    if os.environ.get("FIREWORKS_API_KEY"):
        return os.environ.get("FIREWORKS_MODEL", "accounts/fireworks/models/llama-v3p3-70b-instruct")
    return os.environ.get("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")

def get_nvidia_client():
    """Creates an OpenAI-compatible client, preferring Fireworks for AMD credits."""
    from openai import OpenAI

    # If the key starts with fw_, automatically treat it as Fireworks
    nv_key = os.environ.get("NVIDIA_API_KEY", "")
    if nv_key.startswith("fw_") and not os.environ.get("FIREWORKS_API_KEY"):
        os.environ["FIREWORKS_API_KEY"] = nv_key

    fireworks_key = os.environ.get("FIREWORKS_API_KEY")
    if fireworks_key:
        return OpenAI(
            base_url=os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"),
            api_key=fireworks_key
        )

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        print("    [WARNING] FIREWORKS_API_KEY/NVIDIA_API_KEY not set. LLM agents will be bypassed.")
        return None

    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )

def get_embedding_model():
    global _EMBEDDING_MODEL_CACHE
    if _EMBEDDING_MODEL_CACHE is None:
        from project_veritas.tools.rag_engine import ProjectVeritasRAG
        kb_path = PROJECT_ROOT / "knowledge_base"
        db_path = PROJECT_ROOT / "project_veritas" / "memory" / "chroma_db"
        _EMBEDDING_MODEL_CACHE = ProjectVeritasRAG(str(kb_path), str(db_path))
    return _EMBEDDING_MODEL_CACHE
