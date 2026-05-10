import os
import sys
from pathlib import Path

def verify():
    print("Verifying Project Veritas Setup...")
    
    # 1. Check Env
    required = ["NVIDIA_API_KEY", "TAVILY_API_KEY"]
    missing = [r for r in required if not os.environ.get(r)]
    if missing:
        print(f"  [!] Missing Env Vars: {', '.join(missing)}")
    else:
        print("  [OK] Environment Variables")

    # 2. Check Directories
    dirs = ["data/capiq", "knowledge_base", "project_veritas/memory/chroma_db"]
    for d in dirs:
        if not Path(d).exists():
            print(f"  [!] Missing Directory: {d}")
        else:
            print(f"  [OK] Directory: {d}")

    # 3. Check Python Path
    if str(Path.cwd()) not in sys.path:
        print("  [!] Current directory not in sys.path")
    else:
        print("  [OK] Python Path")

    print("\nSetup verification complete.")

if __name__ == "__main__":
    verify()
