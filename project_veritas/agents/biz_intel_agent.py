import os
import sys
import json
import anthropic
from tavily import TavilyClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from memory.market_data_loader import fetch_indian_market_data
from memory.market_sentiment_loader import fetch_analyst_sentiment
from memory.memory_agent import get_methodology_context

SYSTEM_PROMPT = """You are a senior business analyst at a top-tier Indian PE fund. Your job is to build a comprehensive business intelligence brief on a target company. You establish the factual foundation that every other agent depends on.
You are thorough, skeptical, and never speculate beyond what sources confirm.

QUALITY RULES:
1. Never speculate about promoter background — only state what sources confirm.
2. If promoter holding % unavailable flag as data gap — do not estimate.
3. PE investment history must be verified — not inferred from company size.
4. Recent developments must be from last 12 months.
5. data_confidence = HIGH only if 3+ sources confirm key facts — otherwise MEDIUM.
"""

TOOLS = [
    {
        "name": "fetch_market_data",
        "description": "Fetches market cap, sector, current price, beta, EV/EBITDA, and business summary for Indian listed companies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker symbol, e.g., MANKIND.NS"}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "fetch_analyst_sentiment",
        "description": "Fetches analyst buy/hold/sell counts, consensus, business summary, and recent news.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker symbol, e.g., MANKIND.NS"}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "search_web",
        "description": "Searches the web for business model, revenue segments, promoter background, and recent news.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Specific search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_knowledge_base",
        "description": "Queries ChromaDB for relevant India PE context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "methodology_type": {"type": "string", "description": "Must be 'india_market_context'"}
            },
            "required": ["methodology_type"]
        }
    },
    {
        "name": "finalize_biz_intel",
        "description": "Called ONLY when agent has gathered sufficient info to output the final brief. Ends the agent loop.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "ticker": {"type": "string"},
                "sector": {"type": "string"},
                "subsector": {"type": "string"},
                "founded": {"type": "string"},
                "headquarters": {"type": "string"},
                "business_model": {"type": "string", "description": "2-3 sentences"},
                "revenue_segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "segment": {"type": "string"},
                            "pct_revenue": {"type": "string"}
                        }
                    }
                },
                "geographic_presence": {"type": "string"},
                "key_products_services": {"type": "array", "items": {"type": "string"}},
                "promoter_background": {"type": "string"},
                "promoter_holding_pct": {"type": "string"},
                "key_executives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"}
                        }
                    }
                },
                "market_cap_cr": {"type": "number"},
                "employee_count": {"type": "string"},
                "listing_status": {"type": "string"},
                "pe_investment_history": {"type": "string"},
                "recent_developments": {"type": "array", "items": {"type": "string"}},
                "analyst_consensus": {"type": "string"},
                "data_confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                "data_gaps": {"type": "array", "items": {"type": "string"}}
            },
            "required": [
                "company_name", "ticker", "sector", "subsector", "founded", "headquarters",
                "business_model", "revenue_segments", "geographic_presence", "key_products_services",
                "promoter_background", "promoter_holding_pct", "key_executives", "market_cap_cr",
                "employee_count", "listing_status", "pe_investment_history", "recent_developments",
                "analyst_consensus", "data_confidence", "data_gaps"
            ]
        }
    }
]

def search_web(query: str) -> dict:
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        return {"error": "TAVILY_API_KEY not set"}
    try:
        client = TavilyClient(api_key=tavily_key)
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
            include_domains=[
                "bseindia.com", "nseindia.com", "screener.in", "moneycontrol.com",
                "economictimes.indiatimes.com", "livemint.com", "business-standard.com",
                "thehindubusinessline.com", "vccircle.com"
            ]
        )
        return response
    except Exception as e:
        return {"error": str(e)}

def _execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "fetch_market_data":
        res = fetch_indian_market_data(tool_input["ticker"])
        return json.dumps(res) if res else "{}"
    elif tool_name == "fetch_analyst_sentiment":
        res = fetch_analyst_sentiment(tool_input["ticker"])
        return json.dumps(res) if res else "{}"
    elif tool_name == "search_web":
        res = search_web(tool_input["query"])
        return json.dumps(res)
    elif tool_name == "query_knowledge_base":
        res = get_methodology_context(tool_input["methodology_type"])
        return json.dumps({"context": res})
    elif tool_name == "finalize_biz_intel":
        return json.dumps(tool_input)
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

def run_biz_intel_agent(company_name: str, ticker: str = None, sector: str = None) -> dict:
    client = anthropic.Anthropic()
    
    user_message = f"Please build a business intelligence brief for:\nCompany: {company_name}\n"
    if ticker:
        user_message += f"Ticker: {ticker}\n"
    if sector:
        user_message += f"Sector: {sector}\n"
        
    messages = [{"role": "user", "content": user_message}]
    
    tools_called = 0
    max_iterations = 6
    
    for iteration in range(1, max_iterations + 1):
        # We don't print "Claude is thinking..." to keep log exactly as requested if needed, 
        # but the prompt said "Print iteration log same format as valuation agent:"
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    
                    print(f"[Iter {iteration}] Tool called: {tool_name}")
                    
                    if tool_name == "finalize_biz_intel":
                        if tools_called < 2:
                            # Force it to keep going
                            print(f"[Iter {iteration}] Agent tried to finalize too early. Instructing to call more tools.")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps({"error": "You must call at least 2 information gathering tools before finalizing."})
                            })
                            continue
                        
                        print(f"[Iter {iteration}] Tool complete. Result: {tool_input.get('company_name')} \u2713")
                        return tool_input

                    result_str = _execute_tool(tool_name, tool_input)
                    tools_called += 1
                    
                    # Try to give a concise success message based on what tool was called
                    status_text = f"Result length: {len(result_str)} chars \u2713"
                    if tool_name in ["fetch_market_data", "fetch_analyst_sentiment"]:
                        try:
                            res_json = json.loads(result_str)
                            if res_json:
                                status_text = "Found \u2713"
                            else:
                                status_text = "Not Found \u2717"
                        except:
                            pass
                            
                    print(f"[Iter {iteration}] Tool complete. Result: {status_text}")
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })
                    
            messages.append({"role": "assistant", "content": response.content})
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
                
        elif response.stop_reason == "end_turn":
            print(f"[Iter {iteration}] Claude ended without finalize_biz_intel.")
            return {"error": "Agent ended without finalize"}
            
    return {"error": f"Agent exceeded {max_iterations} iterations"}

if __name__ == "__main__":
    import json
    result = run_biz_intel_agent(
        company_name="Mankind Pharma Limited",
        ticker="MANKIND.NS",
        sector="Pharmaceuticals"
    )
    print(json.dumps(result, indent=2, 
                     ensure_ascii=False))
