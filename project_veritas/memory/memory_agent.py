import os
import chromadb

CHROMA_DB_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

def build_query(methodology_type: str, sector: str = None) -> str:
    """
    Constructs precise semantic search queries based on the requested methodology.
    """
    base_queries = {
        "comparable_company": "comparable company analysis peer selection EV EBITDA percentile quartile methodology trading multiples",
        "dcf_terminal_value": "terminal value NOPLAT RONIC growth perpetuity Value Driver Formula discount rate free cash flow",
        "lbo_returns": "LBO leveraged buyout IRR MOIC equity return debt paydown value creation bridge sources uses",
        "wacc_calculation": "WACC weighted average cost of capital beta equity risk premium cost of debt unlevering",
        "credit_analysis": "credit risk debt capacity interest coverage leverage ratio covenant ICRA rating methodology",
        "india_market_context": "India PE private equity deal market entry multiple regulatory environment sector outlook"
    }
    
    if methodology_type == "sector_specific" and sector:
        return f"{sector} valuation multiples India PE investment EBITDA margin growth rate benchmark sector"
    
    return base_queries.get(methodology_type, methodology_type)

def query_knowledge_base(query: str, collection_name: str, n_results: int = 3) -> list[dict]:
    """
    Semantic search across one ChromaDB collection.
    Returns top n_results chunks with metadata.
    """
    if not os.path.exists(CHROMA_DB_DIR):
        return []
        
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    
    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        # Collection might not exist yet
        return []
        
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    
    formatted_results = []
    
    # Chroma returns lists of lists because you can pass multiple query_texts
    if results['documents'] and len(results['documents']) > 0:
        docs = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0] if 'distances' in results and results['distances'] else [0]*len(docs)
        
        for i in range(len(docs)):
            source_file = metadatas[i].get("source_file", "Unknown")
            # Remove .pdf extension for cleaner citation
            if source_file.endswith(".pdf"):
                source_file = source_file[:-4]
                
            page = metadatas[i].get("page_estimate", "?")
            
            formatted_results.append({
                "content": docs[i],
                "source": metadatas[i].get("source_file", "Unknown"),
                "relevance_score": 1.0 - (distances[i] if distances[i] else 0), # Chroma uses L2 distance by default
                "citation": f"{source_file} — ~p.{page}"
            })
            
    return formatted_results

def get_methodology_context(methodology_type: str, sector: str = None, include_current_deal: bool = False) -> str:
    """
    Higher-level function called by valuation agent.
    Constructs the right query and returns formatted context string with citations.
    """
    query = build_query(methodology_type, sector)
    
    # Determine the primary collection based on methodology type
    if methodology_type == "credit_analysis":
        primary_collection = "forensic_and_credit"
    elif methodology_type == "india_market_context":
        primary_collection = "india_market_context"
    else:
        primary_collection = "valuation_methodology"
        
    results = query_knowledge_base(query, primary_collection)
    
    context_blocks = []
    
    for r in results:
        block = f"RETRIEVED CONTEXT ({r['citation']}):\n'{r['content']}'"
        context_blocks.append(block)
        
    if include_current_deal:
        deal_results = query_knowledge_base(query, "current_deal", n_results=2)
        for r in deal_results:
            # For deals, the source file is likely the annual report or presentation
            source_file = r['source']
            if source_file.endswith(".pdf"):
                source_file = source_file[:-4]
            block = f"DEAL CONTEXT ({source_file}, ~p.{r['citation'].split('~p.')[-1]}):\n'{r['content']}'"
            context_blocks.append(block)
            
    if not context_blocks:
        return "No relevant methodology context found in knowledge base."
        
    return "\n\n".join(context_blocks)
