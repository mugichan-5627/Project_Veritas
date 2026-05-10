# Project Veritas

An institutional-grade, multi-agent financial due diligence pipeline.

## Overview
Project Veritas automates the heavy lifting of Private Equity due diligence. It leverages specialized Python extraction tools to pull high-fidelity TTM financials, compares them against CapIQ peer sets, validates margins and quality of earnings, and orchestrates a multi-agent LLM debate (Bull vs. Bear) to arrive at a final Investment Committee decision.

## Setup

1. **Clone and Install**
   ```bash
   git clone <repo>
   cd Project_Veritas
   pip install -e .
   ```

2. **Environment Variables**
   Copy `.env.example` to `.env` or set them in your terminal:
   - `NVIDIA_API_KEY`: Required for LLM reasoning (meta/llama-3.3-70b-instruct)
   - `TAVILY_API_KEY`: Required for web search and competitor discovery

3. **Pre-built Embeddings (Recommended)**
Instead of building the database from scratch, you can download the institutional-grade ChromaDB embeddings from Hugging Face:

1. **Download the Database**: 
   Visit huggingface.co/datasets/yoruzuya/project-veritas-knowledge-base/tree/main and download the `chroma_db/` folder.
2. **Place in Project**: 
   Move the folder to `project_veritas/memory/chroma_db/`.



## Usage

Run the full end-to-end pipeline on any US public equity ticker:
```bash
python test_full_pipeline.py AMZN
python test_full_pipeline.py MSFT
python test_full_pipeline.py NVDA
```

## Architecture

- `project_veritas/tools/financials.py`: YFinance TTM extraction and EDGAR fallback.
- `project_veritas/tools/peers.py`: CapIQ and programmatic peer grouping.
- `project_veritas/core/validation.py`: Data integrity and industry margin checks.
- `project_veritas/memory/`: ChromaDB RAG layer for specialized financial rules.
- `test_full_pipeline.py`: Main orchestration script integrating tools and LLM agents.
