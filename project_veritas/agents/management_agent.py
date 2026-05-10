import os
import sys
import json
import anthropic
from tavily import TavilyClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from memory.memory_agent import get_methodology_context

SYSTEM_PROMPT = """You are a governance and stewardship analyst for a top-tier private equity fund.
Your job is to relentlessly evaluate the integrity, execution capability, capital allocation track record, 
minority shareholder treatment, and succession planning of the target company's promoters and key executives.
You never rely on superficial metrics. You actively look for red flags: related-party transactions, 
regulatory breaches, frequent auditor changes, or aggressive executive compensation.
Your management_score directly influences the Investment Committee's willingness to partner with this team."""

TOOLS = [
    {
        "name": "search_web",
        "description": "Searches the web using Tavily for news, legal issues, or background information on promoters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_analyst_sentiment",
        "description": "Searches for analyst opinions, earnings call transcripts, or broker reports regarding management quality.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"}
            },
            "required": ["company"]
        }
    },
    {
        "name": "query_governance_knowledge",
        "description": "Queries ChromaDB for internal corporate governance methodology and red flag checklists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "E.g., 'corporate governance', 'related party transactions'"}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "finalize_management",
        "description": "Outputs the final management assessment report. Requires minimum 2 prior tools called.",
        "input_schema": {
            "type": "object",
            "properties": {
                "management_score": {"type": "integer", "description": "Score from 1-100"},
                "promoter_background": {"type": "string"},
                "key_executives": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "board_independence": {"type": "string", "enum": ["STRONG", "ADEQUATE", "WEAK"]},
                "governance_flags": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "analyst_sentiment": {"type": "string", "enum": ["POSITIVE", "NEUTRAL", "NEGATIVE"]},
                "succession_risk": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                "capital_allocation_track_record": {"type": "string"},
                "diligence_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific questions for management diligence sessions."
                },
                "data_gaps": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": [
                "management_score", "promoter_background", "board_independence",
                "governance_flags", "analyst_sentiment", "succession_risk",
                "diligence_questions", "data_gaps"
            ]
        }
    }
]

def _execute_tool(tool_name, tool_input):
    if tool_name == "search_web":
        tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
        try:
            res = tavily.search(query=tool_input["query"], search_depth="advanced")
            return json.dumps(res)
        except Exception as e:
            return f"Error searching web: {str(e)}"
            
    elif tool_name == "fetch_analyst_sentiment":
        tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
        query = f'{tool_input["company"]} management "analyst report" OR "earnings call transcript" OR "downgrade" OR "upgrade"'
        try:
            res = tavily.search(query=query, search_depth="advanced")
            return json.dumps(res)
        except Exception as e:
            return f"Error fetching sentiment: {str(e)}"
            
    elif tool_name == "query_governance_knowledge":
        res = get_methodology_context(tool_input["topic"])
        return res
        
    return f"Unknown tool: {tool_name}"

def run_management_agent(deal_context: dict, max_iterations=5) -> dict:
    company_name = deal_context.get("company_name", "")
    
    messages = [
        {"role": "user", "content": f"Assess the management and governance of {company_name}. You must call at least 2 tools before finalizing."}
    ]
    
    # Check if we should use bedrock or anthropic
    client = anthropic.Anthropic()
    
    tools_called = 0
    final_output = None
    
    for iteration in range(max_iterations):
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS,
            tool_choice={"type": "auto"}
        )
        
        messages.append({"role": "assistant", "content": response.content})
        
        if response.stop_reason == "tool_use":
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_id = block.id
                    
                    if tool_name == "finalize_management":
                        if tools_called < 2:
                            error_msg = "You must call at least 2 tools to gather evidence before finalizing."
                            messages.append({
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_id,
                                        "content": error_msg,
                                        "is_error": True
                                    }
                                ]
                            })
                            continue
                            
                        final_output = tool_input
                        break
                        
                    result = _execute_tool(tool_name, tool_input)
                    tools_called += 1
                    
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": str(result)
                            }
                        ]
                    })
                    
            if final_output:
                break
                
        else:
            messages.append({"role": "user", "content": "Please output structured JSON using the finalize_management tool."})
            
    if not final_output:
        final_output = {
            "management_score": 50,
            "promoter_background": "Failed to extract within iteration limit.",
            "board_independence": "WEAK",
            "governance_flags": ["TIMEOUT"],
            "analyst_sentiment": "NEUTRAL",
            "succession_risk": "HIGH",
            "capital_allocation_track_record": "Unknown",
            "diligence_questions": ["What is the management background?"],
            "data_gaps": ["Agent timeout"]
        }
        
    return final_output
