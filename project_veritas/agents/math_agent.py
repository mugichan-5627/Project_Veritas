import os
import json
import re
import time
import logging
from typing import Dict, Any, Optional
from project_veritas.core.llm_config import get_nvidia_model, get_nvidia_client, get_embedding_model, safe_llm_call

logger = logging.getLogger(__name__)

SECTOR_MULTIPLE_FLOORS = {
    "Technology": 18,
    "Healthcare": 14,
    "Consumer Defensive": 13,
    "Consumer Cyclical": 12,
    "Industrials": 12,
    "Financial Services": 10,
    "Communication Services": 14,
    "Energy": 8,
    "Utilities": 9,
    "Basic Materials": 9,
    "Real Estate": 14,
}

SECTOR_MULTIPLE_CEILINGS = {
    "Technology": 45,
    "Healthcare": 30,
    "Consumer Defensive": 22,
    "Consumer Cyclical": 25,
    "Industrials": 20,
    "Financial Services": 16,
    "Communication Services": 25,
    "Energy": 14,
    "Utilities": 16,
    "Basic Materials": 14,
    "Real Estate": 22,
}

MATH_AGENT_SYSTEM_PROMPT = """
You are a PE valuation analyst. You will receive:
1. Company financial data
2. Retrieved passages from institutional valuation 
   textbooks (Damodaran, McKinsey, Rosenbaum)

Your job:
- READ the retrieved passages carefully
- IDENTIFY which methodology applies to this company
  based on what the passages say, not what you assume
- DERIVE the fair multiple from the passages' logic
- CITE the specific passage that justifies your multiple

Rules:
- If retrieved passages discuss growth-adjusted multiples,
  apply that framework to this specific company's data
- If passages suggest EV/Revenue over EV/EBITDA for 
  pre-profit or high-growth companies, use that
- Every number you produce must trace back to a 
  retrieved passage or a calculation from the data
- NEVER produce a multiple without explaining which 
  retrieved source guided that choice
- If passages conflict, explain the conflict and 
  explain your resolution

Output format — you MUST include:
{
  "fair_multiple": <number>,
  "multiple_type": "EV/EBITDA" or "EV/Revenue" or "P/E",
  "methodology_source": "exact quote or passage reference",
  "reasoning": "how you applied the passage to this data",
  "confidence": "HIGH/MEDIUM/LOW",
  "why_this_methodology": "why this framework fits this company",
  "fair_equity_value_m": <number>,
  "wacc_pct": <number>,
  "forensic_commentary": {"cash_conversion": "string", "margin_safety": "string"}
}
"""

def build_math_agent_message(company_data, rag_chunks):
    # Format retrieved knowledge clearly
    knowledge_section = ""
    if rag_chunks:
        knowledge_section = "\n\nRELEVANT KNOWLEDGE BASE PASSAGES:\n"
        for i, chunk in enumerate(rag_chunks[:5]):
            knowledge_section += (
                f"\n[{i+1}] FROM: {chunk['source']}\n"
                f"RELEVANCE: {chunk['relevance']:.0%}\n"
                f"TEXT: {chunk['text']}\n"
                f"{'─'*40}\n"
            )
    else:
        knowledge_section = (
            "\n\nWARNING: No knowledge base passages "
            "retrieved. Apply conservative methodology "
            "and flag low confidence.\n"
        )
    
    return f"""
Company: {company_data.get('company_name', 'Unknown')} ({company_data.get('ticker', 'N/A')})
Sector: {company_data.get('sector', 'Unknown')}
Revenue: ${company_data.get('revenue', 0)/1e6:.1f}M
Revenue Growth YoY: {company_data.get('revenue_growth', 0)*100:.1f}%
EBITDA: ${company_data.get('ebitda_m', 0):.1f}M  
EBITDA Margin: {company_data.get('ebitda_margin', 0)*100:.1f}%
Net Debt: ${company_data.get('total_debt_m', 0):.1f}M
Net Debt: ${company_data.get('total_debt_m', 0):.1f}M
Peer Median EV/EBITDA: {company_data.get('peer_median_multiple', 15):.1f}x
{knowledge_section}

Based on the retrieved passages above, determine the 
appropriate valuation methodology and fair multiple 
for this specific company. Justify every number 
by citing the retrieved text directly.
"""

def run_math_agent(ticker: str, industry: str, raw_data: dict, peers: list = None, nvidia_client=None, embedding_model=None, rag_chunks: list = None):
    """
    Queries ChromaDB for industry-specific valuation rules and executes explicit math adjustments.
    Hardened with sector-specific floors and ceilings.
    """
    try:
        client = nvidia_client or get_nvidia_client()
        if not client:
            return None

        # RAG context is now passed in as rag_chunks
        
        # FIG Outlier Detection
        peer_median_pe = raw_data.get("pe_ratio") or 14.0
        if raw_data.get("is_financial") and peers:
            primary_peers = [p for p in peers if p.get("peer_type", "PRIMARY") == "PRIMARY"]
            peer_pes = [p.get("raw_pe") for p in primary_peers if p.get("raw_pe") and 0 < p.get("raw_pe") < 50]
            if peer_pes:
                peer_median_pe = sorted(peer_pes)[len(peer_pes)//2]

        # Use the new dynamic message building logic
        prompt = build_math_agent_message(raw_data, rag_chunks)
        
        # safe_llm_call handles retries and rate limits internally
        response = safe_llm_call(
            messages=[
                {"role": "system", "content": MATH_AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.05
        )
        
        if response:
            try:
                txt = response.choices[0].message.content
                match = re.search(r'(\{[\s\S]*\})', txt)
                if match:
                    cleaned_json = match.group(1).replace("\n", " ").replace("  ", " ")
                    res = json.loads(cleaned_json)
                    
                    # Apply Institutional Guardrails (Fix requested)
                    fair_multiple = res.get("fair_multiple") or res.get("fair_p_book_multiple")
                    if fair_multiple:
                        try:
                            fair_multiple = float(fair_multiple)
                        except:
                            fair_multiple = 15.0
                        sector = raw_data.get('sector', 'Industrials')
                        floor = SECTOR_MULTIPLE_FLOORS.get(sector, 8)
                        ceiling = SECTOR_MULTIPLE_CEILINGS.get(sector, 35)

                        if fair_multiple < floor:
                            print(f"      [!] WARNING: Multiple {fair_multiple:.1f}x below sector floor {floor}x — clamping")
                            fair_multiple = floor
                            
                        if fair_multiple > ceiling:
                            print(f"      [!] WARNING: Multiple {fair_multiple:.1f}x above sector ceiling {ceiling}x — clamping")
                            fair_multiple = ceiling
                        
                        # Update the result and potentially recalculate equity value
                        if "fair_multiple" in res: res["fair_multiple"] = fair_multiple
                        if "fair_p_book_multiple" in res: res["fair_p_book_multiple"] = fair_multiple
                        
                    return res
            except Exception as e:
                logger.error(f"Math Agent parse error: {e}")
    except Exception as e:
        logger.error(f"Math Agent exception: {e}")
    return None
