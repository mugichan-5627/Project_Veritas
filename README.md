# Project Veritas

An institutional-grade, multi-agent financial due diligence pipeline.

## 🚀 Quick Start

```bash
git clone https://github.com/mugichan-5627/Project_Veritas.git
cd Project_Veritas
pip install -e .
python scripts/download_db.py  # Get pre-built embeddings
streamlit run app.py           # Launch the dashboard
```

## Overview
Project Veritas automates the heavy lifting of Private Equity due diligence. It leverages specialized Python extraction tools to pull high-fidelity TTM financials, compares them against CapIQ peer sets, validates margins and quality of earnings, and orchestrates a multi-agent LLM debate (Bull vs. Bear) to arrive at a final Investment Committee decision.

## 🏆 AMD Pervasive AI Hackathon 2026
Project Veritas demonstrates GPU-accelerated multi-agent AI applied to institutional finance workflows.
- **LLM Inference**: Agents run on AMD MI300X GPUs via Fireworks AI/NVIDIA NIM infrastructure.
- **Novelty**: Real-time IC debate logic, RAG over 40+ textbooks, and forensic red-flag detection.

## Setup

1. **Environment Variables**
   Copy `.env.example` to `.env`:
   - `NVIDIA_API_KEY` or `FIREWORKS_API_KEY`: For Llama 3.3 70B reasoning.
   - `TAVILY_API_KEY`: For web search and peer discovery.

2. **Institutional Knowledge (Embeddings)**
   The system relies on a specialized vector database. You have two options:
   - **Recommended (Automated)**: Run `python scripts/download_db.py`.
   - **Manual**: Download the `chroma_db/` folder from [Hugging Face](https://huggingface.co/datasets/yoruzuya/project-veritas-knowledge-base/tree/main) and place it in `project_veritas/memory/chroma_db/`.
   - **Build from Scratch**: Run `python project_veritas/memory/build_vectordb.py --demo` to build a small sample database.

## Usage

### 📊 Web Dashboard (Recommended)
Run the professional interactive dashboard to visualize the debate and final memo:
```bash
streamlit run app.py
```

### 💻 CLI Pipeline
Run the full end-to-end orchestration on any US public ticker:
```bash
python test_full_pipeline.py AMZN
```

## Architecture

- `project_veritas/agents/`: Logic for Orchestrator, Math, and IC Debate agents.
- `project_veritas/tools/`: Financial extraction (yfinance/EDGAR) and peer analysis.
- `project_veritas/memory/`: ChromaDB RAG layer for financial methodology.
- `app.py`: Streamlit frontend for institutional reporting.
- `docs/research/`: Background research, specifications, and versioning notes.
- `evals/`: Historical evaluation outputs and ticker-specific memos.
