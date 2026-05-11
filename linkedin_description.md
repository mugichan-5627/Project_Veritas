# Project Veritas: Institutional-Grade AI Due Diligence Engine

**Project Overview**
Project Veritas is a high-fidelity, multi-agent AI framework designed to automate institutional-grade investment due diligence. It replicates the analytical rigor of a Private Equity investment committee by orchestrating seven specialized AI agents that perform real-time financial analysis, adversarial risk assessment, and valuation modeling.

**Core Features & Technical Implementation**
- **Multi-Agent Pipeline Architecture**: Developed a modular orchestrator that manages data flow between specialized agents, including a Deal Champion (Bull), Risk Partner (Bear), and an Investment Committee (IC) Decision Agent.
- **Dynamic Valuation Logic**: Implemented a sector-aware valuation engine that dynamically switches between Industrial (EBITDA/EV) and Financial (P/Book/ROE) methodologies, incorporating market-premium recognition and peer benchmarking.
- **Hybrid RAG System**: Built a Retrieval-Augmented Generation (RAG) system using ChromaDB and BGE-M3 embeddings to ingest and retrieve knowledge from institutional-grade investment reports and proprietary documents.
- **Adversarial Multi-Round Debate**: Engineered a self-correcting "Debate Stage" where AI agents stress-test investment hypotheses in multiple rounds, forcing consensus through evidence-based argumentation and conviction scoring.
- **Resilient Inference Hardening**: Implemented a robust LLM call wrapper with jittered exponential backoff and rate-limit handling to ensure stable execution during high-frequency API operations on NVIDIA NIM and Fireworks AI infrastructure.
- **Institutional Guardrails**: Integrated rigorous mathematical verification layers to prevent "hallucinated" valuation metrics, ensuring all derived outputs (WACC, CoE, Fair Value) align with fundamental finance principles.

**Technologies Used**
- **Back-End**: Python, Streamlit, ChromaDB, yfinance API
- **AI/LLM**: Llama 3.3 70B (via NVIDIA NIM/Fireworks AI), BGE-M3 Embeddings
- **Infrastructure**: AMD Instinct GPU infrastructure, Streamlit Cloud deployment

**Impact for Recruiters**
This project demonstrates proficiency in building production-ready AI applications that solve complex, high-stakes business problems. It showcases deep expertise in agentic workflows, prompt engineering for financial accuracy, and the ability to harden AI systems for institutional reliability.
