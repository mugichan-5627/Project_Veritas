import os
import sys
import json
import anthropic
from tavily import TavilyClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from memory.memory_agent import get_methodology_context

SYSTEM_PROMPT = """You are a sector specialist at a top-tier Indian PE 
fund. Your job is to assess the market opportunity 
and competitive positioning for a target company. 
You think in terms of TAM, growth vectors, and 
competitive moats. You identify where this company 
sits in its sector and whether the sector itself 
deserves PE capital at this point in the cycle. 

FORMATTING RULES for TAM/SAM/SOM:
- Always use the '$' symbol for currency.
- Use 'B' for Billions and 'M' for Millions.
- Format as a single pipe-separated string: 'TAM: $XXB | SAM: $XXB | SOM: $XXB'.
- Ensure every component has a '$' prefix.
"""

TOOLS = [
    {
        "name": "search_sector_landscape",
        "description": "Tavily search for sector-level intelligence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {"type": "string"},
                "company": {"type": "string"}
            },
            "required": ["sector", "company"]
        }
    },
    {
        "name": "load_precedent_transactions",
        "description": "Reads CapIQ precedent transaction files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {"type": "string"},
                "n_deals": {"type": "integer"}
            },
            "required": ["sector"]
        }
    },
    {
        "name": "query_market_knowledge",
        "description": "Calls memory_agent.get_methodology_context()",
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {"type": "string"}
            },
            "required": ["sector"]
        }
    },
    {
        "name": "assess_competitive_position",
        "description": "Scores competitive position based on available data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "sector": {"type": "string"},
                "revenue_cr": {"type": "number"},
                "ebitda_margin": {"type": "number"},
                "sector_data": {"type": "object"}
            },
            "required": ["company_name", "sector", "revenue_cr", "ebitda_margin", "sector_data"]
        }
    },
    {
        "name": "finalize_market_intel",
        "description": "Outputs the final market intelligence report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {"type": "string"},
                "sector_tam_cr": {"type": "string"},
                "sector_growth_rate": {"type": "string"},
                "sector_pe_activity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                "competitive_position": {"type": "string", "enum": ["LEADER", "CHALLENGER", "FOLLOWER", "NICHE"]},
                "competitive_score": {"type": "number"},
                "moat_assessment": {"type": "string"},
                "key_competitors": {"type": "array", "items": {"type": "string"}},
                "recent_pe_deals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string"},
                            "acquirer": {"type": "string"},
                            "ev_ebitda": {"type": "number"},
                            "year": {"type": "string"}
                        }
                    }
                },
                "implied_entry_multiple_range": {
                    "type": "object",
                    "properties": {
                        "low": {"type": "number"},
                        "high": {"type": "number"},
                        "basis": {"type": "string"}
                    }
                },
                "sector_tailwinds": {"type": "array", "items": {"type": "string"}},
                "sector_headwinds": {"type": "array", "items": {"type": "string"}},
                "pe_investment_thesis": {"type": "string"},
                "data_confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                "data_gaps": {"type": "array", "items": {"type": "string"}},
                "methodology_sources": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["sector", "sector_tam_cr", "sector_growth_rate", "sector_pe_activity", "competitive_position", "competitive_score", "moat_assessment", "key_competitors", "recent_pe_deals", "implied_entry_multiple_range", "sector_tailwinds", "sector_headwinds", "pe_investment_thesis", "data_confidence", "data_gaps", "methodology_sources"]
        }
    }
]

def search_sector_landscape(sector: str, company: str) -> dict:
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        return {"error": "TAVILY_API_KEY not set"}
        
    client = TavilyClient(api_key=tavily_key)
    domains = [
        "bseindia.com", "nseindia.com", "sebi.gov.in",
        "economictimes.indiatimes.com", "livemint.com",
        "businessstandard.com", "moneycontrol.com"
    ]
    
    queries = [
        f"{sector} sector India market size TAM growth rate 2024 2025",
        f"{sector} sector India PE investment deal activity 2024 recent",
        f"{sector} sector India competitive landscape key players market share",
        f"{company} competitive position market share vs peers India"
    ]
    
    results = []
    for q in queries:
        try:
            res = client.search(
                query=q,
                search_depth="advanced",
                max_results=3,
                include_answer=True,
                include_domains=domains
            )
            results.append({
                "query": q,
                "answer": res.get("answer", ""),
                "urls": [r.get("url") for r in res.get("results", [])]
            })
        except Exception as e:
            results.append({"query": q, "error": str(e)})
            
    return {"results": results}

def load_precedent_transactions(sector: str, geography: str = "india") -> dict:
    """Loads cleaned precedent transaction statistics for a sector."""
    from memory.capiq_loader import get_transaction_stats
    
    stats = get_transaction_stats(sector, geography)
    if "error" in stats:
        # Try global if india fails
        if geography == "india":
            stats = get_transaction_stats(sector, "global")
            
    return stats

def query_market_knowledge(sector: str) -> dict:
    try:
        res = get_methodology_context(methodology_type="india_market_context")
        return {"sector": sector, "knowledge": res}
    except Exception as e:
        return {"error": str(e)}

def assess_competitive_position(
    company_name: str,
    sector: str,
    revenue_cr: float,
    ebitda_margin: float,
    sector_data: dict
) -> dict:
    import pandas as pd
    import os
    
    top_level = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    damodaran_path = os.path.join(
      top_level,
      "data", "damodaran", "marginIndia.xls"
    )
    
    sector_median_margin = None
    try:
      df = pd.read_excel(damodaran_path)
      # Fuzzy match sector name
      for idx, row in df.iterrows():
        row_sector = str(row.iloc[0]).lower()
        if any(word in row_sector 
               for word in sector.lower().split()):
          sector_median_margin = float(
            row.iloc[1]) if pd.notna(
            row.iloc[1]) else None
          break
    except:
      pass
    
    # Score margin
    margin_score = 5  # default
    if sector_median_margin and ebitda_margin:
      if ebitda_margin > sector_median_margin * 1.2:
        margin_score = 9
      elif ebitda_margin > sector_median_margin:
        margin_score = 7
      elif ebitda_margin > sector_median_margin * 0.8:
        margin_score = 5
      else:
        margin_score = 3
    
    # Score scale (revenue in crores)
    if revenue_cr > 10000:
      scale_score = 9
    elif revenue_cr > 5000:
      scale_score = 7
    elif revenue_cr > 1000:
      scale_score = 5
    elif revenue_cr > 500:
      scale_score = 3
    else:
      scale_score = 2
    
    overall = (margin_score + scale_score) / 2
    
    if overall >= 8:
      position = "LEADER"
    elif overall >= 6:
      position = "CHALLENGER"
    elif overall >= 4:
      position = "FOLLOWER"
    else:
      position = "NICHE"
    
    return {
      "position": position,
      "scale_score": scale_score,
      "margin_score": margin_score,
      "overall_score": round(overall, 1),
      "sector_median_margin": sector_median_margin,
      "company_margin": ebitda_margin,
      "moat_assessment": (
        "Above-median margins suggest pricing power "
        "or operational efficiency advantage"
        if margin_score >= 7
        else "Margins in line with sector \u2014 "
             "no clear cost or pricing moat identified"
        if margin_score >= 5
        else "Below-median margins \u2014 investigate "
             "structural cost disadvantage"
      ),
      "rationale": (
        f"Scale score {scale_score}/10, "
        f"Margin score {margin_score}/10. "
        f"Company EBITDA margin: "
        f"{ebitda_margin*100:.1f}% vs sector "
        f"median: {sector_median_margin*100:.1f}%"
        if sector_median_margin
        else f"Scale score {scale_score}/10. "
             f"Sector margin benchmark unavailable."
      )
    }

def _execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "search_sector_landscape":
        res = search_sector_landscape(tool_input["sector"], tool_input["company"])
        return json.dumps(res)
    elif tool_name == "load_precedent_transactions":
        res = load_precedent_transactions(tool_input["sector"], tool_input.get("n_deals", 10))
        return json.dumps(res)
    elif tool_name == "query_market_knowledge":
        res = query_market_knowledge(tool_input["sector"])
        return json.dumps(res)
    elif tool_name == "assess_competitive_position":
        res = assess_competitive_position(
            tool_input["company_name"],
            tool_input["sector"],
            tool_input["revenue_cr"],
            tool_input["ebitda_margin"],
            tool_input.get("sector_data", {})
        )
        return json.dumps(res)
    elif tool_name == "finalize_market_intel":
        return json.dumps(tool_input)
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

def run_market_intel_agent(company_name: str, ticker: str = None, sector: str = None, raw_financials: dict = None, biz_intel: dict = None, forensics: dict = None) -> dict:
    client = anthropic.Anthropic()
    
    user_message = f"Please build a market intelligence report for:\nCompany: {company_name}\n"
    if ticker: user_message += f"Ticker: {ticker}\n"
    if sector: user_message += f"Sector: {sector}\n"
    user_message += f"Raw Financials: {json.dumps(raw_financials)}\n"
    user_message += f"Biz Intel: {json.dumps(biz_intel)}\n"
    user_message += f"Forensics: {json.dumps(forensics)}\n"
        
    messages = [{"role": "user", "content": user_message}]
    
    tools_called = 0
    max_iterations = 8
    
    for iteration in range(1, max_iterations + 1):
        try:
            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
        except Exception as e:
            return {"error": str(e)}
            
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    
                    print(f"[Iter {iteration}] Tool called: {tool_name}")
                    
                    if tool_name == "finalize_market_intel":
                        if tools_called < 3:
                            print(f"[Iter {iteration}] Agent tried to finalize too early. Instructing to call more tools.")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps({"error": "You must call at least 3 tools before finalizing."})
                            })
                            continue
                        
                        print(f"[Iter {iteration}] Tool complete. Result length: {len(str(tool_input))} chars \u2713")
                        return tool_input

                    result_str = _execute_tool(tool_name, tool_input)
                    tools_called += 1
                    
                    print(f"[Iter {iteration}] Tool complete. Result length: {len(result_str)} chars")
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })
                    
            messages.append({"role": "assistant", "content": response.content})
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
                
        elif response.stop_reason == "end_turn":
            print(f"[Iter {iteration}] Claude ended without finalize_market_intel.")
            return {"error": "Agent ended without finalize"}
            
    return {"error": f"Agent exceeded {max_iterations} iterations"}

if __name__ == "__main__":
    pass
