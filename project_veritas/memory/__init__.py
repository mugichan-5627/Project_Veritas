# project_veritas/memory/__init__.py
# ─────────────────────────────────────────────────────────────────────
# PURPOSE: Registers memory/ as a Python package.
#
# PHASE 2 PLAN:
#   This folder will house our ChromaDB vector database integration.
#   ChromaDB will store embeddings (numerical fingerprints) of:
#     - Damodaran datasets (so agents can query "What's the median
#       EV/EBITDA for Indian IT companies?" without reading raw Excel)
#     - Knowledge base PDFs (so agents can search for relevant
#       methodology passages from McKinsey, Damodaran, etc.)
#     - ICRA rating frameworks (so the credit agent knows which
#       criteria apply to which sector)
#     - Past analysis outputs (institutional memory — the system
#       remembers what it has already analyzed)
#
#   Think of ChromaDB as the "institutional memory" of the fund.
#   A new analyst can ask "Have we looked at this sector before?"
#   and the system retrieves relevant past work.
# ─────────────────────────────────────────────────────────────────────
