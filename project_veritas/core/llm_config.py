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

def safe_llm_call(messages, temperature=0.1, max_tokens=1500, model=None):
    """
    Wraps LLM calls with exponential backoff and rate-limit handling.
    Crucial for hackathons where API credits or RPM limits are tight.
    """
    import time
    import random
    from openai import RateLimitError, APIError
    
    client = get_nvidia_client()
    if not client:
        raise Exception("LLM Client not initialized. Check API keys.")

    target_model = model or get_nvidia_model()
    
    # Check if we should fallback to 8B for better throughput if it's not a 'critical' reasoning step
    # but for now, we'll just stick to the requested model with retries.
    
    max_retries = 5
    base_delay = 2 # Start with 2 seconds
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise Exception("Too Many Requests. Rate limited. Try after a while.")
            
            # Exponential backoff with jitter
            delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
            print(f"    [RATE LIMIT] Hit limit on {target_model}. Waiting {delay:.1f}s (Attempt {attempt+1}/{max_retries})...")
            time.sleep(delay)
            
        except APIError as e:
            if "rate limit" in str(e).lower():
                if attempt == max_retries - 1:
                    raise Exception("Rate limit hit. Please check your API quota.")
                delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                time.sleep(delay)
                continue
            raise e
        except Exception as e:
            raise e
            
    return None
