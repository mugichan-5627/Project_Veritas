import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def build_dynamic_rag_query(company_data: dict) -> list:
    """
    Builds semantic queries from actual company profile.
    No hardcoded sector assumptions.
    """
    queries = []
    
    # Core: what methodology applies to THIS company
    revenue_growth = company_data.get('revenue_growth', 0)
    ebitda_margin = company_data.get('ebitda_margin', 0)
    sector = company_data.get('sector', '')
    ebitda = company_data.get('ebitda_m', company_data.get('ebitda', 0))
    is_profitable = ebitda > 0
    
    # Let the data describe the company — not us
    growth_descriptor = (
        "high growth hypergrowth" if revenue_growth > 0.4
        else "moderate growth" if revenue_growth > 0.1
        else "mature low growth"
    )
    
    margin_descriptor = (
        "high margin asset light" if ebitda_margin > 0.35
        else "average margin" if ebitda_margin > 0.15
        else "low margin capital intensive"
    )
    
    # Query 1: methodology for this company type
    queries.append(
        f"valuation methodology {growth_descriptor} "
        f"{margin_descriptor} {sector} company "
        f"fair multiple EV EBITDA revenue"
    )
    
    # Query 2: terminal value and WACC for this profile
    queries.append(
        f"WACC cost of capital {sector} "
        f"{'high growth' if revenue_growth > 0.2 else 'stable'} "
        f"company discount rate terminal value"
    )
    
    # Query 3: comparable company selection criteria
    queries.append(
        f"comparable company analysis peer selection "
        f"{sector} {growth_descriptor} "
        f"EV multiple benchmarking"
    )
    
    # Query 4: forensic red flags specific to this sector
    queries.append(
        f"forensic accounting quality of earnings "
        f"{sector} revenue recognition "
        f"cash flow manipulation"
    )
    
    return queries

def retrieve_knowledge(queries: list, chroma_client, embedding_fn) -> dict:
    """
    Retrieves relevant passages for each query.
    Returns structured dict with source citations.
    """
    all_chunks = []
    
    collections_to_query = ["valuation_methodology", "forensic_and_credit"]
    
    for query in queries:
        for coll_name in collections_to_query:
            try:
                collection = chroma_client.get_collection(coll_name)
                
                # Embed the query first to avoid dimension mismatch (1024 required)
                query_emb = embedding_fn([query])
                
                results = collection.query(
                    query_embeddings=query_emb,
                    n_results=2,
                    include=["documents", "metadatas", "distances"]
                )
            
                if results["documents"] and results["documents"][0]:
                    for i, doc in enumerate(results["documents"][0]):
                        dist = results["distances"][0][i] if results["distances"] else 0.5
                        relevance = 1 - dist
                        
                        chunk = {
                            "text": doc,
                            "source": results["metadatas"][0][i].get(
                                "source_file", "Unknown"
                            ) if results["metadatas"] else "Unknown",
                            "relevance": relevance,
                            "query_used": query
                        }
                        # Leniency: Include more chunks for debugging, threshold at 0.1
                        if chunk["relevance"] > 0.1:
                            all_chunks.append(chunk)
            except Exception as e:
                # Silently skip if collection doesn't exist
                continue
    
    # Deduplicate by text similarity
    seen_texts = set()
    unique_chunks = []
    for chunk in all_chunks:
        text_key = chunk["text"][:100]
        if text_key not in seen_texts:
            seen_texts.add(text_key)
            unique_chunks.append(chunk)
    
    print(f"RAG: Retrieved {len(unique_chunks)} unique chunks")
    for chunk in unique_chunks[:3]:
        print(f"  [{chunk['relevance']:.2f}] "
              f"{chunk['source']}: "
              f"{chunk['text'][:80]}...")
    
    return {
        "chunks": unique_chunks,
        "sources": list(set(
            c["source"] for c in unique_chunks
        )),
        "total_retrieved": len(unique_chunks)
    }
