import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

from test_full_pipeline import (
    test_chromadb_rag,
    build_deal_context_live,
    run_nvidia_debate,
    run_nvidia_ic_decision,
    build_canonical_verdict
)
from project_veritas.core.llm_config import get_nvidia_client

logger = logging.getLogger(__name__)

class VeritasPipeline:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback or (lambda step, msg: print(f"[{step}] {msg}"))

    def run(self, ticker: str, sector: str = "Technology"):
        """Runs the full 7-agent pipeline for a given ticker."""
        try:
            results = {}
            
            # Step 1: Initialize RAG Retrieval
            self.progress_callback("RAG_RETRIEVAL", f"Initializing Institutional Knowledge Base for {ticker}...")
            deal_context = build_deal_context_live(ticker, progress_callback=self.progress_callback)
            if not deal_context:
                raise Exception(f"Failed to build deal context for {ticker}")
            
            results["deal_context"] = deal_context
            results["rag_context"] = deal_context.get("rag", {})
            results["data_quality_flags"] = deal_context.get("data_quality_flags", [])
            rag_ctx = results["rag_context"]

            # Step 4: Debate
            self.progress_callback("DEBATE", f"Initiating multi-agent Bull/Bear debate...")
            debate_res = run_nvidia_debate(deal_context, rag_ctx)
            results["debate_results"] = debate_res

            # Step 5: IC Decision
            self.progress_callback("IC_DECISION", f"Running Investment Committee decision agent...")
            ic_decision = run_nvidia_ic_decision(deal_context, debate_res)
            results["ic_decision"] = ic_decision

            # Step 6: Canonical Verdict
            self.progress_callback("FINALIZING", f"Synthesizing final investment memo...")
            final_verdict = build_canonical_verdict(deal_context, ic_decision, debate_res)
            results["final_verdict"] = final_verdict
            
            self.progress_callback("COMPLETE", "Pipeline execution finished successfully.")
            return results

        except Exception as e:
            self.progress_callback("ERROR", f"Pipeline failed: {str(e)}")
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return None

if __name__ == "__main__":
    # Test run
    def cb(s, m): print(f"[{s}] {m}")
    pipe = VeritasPipeline(progress_callback=cb)
    res = pipe.run("AXP", "Financial Services")
    if res:
        print("\nDecision:", res["final_verdict"]["decision"])
