import json
import logging
from typing import Dict, Any, Optional

from project_veritas.agents.valuation_agent import run_valuation_agent
from project_veritas.agents.debate_agents import run_debate
from project_veritas.agents.ic_agent import run_ic_agent

logger = logging.getLogger(__name__)

class DueDiligenceOrchestrator:
    def __init__(self, anthropic_api_key: str = None):
        self.api_key = anthropic_api_key
        # Initialize the shared mailbox / deal context
        self.deal_context = {
            "company_name": "",
            "ticker": "",
            "sector": "",
            "raw_financials": {},
            "biz_intel": {},
            "forensics": {},
            "adjusted_ebitda": None,
            "market_intel": {},
            "management": {},
            "valuation": {},
            "debate": {},
            "ic_decision": {},
            "final_recommendation": {}
        }
    
    def _run_biz_intel(self) -> Dict[str, Any]:
        from project_veritas.agents.biz_intel_agent import run_biz_intel_agent
        result = run_biz_intel_agent(
            company_name=self.deal_context["company_name"],
            ticker=self.deal_context.get("ticker"),
            sector=self.deal_context.get("sector")
        )
        return result

    def _run_forensics(self) -> Dict[str, Any]:
        from project_veritas.agents.financial_forensics_agent import run_forensics_agent
        
        result = run_forensics_agent(
            company_name=self.deal_context["company_name"],
            ticker=self.deal_context.get("ticker", ""),
            sector=self.deal_context.get("sector", ""),
            raw_financials=self.deal_context.get("raw_financials", {}),
            biz_intel=self.deal_context.get("biz_intel", {})
        )
        
        self.deal_context["forensics"] = result
        
        # Critical handoff to valuation agent
        self.deal_context["adjusted_ebitda"] = result.get("adjusted_ebitda_cr")
        self.deal_context["quality_of_earnings"] = result.get("quality_of_earnings")
        
        print(f"\nORCHESTRATOR: Forensics complete")
        print(f"  Reported EBITDA:  Rs {result.get('reported_ebitda_cr')} Cr")
        print(f"  Adjusted EBITDA:  Rs {result.get('adjusted_ebitda_cr')} Cr")
        print(f"  Forensic Score:   {result.get('forensic_score')}/100")
        print(f"  QoE:              {result.get('quality_of_earnings')}")
        
        return result

    def _run_market_intel(self) -> Dict[str, Any]:
        from project_veritas.agents.market_intel_agent import run_market_intel_agent
        
        result = run_market_intel_agent(
            company_name=self.deal_context["company_name"],
            ticker=self.deal_context.get("ticker", ""),
            sector=self.deal_context.get("sector", ""),
            raw_financials=self.deal_context.get("raw_financials", {}),
            biz_intel=self.deal_context.get("biz_intel", {}),
            forensics=self.deal_context.get("forensics", {})
        )
        
        self.deal_context["market_intel"] = result
        
        if "implied_entry_multiple_range" in result:
            self.deal_context["implied_entry_multiple"] = result["implied_entry_multiple_range"]
        
        print(f"\nORCHESTRATOR: Market Intel complete")
        print(f"  Sector: {result.get('sector')}")
        print(f"  Position: {result.get('competitive_position')}")
        print(f"  PE Activity: {result.get('sector_pe_activity')}")
        print(f"  Implied multiple: {result.get('implied_entry_multiple_range')}")
        
        return result

    def _run_management(self) -> Dict[str, Any]:
        from project_veritas.agents.management_agent import run_management_agent
        
        result = run_management_agent(
            deal_context=self.deal_context
        )
        
        self.deal_context["management"] = result
        
        print(f"\nORCHESTRATOR: Management Assessment complete")
        print(f"  Score: {result.get('management_score')}/100")
        print(f"  Board: {result.get('board_independence')}")
        print(f"  Flags: {len(result.get('governance_flags', []))} flags found")
        
        return result

    def _run_valuation(self) -> Dict[str, Any]:
        result = run_valuation_agent(self.deal_context)
        
        self.deal_context["valuation"] = result
        
        print(f"\nORCHESTRATOR: Valuation complete")
        print(f"  Decision: {result.get('pe_decision')}")
        print(f"  Max Price: Rs {result.get('do_not_exceed_price_cr')} Cr")
        print(f"  Convergence: {result.get('convergence_quality')} ({result.get('convergence_spread_pct')}%)")
        
        return result

    def _run_debate(self) -> Dict[str, Any]:
        """
        Step 6: Bull vs Bear IC Debate (Agent 6A vs 6B).
        TauricResearch/TradingAgents-inspired structured debate.
        """
        result = run_debate(
            deal_context=self.deal_context,
            max_rounds=3,
            api_key=self.api_key
        )
        
        self.deal_context["debate"] = result
        
        print(f"\nORCHESTRATOR: IC Debate complete")
        print(f"  Rounds: {result.get('total_rounds')}")
        print(f"  Consensus: {result.get('consensus_type')}")
        
        return result

    def _run_ic_decision(self) -> Dict[str, Any]:
        """
        Step 7: Investment Committee final decision (Agent 7).
        TauricResearch/TradingAgents Portfolio Manager pattern with
        SQLite-backed reflection memory.
        """
        result = run_ic_agent(
            deal_context=self.deal_context,
            debate_result=self.deal_context.get("debate", {}),
            api_key=self.api_key
        )
        
        self.deal_context["ic_decision"] = result
        self.deal_context["final_recommendation"] = result
        
        print(f"\nORCHESTRATOR: IC Decision complete")
        print(f"  Decision: {result.get('decision')}")
        print(f"  Conviction: {result.get('conviction_level')}")
        print(f"  Entry Price: Rs {result.get('recommended_entry_price_cr')} Cr")
        
        return result

    def run_full_dd(self, company_name: str, ticker: Optional[str] = None, sector: Optional[str] = None, raw_financials: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the full PE due diligence sequence using the Mailbox Protocol.
        
        Pipeline:
          Step 1: Business Intelligence (Agent 1)
          Step 2: Financial Forensics (Agent 2)
          Step 3: Market Intelligence (Agent 3)
          Step 4: Management Assessment (Agent 4)
          Step 5: Valuation Engine (Agent 5)
          Step 6: Bull vs Bear Debate (Agent 6A vs 6B)
          Step 7: IC Decision (Agent 7)
        """
        logger.info(f"Starting full due diligence for {company_name}")
        self.deal_context["company_name"] = company_name
        self.deal_context["ticker"] = ticker
        self.deal_context["sector"] = sector
        self.deal_context["raw_financials"] = raw_financials or {}
        
        # Step 1: Business Intelligence
        logger.info("Step 1: Running Business Intelligence Agent...")
        result = self._run_biz_intel()
        self.deal_context["biz_intel"] = result
        
        if result.get("sector"):
            self.deal_context["sector"] = result["sector"]
        if result.get("promoter_holding_pct"):
            self.deal_context["promoter_holding"] = result["promoter_holding_pct"]
        
        print(f"ORCHESTRATOR: Biz Intel complete")
        print(f"  Company: {result.get('company_name')}")
        print(f"  Sector: {result.get('sector')}")
        print(f"  Confidence: {result.get('data_confidence')}")
        
        # Step 2: Financial Forensics
        logger.info("Step 2: Running Financial Forensics Agent...")
        self._run_forensics()
        
        # Step 3: Market Intelligence
        logger.info("Step 3: Running Market Intelligence Agent...")
        self._run_market_intel()
        
        # Step 4: Management Assessment
        logger.info("Step 4: Running Management Assessment Agent...")
        self._run_management()
        
        # Step 5: Valuation
        logger.info("Step 5: Running Valuation Agent...")
        self._run_valuation()
        
        # Step 6: Bull vs Bear IC Debate
        logger.info("Step 6: Running IC Debate (Deal Champion vs Risk Partner)...")
        self._run_debate()
        
        # Step 7: IC Decision
        logger.info("Step 7: Running Investment Committee Decision...")
        self._run_ic_decision()
        
        logger.info("Due diligence complete — all 7 agents finished.")
        return self.deal_context

if __name__ == "__main__":
    print("Orchestrator ready — 7-agent pipeline.")
