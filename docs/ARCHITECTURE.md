# Project Veritas Architecture

Project Veritas is a multi-agent investment diligence pipeline:

1. RAG retrieval over finance methodology documents using BGE-M3 and ChromaDB.
2. Live market and fundamental data from yfinance.
3. CapIQ peer and transaction parsing from local exports.
4. RAG math agent for valuation assumptions.
5. Bull/Bear investment committee debate.
6. IC chair verdict with canonical report rendering.

The terminal path is `test_full_pipeline.py`. The web path uses `pipeline_wrapper.py`
and `report_generator.py` so Streamlit can call the same backend without duplicating
logic.
