"""
FULL PIPELINE TEST — Project Veritas 7-Agent Due Diligence
Uses NVIDIA NIM API (OpenAI-compatible) for LLM calls.

This script:
  1. Queries ChromaDB (BGE-M3) to verify RAG works
  2. Mocks Agent 1-5 outputs with realistic NVIDIA Corp data
  3. Runs the Bull/Bear Debate (Agent 6A vs 6B) via NVIDIA API
  4. Runs the IC Decision (Agent 7) via NVIDIA API
  5. Saves IC decision to SQLite memory

Setup (run once in your terminal):
  $env:NVIDIA_API_KEY = "nvapi-YOUR-KEY-HERE"

Usage:
  py test_full_pipeline.py
"""

import os
import sys
import json
import re
import time
import yfinance as yf
import logging
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from datetime import datetime
from project_veritas.core.utils import compute_entry_strategy
from project_veritas.tools.peers import PeerDiscoveryEngine

PROJECT_ROOT = Path(r"C:\Users\Moosa\Downloads\Project_Veritas")
sys.path.insert(0, str(PROJECT_ROOT))

from project_veritas.agents.math_agent import run_math_agent
from project_veritas.agents.rag_agent import build_dynamic_rag_query, retrieve_knowledge
from project_veritas.core.llm_config import get_nvidia_model, get_nvidia_client, get_embedding_model, safe_llm_call

# =====================================================================
# GLOBAL STEP COUNTER
# =====================================================================
step_counter = 0
VERBOSE = "--verbose" in sys.argv

logging.basicConfig(
    level=logging.DEBUG if VERBOSE else logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stderr,
)

@contextmanager
def quiet_library_stdout():
    """Keep noisy helper diagnostics out of the demo report unless --verbose is set."""
    if VERBOSE:
        yield
    else:
        with redirect_stdout(sys.stderr):
            yield

def next_step(title: str):
    global step_counter
    step_counter += 1
    print("\n" + "="*60)
    print(f"  STEP {step_counter}: {title}")
    print("="*60)

# =====================================================================
# NVIDIA NIM LLM PROVIDER (OpenAI-compatible)
# =====================================================================

# LLM and Embedding Model configuration moved to project_veritas.core.llm_config

def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip(" \"'[]") for v in value if str(v).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.startswith("[") and cleaned.endswith("]"):
            try:
                return _as_list(json.loads(cleaned.replace("'", '"')))
            except Exception:
                pass
        return [part.strip(" -\t\"'") for part in cleaned.split("\n") if part.strip(" -\t\"'")]
    return [str(value)]

def _fmt_bullets(value, fallback="Refer to reasoning section above"):
    items = _as_list(value) or [fallback]
    return "\n".join(f"  - {item}" for item in items if item)

def _fmt_price(value):
    return "N/A" if value is None else f"${value:,.2f}"

def _fmt_pct(value):
    return "N/A" if value is None else f"{value:.1f}%"

def _fmt_m(value):
    if value is None:
        return "N/A"
    return f"${value/1000:,.1f}B" if abs(value) >= 1000 else f"${value:,.0f}M"

def build_canonical_verdict(deal_context, ic_decision, debate_result):
    fin = deal_context.get("financial_data", {})
    val = deal_context.get("valuation", {})
    shares = fin.get("shares_outstanding_M") or 0
    current_price = fin.get("current_price") or 0
    fair_equity_m = val.get("fair_equity_value_m") or val.get("scenarios", {}).get("base") or 0
    fair_price = fair_equity_m / shares if shares else None
    implied_return = ((fair_price - current_price) / current_price * 100) if fair_price and current_price else 0
    forensic = deal_context.get("forensics", {}).get("forensic_score", 0)
    management = deal_context.get("management", {}).get("management_score", 0)

    bull = debate_result.get("champion_final_conviction", 5)
    bear = debate_result.get("risk_partner_final_conviction", 5)
    debate_winner = "DEAL_CHAMPION" if bull > bear else ("RISK_PARTNER" if bear > bull else "DRAW")
    conviction = "HIGH" if abs(bull - bear) >= 3 else ("MEDIUM" if abs(bull - bear) >= 1 else "LOW")

    reasoning = _as_list(ic_decision.get("reasoning"))
    if not reasoning:
        reasoning = [
            f"Model fair value is {_fmt_price(fair_price)} versus current price {_fmt_price(current_price)}, implying {_fmt_pct(implied_return)} upside/downside.",
            f"Forensic score is {forensic}/100 and management score is {management}/100.",
            f"Debate winner: {debate_winner} ({bull}/10 champion vs {bear}/10 risk partner).",
        ]

    llm_decision = (ic_decision.get("decision") or ic_decision.get("verdict") or "").upper().strip()
    decision = llm_decision if llm_decision in {"APPROVE", "HOLD", "REJECT"} else "REJECT"

    # Consistency check (Fix requested)
    champion_score = bull
    risk_score = bear
    forensic_total = forensic
    
    # Rule: Can't REJECT if champion >8 AND forensic >75 
    # unless valuation premium is extreme (>50% above fair)
    if decision == "REJECT":
        if current_price and fair_price and fair_price > 0:
            premium = (current_price - fair_price) / fair_price
            if champion_score >= 8 and forensic_total >= 75:
                if premium < 0.50:
                    decision = "HOLD"
                    reasoning.append(
                        "Verdict upgraded from REJECT to HOLD: "
                        "Strong champion conviction and healthy "
                        "forensic score do not support rejection "
                        "at current valuation premium."
                    )

    # Rule: Can't APPROVE if forensic <60
    if decision == "APPROVE" and forensic_total < 60:
        decision = "HOLD"
        reasoning.append(
            "Verdict downgraded from APPROVE to HOLD: "
            "Forensic score below 60 indicates earnings "
            "quality concerns that prevent full approval."
        )

    # Rule: Can't APPROVE if valuation premium >40%
    if decision == "APPROVE" and current_price and fair_price and fair_price > 0:
        if current_price > fair_price * 1.40:
            decision = "HOLD"
            reasoning.append(
                "Verdict downgraded from APPROVE to HOLD: "
                "Current price exceeds fair value by >40%."
            )

    if decision.startswith("APPROVE"):
        max_entry_price = fair_price
        price_label = "Max Entry Price"
    elif decision == "HOLD":
        max_entry_price = fair_price * 0.90 if fair_price else None
        price_label = "Recommended Entry"
    else:
        max_entry_price = fair_price * 0.75 if fair_price else None
        price_label = "Re-evaluation Threshold"

    conditions = _as_list(ic_decision.get("conditions") or ic_decision.get("key_conditions"))
    if not conditions:
        conditions = ["Monitor valuation versus fair value", "Refresh public-source financials before IC presentation"]

    risk_points = []
    for entry in debate_result.get("debate_transcript", []):
        if entry.get("role") == "RISK_PARTNER":
            risk_points.extend(_as_list(entry.get("evidence_cited")))
            if entry.get("argument"):
                risk_points.append(entry["argument"])
    if not risk_points:
        risk_points = deal_context.get("valuation", {}).get("key_risks", []) or ["Refer to reasoning section above"]

    return {
        "decision": decision,
        "conviction": conviction,
        "debate_winner": debate_winner,
        "reasoning": reasoning,
        "conditions": conditions,
        "risks": risk_points[:4],
        "fair_price": fair_price,
        "current_price": current_price,
        "implied_return_pct": implied_return,
        "max_entry_price": max_entry_price,
        "price_label": price_label,
        "strategic_outlook": ic_decision.get("strategic_outlook", {})
    }

def _valid_memo_bullet(text, min_len=30):
    text = str(text).strip()
    return len(text) >= min_len and not text.startswith("$") and not text.replace(",", "").replace(".", "").isdigit()

def _memo_bullets(items, fallbacks, min_len=30):
    cleaned = [str(item).strip() for item in _as_list(items) if _valid_memo_bullet(item, min_len)]
    for item in fallbacks:
        if len(cleaned) >= 3:
            break
        if _valid_memo_bullet(item, min_len):
            cleaned.append(item)
    return cleaned[:3]

# =====================================================================
# GLOBAL CACHE for RAG & Models
# =====================================================================
# Embedding model cache handled by project_veritas.core.llm_config

# =====================================================================
# STEP 1: Test ChromaDB RAG retrieval
# =====================================================================

def test_chromadb_rag(ticker: str = "NVDA", sector: str = "Technology", company_data: dict = None):
    """
    FIX: Dynamic RAG Queries. 
    Queries ChromaDB based on specific company context and sector pitfalls.
    """
    next_step("Dynamic ChromaDB RAG Retrieval")

    rag_obj = get_embedding_model()
    client = rag_obj.client

    if not company_data:
        # Fallback for simple testing
        company_data = {
            "ticker": ticker,
            "sector": sector,
            "revenue_growth": 0.2,
            "ebitda_margin": 0.25,
            "ebitda": 1000
        }

    queries = build_dynamic_rag_query(company_data)
    rag_data = retrieve_knowledge(queries, client, rag_obj.embedding_function)
    
    print("  RAG STATUS: OK")
    return rag_data


# =====================================================================
# STEP 2: RAG-Driven Math Agent
# =====================================================================

# Local definition removed, now imported from project_veritas.agents.math_agent

# =====================================================================
# STEP 2.5: Intel Agent (Tavily Parse)
# =====================================================================

def run_intel_agent(ticker: str, company_name: str, industry: str, search_results: str):
    """Parses raw Tavily search snippets into structured TAM/Moat logic."""
    prompt = f"""You are a Strategic Market Analyst specializing in the {industry} sector.
Based on these search results for {company_name} ({ticker}), extract the TAM, SAM, and SOM (in USD Billions) and summarize the Competitive Moat.
CRITICAL: Do NOT provide generic theory. Identify the SPECIFIC advantages of {company_name} (e.g., proprietary tech, regulatory capture, switching costs) in the {industry} market.
IF exact TAM/SAM/SOM numbers are from ancient history, ignore them and provide a RECENT 2024/2025 estimate.

SEARCH RESULTS:
{search_results}

Strictly output a JSON object:
{{"tam_sam_som": "TAM: $XB | SAM: $XB | SOM: $XB", "competitive_moat": "2-3 sentence summary", "forensic_red_flags": ["List any issues"], "management_intel": {{"score": int, "decomposition": {{"vision": int, "execution": int, "governance": int}}, "board": "Independence rating", "flags": ["List any issues"]}}}}
"""
    # safe_llm_call handles retries and rate limits internally
    response = safe_llm_call(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    
    if response:
        try:
            import re
            match = re.search(r'\{.*\}', response.choices[0].message.content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                m_intel = parsed.get("management_intel", {})
                if m_intel.get("score", 0) <= 10 and m_intel.get("score", 0) > 0:
                    m_intel["score"] *= 10
                    decomp = m_intel.get("decomposition", {})
                    for k in decomp: decomp[k] *= 10
                return parsed
        except Exception as e:
            print(f"    [!] Intel Agent parse failure: {e}")
            
    return None
    return None

# =====================================================================
# STEP 3: Pull LIVE data from yfinance (no mocks)
# =====================================================================

def build_deal_context_live(ticker: str, framing: str = "PUBLIC", progress_callback=None):
    """
    Pulls REAL financial data using a Hybrid Architecture:
    Primary: yfinance (quarterly sum)
    Secondary: EDGAR (for future hardening)
    Peers: CapIQ -> yfinance fallback
    Framing: 'PUBLIC' (Multiple-based) or 'LBO' (IRR-based)
    """
    import sys
    import os
    from datetime import datetime
    import json
    from project_veritas.tools.financials import get_financials_summary, get_sector_tier

    def next_step(msg):
        print(f"    [PROGRESS] {msg}...")
        if progress_callback:
            import time
            progress_callback("DATA_PROCESS", msg)
            time.sleep(0.4) # UX: Allow UI to breathe

    # Initial Signal (Fix requested: Animation Speed)
    if progress_callback:
        import time
        progress_callback("RAG_RETRIEVAL", "Initializing Knowledge Retrieval Engine...")
        time.sleep(0.6)

    from project_veritas.tools.peers import PeerDiscoveryEngine
    from project_veritas.core.validation import validate_financials
    from datetime import datetime

    # Tavily for enrichment (Fix 6)
    tv_key = os.environ.get("TAVILY_API_KEY")
    if tv_key:
        try:
            from tavily import TavilyClient
            tavily = TavilyClient(api_key=tv_key)
        except Exception as e:
            print(f"    [!] Failed to init Tavily: {e}")
            tavily = None
    else:
        tavily = None

    next_step("Pulling LIVE Data (yfinance + CapIQ)")

    # 1. Fetch Financials
    with quiet_library_stdout():
        fin_data = get_financials_summary(ticker)
    if not fin_data.get("revenue_ttm_M"):
        print("    [ERROR] Could not fetch fundamental data.")
        return {}

    # Sector Routing Layer (Failure 1 Fix)
    is_fin = fin_data.get("is_financial", False)
    industry = fin_data.get("industry", "Technology")
    sector = fin_data.get("sector", "Technology")
    company_name = fin_data.get("long_name", ticker)
    
    # Standardize Variables (Fix 2)
    revenue_m = fin_data.get("revenue_ttm_M") or 0
    ebitda_m = fin_data.get("ebitda_reported_M") or 0
    sbc_haircut_m = fin_data.get("sbc_M") or 0
    adjusted_ebitda_m = fin_data.get("ebitda_adj_M") or 0
    fcf_m = fin_data.get("fcf_M") or 0
    fcf_margin = fin_data.get("fcf_margin_pct") or 0
    current_market_ev = fin_data.get("enterprise_value_M") or 0

    # Run Validation
    val_report = validate_financials(fin_data)
    if VERBOSE:
        val_report.print_summary()
    
    # Store quality flags for UI (Fix requested)
    quality_flags = val_report.get_quality_flags()

    # 2. Initialize Peer Engine & Discover with Session Caching (Fix 9)
    peer_engine = PeerDiscoveryEngine(
        capiq_directory=str(PROJECT_ROOT / "data"),
        tavily_client=tavily,
        llm_client=get_nvidia_client()
    )
    
    # Static session cache to prevent redundant peer discovery
    if not hasattr(PeerDiscoveryEngine, '_static_peer_cache'):
        PeerDiscoveryEngine._static_peer_cache = {}
    
    if ticker not in PeerDiscoveryEngine._static_peer_cache:
        with quiet_library_stdout():
            PeerDiscoveryEngine._static_peer_cache[ticker] = peer_engine.discover_peers(ticker)
    
    peer_result = PeerDiscoveryEngine._static_peer_cache[ticker]
    peers = peer_result["peers"]

    # 3. Independent Fair Value Derivation (Fix 3)
    premium_data = PeerDiscoveryEngine.calculate_premium_discount(fin_data, peers)
    base_multiple = premium_data.get("implied_fair_multiple", 15.0)
    fair_value_ev = adjusted_ebitda_m * base_multiple
    
    # 4. Forensic Score Recalibration (Fix 4 / Problem 4)
    # Start with quantitative score from financials.py logic
    forensic_data = fin_data.get("forensic_details", {})
    forensic_score = fin_data.get("forensic_score", 75)
    
    # Red Flag Penalty: Deduct for qualitative issues found by Intel Agent
    intel_red_flags = [] 
    
    # Triggering RAG Math Agent (Moved up for rationale)
    raw_fin = {
        "ticker": ticker,
        "company_name": company_name,
        "is_financial": is_fin,
        "market_cap_m": fin_data.get("market_cap_M"),
        "total_debt_m": fin_data.get("total_debt_M") if is_fin else fin_data.get("net_debt_M", 0),
        "total_liabilities_m": fin_data.get("total_liabilities_M"),
        "debt_data_gap": fin_data.get("debt_data_gap", False),
        "total_cash_m": 0,
        "ebitda_m": ebitda_m if not is_fin else 0,
        "revenue": revenue_m * 1e6, # Pass raw for conversion logic in agent
        "ebitda_margin": (ebitda_m / revenue_m) if revenue_m > 0 else 0,
        "net_income_m": fin_data.get("net_income_M", 0),
        "sbc_expense_m": sbc_haircut_m,
        "book_value_m": (fin_data.get("book_value_ps", 0) * fin_data.get("shares_outstanding_M", 0)) if is_fin else 0,
        "roe_pct": fin_data.get("roe_pct", 0),
        "price_to_book": fin_data.get("price_to_book"),
        "current_price": fin_data.get("current_price", 0),
        "beta": fin_data.get("cost_of_equity_components", {}).get("beta_used", fin_data.get("beta", 1.15)),
        "cost_of_equity_pct": fin_data.get("cost_of_equity_pct")
    }
    # Dynamic RAG Retrieval before Math Agent
    if progress_callback: 
        import time
        progress_callback("RAG_RETRIEVAL", "Building Dynamic RAG Queries...")
        time.sleep(0.5)
    rag_data = test_chromadb_rag(ticker, sector, company_data=raw_fin)
    rag_chunks = rag_data.get("chunks", [])
    if not rag_chunks:
        quality_flags.append("No RAG context available for valuation math")

    if progress_callback: 
        import time
        progress_callback("MATH_AGENT", "Running Math Agent (Valuation & Multiples)...")
        time.sleep(0.5)
    next_step("Triggering RAG Math Agent")
    # Pass sector and rag_chunks for guardrails and knowledge-driven valuation
    raw_fin["sector"] = sector
    raw_fin["company_name"] = company_name
    math_res = run_math_agent(ticker, industry, raw_fin, peers=peers, nvidia_client=get_nvidia_client(), embedding_model=get_embedding_model(), rag_chunks=rag_chunks)
    if math_res:
        rationale_parts = []
        if math_res.get("why_this_methodology"):
            rationale_parts.append(f"**Methodology:** {math_res['why_this_methodology']}")
        if math_res.get("reasoning"):
            rationale_parts.append(f"**Reasoning:** {math_res['reasoning']}")
        if math_res.get("methodology_source"):
            rationale_parts.append(f"**Source:** *{math_res['methodology_source']}*")
        
        math_rationale = "\n\n".join(rationale_parts) if rationale_parts else math_res.get("rationale", "Standard institutional calculation.")
    else:
        math_rationale = "Valuation derived from sector-standard multiples and peer benchmarking."
    f_commentary = math_res.get("forensic_commentary", {}) if math_res else {}
    wacc_pct_val = fin_data.get("cost_of_equity_pct") if is_fin else (math_res.get("wacc_pct", 9.5) if math_res else 9.5)
    try:
        wacc_pct = float(wacc_pct_val)
    except:
        wacc_pct = 9.5
    wacc_pct = max(5.0, min(18.0, wacc_pct))
    
    # Fair Value Logic (Failure 4 Fix)
    pe_cross_check = {}
    if is_fin:
        book_equity_m = (fin_data.get("book_value_ps", 0) or 0) * (fin_data.get("shares_outstanding_M", 0) or 0)
        roe = (fin_data.get("roe_pct", 0) or 0) / 100
        coe = (wacc_pct or 9.5) / 100
        sustainable_g = 0.045
        if coe > sustainable_g and roe > sustainable_g:
            base_multiple = (roe - sustainable_g) / (coe - sustainable_g)
        elif math_res and math_res.get("fair_p_book_multiple"):
            base_multiple = float(math_res["fair_p_book_multiple"])
        else:
            base_multiple = fin_data.get("price_to_book") or 1.0
        base_multiple = max(0.5, min(base_multiple, 6.5))
        pb_equity_m = base_multiple * book_equity_m

        primary_peers = [p for p in peers if p.get("peer_type", "PRIMARY") == "PRIMARY"]
        peer_pes = sorted([
            p.get("raw_pe") for p in primary_peers
            if p.get("raw_pe") and 0 < p.get("raw_pe") < 40
        ])
        peer_median_pe = peer_pes[len(peer_pes)//2] if peer_pes else (fin_data.get("pe_ratio") or 14.0)
        peer_roes = [p.get("raw_roe") for p in primary_peers if p.get("raw_roe")]
        peer_median_roe = sorted(peer_roes)[len(peer_roes)//2] if peer_roes else (fin_data.get("roe_pct") or 10.0)
        target_growth = fin_data.get("revenue_growth_pct") or 0
        peer_growth = max(abs(peer_median_roe), 1.0)
        growth_adjustment = 1 + ((target_growth - peer_growth) / peer_growth * 0.25)
        franchise_floor = 16.0 if (fin_data.get("roe_pct") or 0) >= 30 else (13.0 if (fin_data.get("roe_pct") or 0) >= 20 else 8.0)
        fair_pe = max(franchise_floor, min(peer_median_pe * growth_adjustment, 28.0))
        pe_equity_m = fair_pe * (fin_data.get("net_income_M") or 0)
        fair_value_m = (0.5 * pb_equity_m + 0.5 * pe_equity_m) if pe_equity_m > 0 else pb_equity_m
        if pb_equity_m > 0:
            diff = abs(pb_equity_m - (base_multiple * book_equity_m)) / pb_equity_m
            assert diff < 0.05, "P/Book base equity does not reconcile to fair multiple x book equity"
        pe_cross_check = {
            "pbook_equity_m": pb_equity_m,
            "pe_equity_m": pe_equity_m,
            "blended_equity_m": fair_value_m,
            "fair_p_book": base_multiple,
            "fair_pe": fair_pe,
            "peer_median_pe": peer_median_pe,
            "book_equity_m": book_equity_m,
        }
    if is_fin:
        # Financial logic already handled above
        pass
    elif math_res and math_res.get("fair_equity_value_m"):
        try:
            fair_value_m = float(math_res["fair_equity_value_m"])
        except:
            fair_value_m = (adjusted_ebitda_m * base_multiple) - (fin_data.get("net_debt_M", 0) or 0)
    else:
        # Standard Industrial: EV - Net Debt
        fair_value_m = (adjusted_ebitda_m * base_multiple) - (fin_data.get("net_debt_M", 0) or 0)

    # Sanity Check: Ensure fair value is within 60% of market price (Fix requested)
    current_mkt_cap = fin_data.get("market_cap_M", 0)
    if current_mkt_cap > 0:
        lower_bound = current_mkt_cap * 0.4
        upper_bound = current_mkt_cap * 1.6
        if fair_value_m < lower_bound:
            print(f"    [!] WARNING: Fair value ${fair_value_m:,.0f}M is >60% below market ${current_mkt_cap:,.0f}M. Clamping to lower bound.")
            fair_value_m = lower_bound
        elif fair_value_m > upper_bound:
            print(f"    [!] WARNING: Fair value ${fair_value_m:,.0f}M is >60% above market ${current_mkt_cap:,.0f}M. Clamping to upper bound.")
            fair_value_m = upper_bound

    if math_res:
        rationale_parts = []
        # Construct PE Bridge (Fix requested: Real Math)
        if not is_fin:
            rationale_parts.append("### PE Valuation Bridge")
            rationale_parts.append(f"- **TTM Adj. EBITDA:** ${adjusted_ebitda_m:,.1f}M")
            rationale_parts.append(f"- **Fair Multiple:** {base_multiple:.1f}x")
            rationale_parts.append(f"- **Implied Enterprise Value:** ${(adjusted_ebitda_m * base_multiple):,.1f}M")
            rationale_parts.append(f"- **Net Debt:** ${fin_data.get('net_debt_M', 0):,.1f}M")
            rationale_parts.append(f"- **Implied Equity Value:** ${fair_value_m:,.1f}M")
            rationale_parts.append("---")
        
        if math_res.get("why_this_methodology"):
            rationale_parts.append(f"**Methodology:** {math_res['why_this_methodology']}")
        if math_res.get("reasoning"):
            rationale_parts.append(f"**Reasoning:** {math_res['reasoning']}")
        if math_res.get("methodology_source"):
            rationale_parts.append(f"**Source:** *{math_res['methodology_source']}*")
        
        math_rationale = "\n\n".join(rationale_parts) if rationale_parts else math_res.get("rationale", "Standard institutional calculation.")
    else:
        math_rationale = "Valuation derived from sector-standard multiples and peer benchmarking."


    # Business Intel Enrichment (Fix 6/9)
    competitive_moat = "N/A"
    tam_sam_som = "N/A"
    if tavily:
        try:
            print(f"    [TAVILY] Enriching {company_name} business intel...")
            combined_search = ""
            # Failure 2/6 FIX: Search by long name, add disambiguation
            search_name = company_name if len(company_name) > 3 else f"{company_name} company"
            queries = [
                f"{search_name} competitive moat and business model 2025", 
                f"{search_name} TAM SAM SOM and market share 2025", 
                f"{search_name} management quality CEO track record governance flags",
                f"{search_name} investigation fines regulatory news 2024"
            ]
            if is_fin:
                queries.append(f"{search_name} CET1 ratio efficiency ratio wealth management mix")
            if progress_callback: 
                import time
                progress_callback("INTEL_AGENT", "Running Business Intel Agent (TAM/Moat/Governance)...")
                time.sleep(0.5)
            for q in queries:
                res = tavily.search(q, search_depth="basic")
                for r in res.get('results', []): combined_search += f"\n- {r['content']}"
            intel_res = run_intel_agent(ticker, company_name, industry, combined_search)
            if intel_res:
                competitive_moat = intel_res.get("competitive_moat", "N/A")
                tam_sam_som = intel_res.get("tam_sam_som", "N/A")
                intel_red_flags = intel_res.get("forensic_red_flags", [])
                management_intel = intel_res.get("management_intel", {})
        except Exception as e:
            print(f"    [!] Tavily failed: {e}")

    # 5. CapIQ Precedent Transactions (Fix 10 & 20)
    txns = []
    try:
        from project_veritas.tools.capiq_parser import CapIQParser
        capiq_parser = CapIQParser(data_dir=str(PROJECT_ROOT / "data"))
        
        # Sector Mapping Logic (Fix 20)
        sector_map = {
            "Technology": "information technology",
            "Communication Services": "communication services",
            "Consumer Cyclical": "consumer discretionary",
            "Financial Services": "financials",
            "Credit Services": "financials",
            "Banks—Diversified": "financials",
            "Banks—Regional": "financials",
            "Healthcare": "health care",
            "Industrials": "industrials",
            "Consumer Defensive": "consumer staples"
        }
        lookup_sector = sector_map.get(industry) or sector_map.get(sector, sector.lower())
        txns = capiq_parser.get_precedent_transactions(lookup_sector, limit=5)
    except Exception as e:
        print(f"    [!] Precedent Transaction fetch failed: {e}")

    # 6. Sensitivity Table Generation (Fix 7)
    sensitivity = []
    if is_fin:
        # Bank Sensitivity: P/Book vs ROE (Fix 7 + Problem 2)
        target_pb = pe_cross_check.get("fair_p_book") or (math_res.get("fair_p_book_multiple") if math_res else fin_data.get("price_to_book", 1.0))
        # Total Book Equity must match base case
        book_equity = pe_cross_check.get("book_equity_m") or (fin_data.get("book_value_ps", 0) * fin_data.get("shares_outstanding_M", 0))
        
        for pb_adj in [-0.5, -0.25, 0, 0.25, 0.5]:
            row = []
            curr_pb = (target_pb or 1.0) + pb_adj
            for roe_mult in [0.8, 1.0, 1.2]:
                val = (curr_pb * book_equity) * roe_mult
                row.append(val)
            sensitivity.append({"multiple": round(curr_pb, 2), "values": row})
        center = sensitivity[2]["values"][1] if len(sensitivity) >= 3 else 0
        expected = (target_pb or 1.0) * book_equity
        if expected > 0:
            assert abs(center - expected) / expected < 0.01, "Sensitivity center does not reconcile to P/Book base case"
    elif adjusted_ebitda_m > 0 and base_multiple > 0:
        for mult_adj in [-2, -1, 0, 1, 2]:
            row = []
            for ebitda_pct in [0.9, 1.0, 1.1]:
                val = (adjusted_ebitda_m * ebitda_pct) * (base_multiple + mult_adj)
                row.append(val)
            sensitivity.append({"multiple": base_multiple + mult_adj, "values": row})

    # Problem 4: Apply penalties to Forensic Score if intel flags exist (Moved here)
    if intel_red_flags:
        penalty = min(25, len(intel_red_flags) * 5)
        forensic_score = max(40, forensic_score - penalty)

    # Extra variables needed for the dict
    company_name = fin_data.get("long_name", ticker)
    framing = f"{industry} Buyout Candidate"
    trading_mult = fin_data.get("ev_ebitda", 0)
    sbc_rev_pct = (sbc_haircut_m / revenue_m * 100) if revenue_m > 0 else 0

    deal_context = {
        "company_name": company_name,
        "ticker": ticker,
        "framing": framing,
        "lbo_irr_est": _calculate_simple_irr(adjusted_ebitda_m, current_market_ev),
        "sector": sector,
        "industry": industry,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "forensics": {
            "forensic_score": forensic_score,
            "forensic_decomposition": fin_data.get("forensic_decomposition", {}),
            "forensic_commentary": f_commentary,
            "quality_of_earnings": fin_data.get("quality_of_earnings", "MODERATE"),
            "reported_ebitda_usd_m": ebitda_m,
            "adjusted_ebitda_usd_m": adjusted_ebitda_m,
            "ebitda_adjustment_pct": round((adjusted_ebitda_m - ebitda_m) / ebitda_m * 100, 1) if ebitda_m > 0 else 0,
            "math_agent_rationale": math_rationale,
            "red_flags": intel_red_flags,
            "net_cash_debt_usd_m": fin_data.get("net_debt_M", 0),
            "sbc_rev_pct": sbc_rev_pct,
            "fcf_margin": fcf_margin
        },
        "market_intel": {
            "tier": get_sector_tier(fin_data),
            "competitive_moat": competitive_moat,
            "tam_sam_som": tam_sam_som,
            "current_trading_multiple": trading_mult,
            "current_ev_rev": fin_data.get("ev_rev", 0),
            "peer_comps": peers,
            "precedent_transactions": txns,
            "independent_fair_multiple": base_multiple,
            "sensitivity_matrix": sensitivity,
            "revenue_ttm_m": revenue_m,
            "revenue_growth_pct": fin_data.get("revenue_growth_pct", 0),
            "is_financial": fin_data.get("is_financial", False),
            "net_income_m": fin_data.get("net_income_M", 0),
            "roe_pct": fin_data.get("roe_pct", 0),
            "efficiency_ratio": fin_data.get("efficiency_ratio", 0),
            "book_value_ps": fin_data.get("book_value_ps", 0),
            "div_yield_pct": fin_data.get("div_yield_pct", 0),
            "pe_ratio": fin_data.get("pe_ratio", 0),
            "price_to_book": fin_data.get("price_to_book", 0)
        },
        "management": {
            "management_score": management_intel.get("score", 70) if 'management_intel' in locals() else 70,
            "management_decomposition": management_intel.get("decomposition", {"vision": 70, "execution": 70, "governance": 70}) if 'management_intel' in locals() else {"vision": 70, "execution": 70, "governance": 70},
            "board_independence": management_intel.get("board", "MODERATE") if 'management_intel' in locals() else "MODERATE",
            "promoter_background": "Standard Institutional Management",
            "governance_flags": management_intel.get("flags", []) if 'management_intel' in locals() else []
        },
        "valuation": {
            "pe_decision": "PROCEED" if fin_data.get("forensic_score", 75) > 50 else "DO NOT INVEST",
            "do_not_exceed_ev_usd_m": fair_value_m + (fin_data.get("net_debt_M", 0) if not is_fin else 0),
            "fair_equity_value_m": fair_value_m,
            "valuation_cross_check": pe_cross_check,
            "scenarios": {
                "bear": fair_value_m * 0.8,
                "base": fair_value_m,
                "bull": fair_value_m * 1.2
            },
            "wacc_pct": wacc_pct,
            "key_risks": intel_red_flags + [f"Valuation Premium: {premium_data.get('premium_pct', 0)}%"]
        },
        "financial_data": fin_data,
        "data_quality_flags": quality_flags,
        "rag": rag_data if 'rag_data' in locals() else {}
    }

    print(f"\n  Final Deal Context Built for {ticker}")
    mult_label = "P/Book" if is_fin else "EV/EBITDA"
    print(f"    - Fair {mult_label} Multiple: {base_multiple:.1f}x")
    print(f"    - Forensic Score: {forensic_score}/100")
    print(f"    - Precedents Found: {len(txns)}")
    
    return validate_deal_context(deal_context)

def validate_deal_context(ctx):
    """Audits the context for data integrity and common agent hallucinations."""
    print("    [GUARDRAIL] Auditing deal context integrity...")
    ticker = ctx.get('ticker', 'N/A')
    val = ctx.get('valuation', {})
    fin = ctx.get('financial_data', {})
    
    # 1. Price check
    if val.get('fair_price', 0) <= 0:
        print(f"      [!] ALERT: Zero fair price detected for {ticker}. Forcing fallback.")
        val['fair_price'] = fin.get('current_price', 1.0)
        
    # 2. Multiple sanity
    if val.get('fair_multiple', 0) > 100:
         print(f"      [!] ALERT: Extreme multiple ({val['fair_multiple']}) detected. Capping at 50x.")
         val['fair_multiple'] = 50.0
         
    # 3. ROE check for financials
    if ctx.get('is_financial'):
        roe = fin.get('roe', 0)
        if roe <= 0:
            print(f"      [!] ALERT: Missing ROE for financial institution. Using sector median 12%.")
            fin['roe'] = 0.12
            
    return ctx

def _calculate_simple_irr(ebitda, entry_ev, exit_year=5, leverage=3.0, exit_mult=None):
    """Simple 5-year IRR approximation for LBO framing."""
    if ebitda <= 0 or entry_ev <= 0: return 0
    if not exit_mult: exit_mult = entry_ev / ebitda
    
    # Assume 40% equity on entry
    entry_equity = entry_ev * 0.4
    # Assume 3% organic EBITDA growth
    exit_ebitda = ebitda * (1.15) # 15% cumulative growth over 5 years
    exit_ev = exit_ebitda * exit_mult
    # Assume 20% debt paydown
    exit_equity = exit_ev - (entry_ev * 0.6 * 0.8) 
    
    irr = ((exit_equity / entry_equity) ** (1/exit_year) - 1) * 100
    return round(irr, 1)

def run_nvidia_debate(deal_context, rag_context):
    """Runs the Bull/Bear debate using NVIDIA NIM API."""
    next_step("Multi-Agent Investment Committee Debate")
    print(f"  LLM: NVIDIA NIM ({get_nvidia_model()})")

    client = get_nvidia_client()
    if not client:
        return {
            "debate_transcript": [],
            "total_rounds": 0,
            "champion_final_conviction": 5,
            "risk_partner_final_conviction": 5,
            "consensus_reached": False,
            "consensus_type": "BYPASSED",
            "debate_status": "BYPASSED"
        }
    is_fin = deal_context.get('financial_data', {}).get('is_financial', False)
    forensics = deal_context.get("forensics", {})
    val = deal_context.get("valuation", {})
    market = deal_context.get("market_intel", {})
    mgmt = deal_context.get("management", {})

    if is_fin:
        fin = deal_context.get('financial_data', {})
        deal_brief = f"""
ALL MONETARY VALUES ARE IN USD MILLIONS (USD M).
THIS IS A FINANCIAL INSTITUTION (BANK). 
DO NOT REFERENCE EBITDA, EV, FCF, OR NET DEBT.

COMPANY: {deal_context.get('company_name', 'Unknown')} ({deal_context.get('ticker', 'N/A')})
SECTOR: {deal_context.get('sector', 'Unknown')} (Bank Mode)

FINANCIALS:
  ROE: {fin.get('roe_pct', 0)}%
  Efficiency Ratio: {fin.get('efficiency_ratio', 'N/A')}%
  P/Book (Current): {fin.get('price_to_book', 'N/A')}x
  P/E (Current): {fin.get('pe_ratio', 'N/A')}x
  Book Value per Share: ${fin.get('book_value_ps', 0)}

FORENSICS:
  Score: {forensics.get('forensic_score', 'N/A')}/100
  Red Flags: {json.dumps(forensics.get('red_flags', []))}
  Green Flags: {json.dumps(forensics.get('green_flags', []))}

MARKET:
  Position: {market.get('competitive_position', 'N/A')}
  Peer Median P/Book: {market.get('peer_median_pb', 'N/A')}x
  Competitors: {json.dumps(market.get('key_competitors', []))}

MANAGEMENT:
  Score: {mgmt.get('management_score', 'N/A')}/100
  Board: {mgmt.get('board_independence', 'N/A')}
  Governance Flags: {json.dumps(mgmt.get('governance_flags', []))}

VALUATION:
  Base Case Equity Value: ${val.get('scenarios', {}).get('base', 0):,}M
  Cost of Equity: {val.get('wacc_pct', 0)}%
  Key Risks: {json.dumps(val.get('key_risks', []))}
"""
    else:
        deal_brief = f"""
ALL MONETARY VALUES ARE IN USD MILLIONS (USD M).

COMPANY: {deal_context.get('company_name', 'Unknown')} ({deal_context.get('ticker', 'N/A')})
SECTOR: {deal_context.get('sector', 'Unknown')}

FORENSICS:
  Score: {forensics.get('forensic_score', 'N/A')}/100 | QoE: {forensics.get('quality_of_earnings', 'N/A')}
  Reported EBITDA: ${forensics.get('reported_ebitda_usd_m', 0):,}M
  Adjusted EBITDA: ${forensics.get('adjusted_ebitda_usd_m', 0):,}M (adj: {forensics.get('ebitda_adjustment_pct', 0)}%)
  Red Flags: {json.dumps(forensics.get('red_flags', []))}
  Green Flags: {json.dumps(forensics.get('green_flags', []))}

MARKET:
  Position: {market.get('competitive_position', 'N/A')}
  Current EV/EBITDA: {market.get('current_ev_ebitda', 'N/A')}x
  Competitors: {json.dumps(market.get('key_competitors', []))}

MANAGEMENT:
  Score: {mgmt.get('management_score', 'N/A')}/100 | Board: {mgmt.get('board_independence', 'N/A')}
  Governance Flags: {json.dumps(mgmt.get('governance_flags', []))}

VALUATION:
  Base Case EV: ${val.get('scenarios', {}).get('base', 0):,}M
  WACC: {val.get('wacc_pct', 0)}%
  Key Risks: {json.dumps(val.get('key_risks', []))}
"""

    # Add RAG context
    rag_text = ""
    if isinstance(rag_context, dict) and "chunks" in rag_context:
        for chunk in rag_context["chunks"]:
            # Handle both string and dict chunks
            text = chunk["text"] if isinstance(chunk, dict) else chunk
            source = chunk.get("source", "Unknown") if isinstance(chunk, dict) else "Unknown"
            rel = chunk.get("relevance", 0) if isinstance(chunk, dict) else 0
            rag_text += f"\n[RAG Source: {source}, Relevance: {rel:.2f}] {text[:500]}...\n"
    elif isinstance(rag_context, dict):
        for query, chunks in rag_context.items():
            for chunk in chunks:
                text = chunk["text"] if isinstance(chunk, dict) else chunk
                rag_text += f"\n[RAG] {text[:500]}...\n"

    debate_transcript = []
    MAX_ROUNDS = 2  # Keep to 2 for cost efficiency

    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n  --- Round {round_num}/{MAX_ROUNDS} ---")

        # History text
        history = ""
        for entry in debate_transcript:
            history += f"\n[Round {entry['round']}] {entry['role']}:\n{entry['argument']}\n"

        # DEAL CHAMPION (Bull)
        print(f"  [DEAL CHAMPION] Arguing...")
        bull_prompt = f"""You are the DEAL CHAMPION at a PE fund. Argue FOR this investment.
Cite SPECIFIC numbers from the deal brief. All values are USD millions.
{"IF BANK/FIN: Cite ROE and Justified P/Book premium. Highlight franchise value." if is_fin else "Cite Adj EBITDA and FCF conversion."}
CRITICAL: Avoid generic "high growth" statements. 
Highlight why the forensic red flags are manageable.
FORCE DIFFERENTIATION: Your conviction_score MUST reflect your true confidence. If the case is strong, use 9. If you are rebutting a weak bear point, use 8-9. 

{deal_brief}

PREVIOUS DEBATE:
{history}

Respond with ONLY a raw JSON object:
{{"headline": "one-line max 80 chars", "argument": "2-3 paragraphs citing specific USD M figures", "evidence_cited": ["example cited value"], "concessions": ["risks you concede"], "conviction_score": 9}}"""

        bull_resp = safe_llm_call(
            messages=[{"role": "user", "content": bull_prompt}],
            max_tokens=1500,
            temperature=0.7
        )
        
        if bull_resp:
            bull_text = bull_resp.choices[0].message.content.strip()
            # Try to parse JSON from response
            bull_arg = _parse_debate_response(bull_text, "DEAL_CHAMPION", round_num)
            debate_transcript.append(bull_arg)
            print(f"    Headline: {bull_arg['headline'][:80]}")
            print(f"    Conviction: {bull_arg['conviction_score']}/10")
        else:
            print(f"    ERROR: Bull Agent failed to respond")
            bull_arg = {"role": "DEAL_CHAMPION", "round": round_num,
                       "headline": "API Error", "argument": "LLM failed to respond",
                       "evidence_cited": [], "conviction_score": 5}
            debate_transcript.append(bull_arg)

        # Update history
        history += f"\n[Round {round_num}] DEAL_CHAMPION:\n{bull_arg.get('argument', '')}"

        # RISK PARTNER (Bear)
        print(f"  [RISK PARTNER] Rebutting...")
        bear_prompt = f"""You are the RISK PARTNER at a PE fund. Stress-test this investment.
Attack the WEAKEST assumptions using SPECIFIC numbers from the deal brief.
{"IF BANK/FIN: Attack ROE sustainability, credit cycle risk, and partnership renewal risk. DO NOT MENTION GENERIC CURRENCY RISK." if is_fin else "Attack EBITDA margin and FCF conversion assumptions."}
CRITICAL: Focus on specific sector risks (e.g. Gen-Z adoption for payments, NCO expansion for credit).
FORCE DIFFERENTIATION: Your conviction_score MUST reflect your intensity. Do NOT copy the champion's score. If you are winning the argument, use 8-9.

{deal_brief}

PREVIOUS DEBATE:
{history}

Respond with ONLY a raw JSON object:
{{"headline": "one-line max 80 chars", "argument": "2-3 paragraphs attacking specific assumptions", "evidence_cited": ["example cited value"], "concessions": ["bull points you concede"], "conviction_score": 7}}"""

        bear_resp = safe_llm_call(
            messages=[{"role": "user", "content": bear_prompt}],
            max_tokens=1500,
            temperature=0.6
        )
        
        if bear_resp:
            bear_text = bear_resp.choices[0].message.content.strip()
            bear_arg = _parse_debate_response(bear_text, "RISK_PARTNER", round_num)
            debate_transcript.append(bear_arg)
            print(f"    Headline: {bear_arg['headline'][:80]}")
            print(f"    Conviction: {bear_arg['conviction_score']}/10")
        else:
            print(f"    ERROR: Bear Agent failed to respond")
            bear_arg = {"role": "RISK_PARTNER", "round": round_num,
                       "headline": "API Error", "argument": "LLM failed to respond",
                       "evidence_cited": [], "conviction_score": 5}
            debate_transcript.append(bear_arg)

    # Determine consensus
    final_bull = debate_transcript[-2].get("conviction_score", 5)
    final_bear = debate_transcript[-1].get("conviction_score", 5)

    if final_bull >= 7 and final_bear <= 4:
        consensus = "BULL_DOMINANT"
    elif final_bear >= 7 and final_bull <= 4:
        consensus = "BEAR_DOMINANT"
    else:
        consensus = "CONTESTED"

    debate_result = {
        "debate_transcript": debate_transcript,
        "total_rounds": MAX_ROUNDS,
        "champion_final_conviction": final_bull,
        "risk_partner_final_conviction": final_bear,
        "consensus_reached": consensus != "CONTESTED",
        "consensus_type": consensus,
        "debate_status": consensus
    }

    print(f"\n  DEBATE RESULT: {consensus}")
    print(f"    Champion: {final_bull}/10 | Risk Partner: {final_bear}/10")

    return debate_result


def _parse_debate_response(text, role, round_num):
    """Parses JSON from LLM response. Handles markdown fences and multiline strings."""
    import re

    # Strip markdown code fences
    cleaned = re.sub(r'```json\s*', '', text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()

    # Method 1: Direct parse
    try:
        parsed = json.loads(cleaned)
        parsed["role"] = role
        parsed["round"] = round_num
        if "conviction_score" in parsed:
            parsed["conviction_score"] = int(float(str(parsed["conviction_score"])))
        return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Method 2: Find JSON block, sanitize newlines inside string values
    brace_depth = 0
    start = -1
    for i, ch in enumerate(cleaned):
        if ch == '{':
            if start == -1:
                start = i
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
            if brace_depth == 0 and start != -1:
                candidate = cleaned[start:i+1]
                # Replace literal newlines inside JSON strings with \\n
                # Preserve spaces - only replace newlines if they are clearly breaking a JSON key/value
                candidate = re.sub(r'([a-zA-Z0-9])[\r\n]+([a-zA-Z0-9])', r'\1 \2', candidate)
                candidate_flat = candidate.replace('\n', ' ').replace('\r', ' ')
                for attempt in [candidate, candidate_flat]:
                    try:
                        parsed = json.loads(attempt)
                        parsed["role"] = role
                        parsed["round"] = round_num
                        if "conviction_score" in parsed:
                            parsed["conviction_score"] = int(float(str(parsed["conviction_score"])))
                        return parsed
                    except (json.JSONDecodeError, ValueError):
                        continue
                start = -1

    # Method 3: Regex extraction of individual fields
    headline_m = re.search(r'"headline"\s*:\s*"([^"]+)"', cleaned)
    arg_m = re.search(r'"argument"\s*:\s*"(.+?)"\s*,\s*"', cleaned, re.DOTALL)
    conv_m = re.search(r'"conviction_score"\s*:\s*(\d+)', cleaned)

    if headline_m:
        return {
            "role": role,
            "round": round_num,
            "headline": headline_m.group(1)[:100],
            "argument": arg_m.group(1).replace('\n', ' ') if arg_m else cleaned,
            "evidence_cited": [],
            "sources_cited": [],
            "concessions": [],
            "conviction_score": int(conv_m.group(1)) if conv_m else 6
        }

    # Final fallback
    return {
        "role": role,
        "round": round_num,
        "headline": text[:100] if text else "No response",
        "argument": text,
        "evidence_cited": [],
        "sources_cited": [],
        "concessions": [],
        "conviction_score": 5
    }


# =====================================================================
# STEP 5: IC Decision (Agent 7) via NVIDIA
# =====================================================================

def run_nvidia_ic_decision(deal_context, debate_result):
    """Runs the IC Agent using NVIDIA NIM API."""
    print("\n" + "=" * 60)
    print("  STEP 5: Investment Committee Decision")
    print("  LLM: NVIDIA NIM (" + get_nvidia_model() + ")")
    print("=" * 60)

    client = get_nvidia_client()
    if not client:
        fallback = build_canonical_verdict(deal_context, {}, debate_result)
        return {
            "decision": fallback["decision"],
            "verdict": fallback["decision"],
            "conviction_level": fallback["conviction"],
            "reasoning": fallback["reasoning"],
            "conditions": fallback["conditions"],
            "key_conditions": fallback["conditions"],
            "max_entry_price": fallback["max_entry_price"],
        }
    transcript = ""
    for entry in debate_result.get("debate_transcript", []):
        transcript += f"\n[Round {entry.get('round')}] {entry.get('role')}: {entry.get('headline')} (Conviction: {entry.get('conviction_score')}/10)\n"

    val = deal_context.get("valuation", {})
    forensics = deal_context.get("forensics", {})
    
    ic_prompt = f"""You are the IC CHAIR at a Private Equity fund. Render a final decision.
DECISION RULES:
1. RESPECT THE DEBATE: The Deal Champion scored {debate_result.get('champion_final_conviction', 5)}/10 and the Risk Partner scored {debate_result.get('risk_partner_final_conviction', 5)}/10. 
   - If the Champion won (higher score), you MUST favor APPROVE/HOLD unless Implied Downside > 40% OR Forensic Score < 40.
   - If you override the debate winner, you MUST provide quantified reasoning.
2. VALUATION SENSITIVITY: {val.get('implied_return_pct', 0)}% implied upside/downside.
3. QUALITY BIAS: For 30%+ ROE franchises, value stability and moat over minor model discounts.

STRATEGIC OUTLOOK MANDATE (Fix 1):
- WHAT MUST GO RIGHT (generate exactly 3 bullets):
  - Each bullet is a SPECIFIC ASSUMPTION the bull case depends on.
  - Format: "[Assumption] - [why it matters to valuation]"
  - DO NOT list financial metrics or monitoring actions.
  - Minimum 40 characters per bullet.
- WHAT MUST GO WRONG (generate exactly 3 bullets):
  - Each bullet is a SPECIFIC RISK that would break the thesis.
  - Format: "[Risk] - [potential impact on equity value]"
  - DO NOT mention currency risk or generic macro unless company-specific.

TRANSCRIPT:
{transcript}

CONTEXT:
{json.dumps(deal_context, indent=2)}

Respond with ONLY a raw JSON object:
{{
  "decision": "APPROVE | APPROVE WITH CAUTION | HOLD | REJECT",
  "conviction_level": "HIGH | MEDIUM | LOW",
  "reasoning": ["3-4 specific reasons"],
  "max_entry_price": float,
  "conditions": ["list"],
  "strategic_outlook": {{
    "what_must_go_right": ["3 analytical bullets"],
    "what_must_go_wrong": ["3 analytical bullets"]
  }}
}}
"""

    try:
        response = safe_llm_call(
            messages=[{"role": "user", "content": ic_prompt}],
            temperature=0.1
        )
        
        if response:
            ic_text = response.choices[0].message.content.strip()
            import re
            match = re.search(r'\{.*\}', ic_text, re.DOTALL)
            if match:
                res = json.loads(match.group(0))
                if "max_entry_price" not in res and "max_entry_ev" in res:
                    res["max_entry_price"] = res["max_entry_ev"] / deal_context.get('financial_data', {}).get('shares_outstanding_M', 1)
                if "decision" not in res and "verdict" in res:
                    res["decision"] = res["verdict"]
                if "conditions" not in res and "key_conditions" in res:
                    res["conditions"] = res["key_conditions"]
                canonical = build_canonical_verdict(deal_context, res, debate_result)
                res.update({
                    "decision": canonical["decision"],
                    "verdict": canonical["decision"],
                    "conviction_level": res.get("conviction_level") or canonical["conviction"],
                    "reasoning": _as_list(res.get("reasoning")) or canonical["reasoning"],
                    "conditions": _as_list(res.get("conditions")) or canonical["conditions"],
                    "max_entry_price": canonical["max_entry_price"],
                })
                deal_context["ic_decision"] = res
                
                # Print Verdict
                print(f"  IC VERDICT: {res.get('decision', 'N/A')}")
                return res
    except Exception as e:
        print(f"  ERROR: {e}")
        fallback = build_canonical_verdict(deal_context, {"reasoning": [f"IC Agent error: {e}"]}, debate_result)
        return {"decision": fallback["decision"], "verdict": fallback["decision"], "reasoning": fallback["reasoning"], "max_entry_price": fallback["max_entry_price"], "conditions": fallback["conditions"]}


def _parse_ic_response(text):
    """Parses IC JSON response."""
    import re
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {
        "decision": "REJECT",
        "conviction_level": "LOW",
        "executive_summary": text,
        "key_thesis_points": [],
        "conditions": [],
        "debate_winner": "DRAW",
        "thesis_pillars": ["N/A", "N/A"],
        "go_right": ["N/A", "N/A"],
        "go_wrong": ["N/A", "N/A"],
        "reasoning": "N/A",
        "risk_assessment": "N/A"
    }


def _save_to_memory(deal_context, ic_decision):
    """Saves IC decision to SQLite for reflection memory."""
    from project_veritas.agents.ic_agent import _save_decision

    try:
        _save_decision(
            company_name=deal_context.get("company_name", "Unknown"),
            sector=deal_context.get("sector", ""),
            decision=ic_decision,
            forensic_score=deal_context.get("forensics", {}).get("forensic_score", 0),
            management_score=deal_context.get("management", {}).get("management_score", 0)
        )
        print(f"  Memory: Decision saved to SQLite")
    except Exception as e:
        print(f"  Memory: Failed to save — {e}")


def print_final_summary(ticker: str, deal_context: dict, ic_decision: dict, debate_result: dict):
    """Prints institutional-grade investment summary."""
    intel = deal_context.get('market_intel', {})
    is_fin = intel.get('is_financial', False)
    tier = intel.get('tier', 4)
    forensics = deal_context.get('forensics', {})
    val = deal_context.get('valuation', {})
    scen = val.get('scenarios', {})
    fin = deal_context.get('financial_data', {})
    canonical = build_canonical_verdict(deal_context, ic_decision, debate_result)
    deal_context["canonical_verdict"] = canonical
    
    tier_labels = {1: "Banks/Insurance", 2: "Asset-Light/Network", 3: "Tech/Growth", 4: "General Industrial"}
    
    print("\n" + "="*70)
    print("  EXECUTIVE SUMMARY")
    print(f"  {ticker} | {_fmt_price(canonical['current_price'])} | Fair Value: {_fmt_price(canonical['fair_price'])} | Upside: {_fmt_pct(canonical['implied_return_pct'])} | {canonical['decision']}")
    print(f"  ROE: {_fmt_pct(intel.get('roe_pct'))} | Growth: {_fmt_pct(intel.get('revenue_growth_pct'))} | Forensic: {forensics.get('forensic_score', 0)} | Management: {deal_context.get('management', {}).get('management_score', 0)}")
    print("="*70)

    print("\n" + "="*70)
    print("  PIPELINE COMPLETE - FINAL SUMMARY (ALL LIVE DATA)")
    print("="*70)
    
    print(f"\n  REPORT GENERATED: {deal_context.get('timestamp')}")
    print(f"  Company:          {deal_context.get('company_name')} ({ticker})")
    print(f"  Sector/Tier:      {deal_context.get('sector')} | Tier {tier}: {tier_labels.get(tier)}")

    if is_fin:
        print("\n------------------------------")
        print("  FINANCIAL SNAPSHOT (Bank Metrics)")
        print("------------------------------")
        print(f"  Revenue (TTM):    ${intel['revenue_ttm_m']:,.1f}M (Growth: {intel['revenue_growth_pct']:.1f}%)")
        print(f"  Net Income (TTM): ${intel['net_income_m']:,.1f}M")
        print(f"  ROE:              {intel['roe_pct']:.1f}%")
        print(f"  Efficiency Ratio: {intel['efficiency_ratio']:.1f}%" if intel['efficiency_ratio'] else "  Efficiency Ratio: N/A")
        print(f"  Book Value/Share: ${intel['book_value_ps']:.2f}")
        print(f"  Dividend Yield:   {intel['div_yield_pct']:.2f}%" if intel['div_yield_pct'] else "  Dividend Yield:   0.00%")
        
        print("\n----------------------------------------")
        print("  PEER COMPARABLES (Bank Metrics)")
        print("----------------------------------------")
        print("  Ticker   | Type      | P/E Ratio | P/Book | ROE")
        print("  " + "-"*55)
        # Peer comparison row for banks
        t_pe = f"{intel.get('pe_ratio', 0):.1f}x" if intel.get('pe_ratio') else "N/A"
        t_pb = f"{intel.get('price_to_book', 0):.2f}x" if intel.get('price_to_book') else "N/A"
        t_roe = f"{intel.get('roe_pct', 0):.1f}%" if intel.get('roe_pct') else "N/A"
        print(f"  {ticker:<8} | TARGET    | {t_pe:<9} | {t_pb:<6} | {t_roe}")
        
        for peer in intel.get('peer_comps', []):
            p_pe = peer.get('pe_ratio', 'N/A')
            p_pb = peer.get('price_to_book', 'N/A')
            p_roe = peer.get('roe_pct', 'N/A')
            p_type = peer.get("peer_type", "PRIMARY")
            note = " *" if p_type == "REFERENCE" else ""
            print(f"  {peer['ticker']:<8} | {p_type:<9} | {p_pe:<9} | {p_pb:<6} | {p_roe}{note}")
        if any(p.get("peer_type") == "REFERENCE" for p in intel.get("peer_comps", [])):
            print("  * Reference peers excluded from median valuation where applicable.")
    else:
        print("\n------------------------------")
        print("  FINANCIAL SNAPSHOT (USD M)")
        print("------------------------------")
        print(f"  Revenue (TTM):    ${intel.get('revenue_ttm_m', 0):,.1f}M (Growth: {intel.get('revenue_growth_pct', 0):.1f}%)")
        print(f"  EBITDA (Rep):     ${forensics.get('reported_ebitda_usd_m', 0):,.1f}M")
        adj_ebitda = forensics.get('adjusted_ebitda_usd_m', 0)
        adj_pct = forensics.get('ebitda_adjustment_pct', 0)
        print(f"  EBITDA (Adj):     ${adj_ebitda:,.1f}M (Adj: {adj_pct:.1f}% SBC Haircut)")
        print(f"  FCF Margin:       {forensics.get('fcf_margin', 0):.1f}%")
        
        net_debt = forensics.get('net_cash_debt_usd_m', 0)
        debt_label = "Net Cash" if net_debt < 0 else "Net Debt"
        print(f"  {debt_label}:    ${abs(net_debt):,.0f}M")
    
        print("\n----------------------------------------")
        print("  PEER COMPARABLES")
        print("----------------------------------------")
        print("  Ticker   | Adj EV/EBITDA  | EV/Rev   | Growth")
        print("  " + "-"*46)
        print(f"  {ticker:<8} | {intel.get('current_trading_multiple', 0):.1f}x          | {intel.get('current_ev_rev', 0):.1f}x     | {intel.get('revenue_growth_pct', 0):.1f}%")
        for peer in intel.get('peer_comps', []):
            print(f"  {peer.get('ticker', 'N/A'):<8} | {peer.get('ev_ebitda', 'N/A'):<14} | {peer.get('ev_rev', 'N/A'):<8} | {peer.get('rev_growth', 'N/A')}")

        # Fix 10: Precedent Transactions
        if intel.get('precedent_transactions'):
            print("\n----------------------------------------")
            print("  PRECEDENT TRANSACTIONS (CapIQ)")
            print("----------------------------------------")
            print("  Target            | Date       | Mult  | Value")
            print("  " + "-"*46)
            for tx in intel['precedent_transactions']:
                print(f"  {tx['target'][:17]:<17} | {tx['date']} | {tx['ev_ebitda']} | ${tx['value_M']:,.0f}M")

    print(f"\n  MARKET INTEL")
    print(f"  TAM/SAM/SOM:      {intel['tam_sam_som']}")
    print(f"  Competitive Moat: {intel['competitive_moat']}")

    print("\n" + "-" * 30)
    print("  SCORING AUDIT (0-100)")
    print("-" * 30)
    f_decomp = deal_context.get('forensics', {}).get('forensic_decomposition', {})
    m_decomp = deal_context.get('management', {}).get('management_decomposition', {})
    
    f_score = deal_context.get('forensics', {}).get('forensic_score', 0)
    f_comm = deal_context.get('forensics', {}).get('forensic_commentary', {})
    if is_fin:
        print(f"  FORENSIC:    {f_score} (Earnings Quality:{f_decomp.get('earnings_quality', 0)} | Capital Adequacy:{f_decomp.get('capital_adequacy', 0)} | Credit Risk:{f_decomp.get('cost_discipline', 0)})")
        if f_comm:
            print(f"    - EQ: {f_comm.get('earnings_quality', 'N/A')}")
            print(f"    - CA: {f_comm.get('capital_adequacy', 'N/A')}")
            print(f"    - CR: {f_comm.get('credit_risk', 'N/A')}")
    else:
        print(f"  FORENSIC:    {f_score} (Cash:{f_decomp.get('cash_conversion', 0)}/33 | Margin:{f_decomp.get('margin_safety', 0)}/33 | Leverage:{f_decomp.get('leverage_safety', 0)}/34)")
        if f_comm:
            print(f"    - Cash: {f_comm.get('cash_conversion', 'N/A')}")
            print(f"    - Margin: {f_comm.get('margin_safety', 'N/A')}")
            print(f"    - Lev: {f_comm.get('leverage_safety', 'N/A')}")
    
    m_score = deal_context.get('management', {}).get('management_score', 0)
    print(f"  MANAGEMENT:  {m_score} (Vision:{m_decomp.get('vision', 0)} | Execution:{m_decomp.get('execution', 0)} | Governance:{m_decomp.get('governance', 0)})")

    print("\n" + "-" * 30)
    print("  VALUATION SCENARIOS (Equity Value)")
    print("-" * 30)
    wacc = deal_context['valuation'].get('wacc_pct', 'N/A')
    wacc_label = "Cost of Equity" if is_fin else "WACC (Cost of Capital)"
    print(f"  {wacc_label}: {wacc}% (Damodaran Logic)")
    if deal_context.get('framing') == "LBO":
        print(f"  LBO IRR (Estimated): {deal_context.get('lbo_irr_est')}% (5-yr exit)")
    
    val_unit = "Equity" if is_fin else "EV"
    print(f"  BEAR CASE {val_unit}:   {_fmt_m(scen.get('bear', 0))}")
    print(f"  BASE CASE {val_unit}:   {_fmt_m(scen.get('base', 0))}")
    print(f"  BULL CASE {val_unit}:   {_fmt_m(scen.get('bull', 0))}")

    cross = val.get("valuation_cross_check", {})
    if is_fin and cross:
        shares = fin.get("shares_outstanding_M") or 0
        print("\n  VALUATION CROSS-CHECK")
        print(f"  P/Book Method:  {_fmt_price(cross.get('pbook_equity_m', 0) / shares if shares else None)} ({cross.get('fair_p_book', 0):.2f}x x ${fin.get('book_value_ps', 0):.2f} BV/share)")
        print(f"  P/E Method:     {_fmt_price(cross.get('pe_equity_m', 0) / shares if shares else None)} ({cross.get('fair_pe', 0):.1f}x earnings)")
        print(f"  Blended:        {_fmt_price(canonical['fair_price'])} ({_fmt_pct(canonical['implied_return_pct'])} vs market)")
    
    # Fix 7: Sensitivity Table
    if intel.get('sensitivity_matrix'):
        sens_label = "P/Book vs ROE" if is_fin else "Multiple vs EBITDA"
        print(f"\n  VALUATION SENSITIVITY ({sens_label})")
        col_label = " -20% ROE " if is_fin else " -10% EBT "
        mid_label = " Base ROE " if is_fin else " Base EBT "
        hi_label = " +20% ROE " if is_fin else " +10% EBT "
        print(f"  Mult \\ {col_label} | {mid_label} | {hi_label}")
        print("  " + "-"*44)
        for row in intel['sensitivity_matrix']:
            vals = row['values']
            marker = " <- base" if is_fin and abs(row['multiple'] - (cross.get('fair_p_book') or row['multiple'])) < 0.01 else ""
            print(f"  {row['multiple']:>5.2f}x      | ${vals[0]/1e3:>7.1f}B | ${vals[1]/1e3:>7.1f}B | ${vals[2]/1e3:>7.1f}B{marker}")

    if is_fin and intel.get('precedent_transactions'):
        print("\n----------------------------------------")
        print("  PRECEDENT TRANSACTIONS (FIG/Banks)")
        print("----------------------------------------")
        print("  Target            | Date       | P/Book | Value")
        print("  " + "-"*46)
        for tx in intel['precedent_transactions']:
            tx_mult = tx.get('p_book') or tx.get('ev_ebitda') or "N/A"
            print(f"  {tx['target'][:17]:<17} | {tx['date']} | {tx_mult} | ${tx['value_M']:,.0f}M")

    print("\n" + "-" * 30)
    print("  ACTIONABLE VALUATION (PRICE)")
    print("-" * 30)
    fin = deal_context.get('financial_data', {})
    shares = fin.get('shares_outstanding_M', 0)
    net_debt = fin.get('net_debt_M', 0) if not is_fin else 0
    if shares > 0:
        curr_price = fin.get('current_price', 0)
        # For banks, scen['base'] IS Equity Value. For industrials, it is EV.
        fair_eq = scen.get('base', 0) if is_fin else (scen.get('base', 0) - net_debt)
        fair_price = fair_eq / shares
        upside_price = ((fair_price - curr_price) / curr_price * 100) if curr_price > 0 else 0
        print(f"  Current Price: ${curr_price:.2f}")
        print(f"  Implied Fair Value: ${fair_price:.2f}")
        print(f"  Implied Upside/Downside: {upside_price:.1f}%")
    else:
        print("  Share/Debt data not available for implied price.")

    print("\n" + "-" * 30)
    print("  ENTRY STRATEGY")
    print("-" * 30)
    entry_strategy = compute_entry_strategy(canonical["current_price"], canonical["fair_price"], canonical["decision"])
    print(f"  Fair Value:       {_fmt_price(canonical['fair_price'])}")
    print(f"  Current Price:    {_fmt_price(canonical['current_price'])}")
    print(f"  Status:           {entry_strategy.get('status')}")
    print(f"  Action:           {entry_strategy.get('action')}")
    if "max_entry" in entry_strategy:
        print(f"  Max Entry:        {_fmt_price(entry_strategy.get('max_entry'))}")
        print(f"  Accumulate Below: {_fmt_price(entry_strategy.get('accumulate_below'))}")
    else:
        print(f"  Recommended Entry:{_fmt_price(entry_strategy.get('recommended_entry'))}")
        print(f"  Aggressive Entry: {_fmt_price(entry_strategy.get('aggressive_entry'))}")
        print(f"  Walk Away Above:  {_fmt_price(entry_strategy.get('walk_away_above'))}")
    print("  Catalyst Watch:")
    for item in canonical["conditions"][:3]:
        print(f"  - {item}")

    print("\n" + "=" * 70)
    print("  EXECUTIVE INVESTMENT MEMO")
    print("=" * 70)
    print(f"  IC VERDICT:  {canonical['decision']} ({canonical['conviction']} CONVICTION)")
    print(f"  DEBATE:      {debate_result.get('debate_status', 'N/A')}")
    
    print("\n  THESIS PILLARS:")
    positive_words = ("strong", "exceeds", "quality", "growth", "roe", "moat", "fair value")
    pillars = [r for r in canonical["reasoning"] if any(w in r.lower() for w in positive_words)][:3] or ["Refer to reasoning section above"]
    for p in pillars:
        print(f"  - {p}")

    print("\n  --------------------------------------------------")
    print("  WHAT MUST GO RIGHT       | WHAT CAN GO WRONG")
    print("  --------------------------------------------------")
    company_short = deal_context.get("company_name", ticker)
    go_right = _memo_bullets(
        ic_decision.get("strategic_outlook", {}).get("what_must_go_right", []),
        [
            f"{company_short} sustains core demand - supports the base-case revenue and margin assumptions",
            "Pricing power remains intact - protects normalized earnings through the cycle",
            "Management executes capital allocation discipline - keeps downside risk within IC limits",
        ],
        min_len=40,
    )
    go_wrong = _memo_bullets(
        ic_decision.get("strategic_outlook", {}).get("what_must_go_wrong", []),
        [
            f"{company_short} loses competitive momentum -> earnings reset lower -> valuation multiple compresses",
            "Macro or credit cycle worsens -> cash flow visibility declines -> IC entry threshold moves lower",
            "Governance or regulatory issue escalates -> risk premium rises -> fair value declines materially",
        ],
        min_len=50,
    )
    for i in range(max(len(go_right), len(go_wrong))):
        left = (go_right[i]) if i < len(go_right) else ""
        right = go_wrong[i] if i < len(go_wrong) else ""
        print(f"   {left[:45]:<45} |  {right}")

    # Thesis/Risks/Conds
    print(f"\n[REASONING]")
    print(_fmt_bullets(canonical["reasoning"]))

    print(f"\n[RISKS]")
    print(_fmt_bullets(canonical["risks"]))

    print(f"\n[CONDITIONS]")
    print(_fmt_bullets(canonical["conditions"] + ["Verify TTM FCF accuracy vs quarterly capex lumpy-ness."]))

    print("\n" + "=" * 70)
    print("  MODEL LIMITATIONS & CAVEATS")
    print("=" * 70)
    print("  - Valuation is an automated screening estimate, not a full investment bank fairness opinion.")
    print("  - Forensic score uses public data only and does not replace a QoE engagement.")
    print("  - Peer set is algorithmic and should be reviewed by a sector banker or PE associate.")
    print("  - Management assessment excludes proprietary reference checks.")
    print("  - Use this output as IC preparation, not final diligence sign-off.")

    print("\n" + "=" * 70)
    print("  DATA PROVENANCE & FOOTNOTES")
    print("=" * 70)
    print("  • Financials: yfinance (TTM Summation Logic)")
    print("  • Peer Sets: CapIQ (Primary) / Sector fallbacks")
    print("  • Valuation: Damodaran/IB Methodology via RAG Math Agent")
    print("  • Search: Tavily (Market Intel & Competitive Moats)")
    print(f"  • Decision: Multi-Agent NVIDIA NIM ({get_nvidia_model()})")
    print("=" * 70)


if __name__ == "__main__":
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    ticker = args[0] if args else "NVDA"
    llm_backend = "Fireworks AI" if os.environ.get("FIREWORKS_API_KEY") else "NVIDIA NIM API"

    print("\n" + "=" * 70)
    print("  PROJECT VERITAS — Full Pipeline Test (LIVE DATA)")
    print(f"  Target: {ticker}")
    print(f"  LLM Backend: {llm_backend}")
    print(f"  Model: {get_nvidia_model()}")
    print("=" * 70)
    
    # Ensure fresh data for every run (Fix 5)
    PeerDiscoveryEngine.clear_cache()

    # Step 1: Test ChromaDB
    industry_info = yf.Ticker(ticker).info.get('industry', 'Technology')
    rag_context = test_chromadb_rag(ticker, industry_info)

    # Step 2: Pull LIVE financials from yfinance
    deal_context = build_deal_context_live(ticker)
    if not deal_context:
        print(f"\n[CRITICAL ERROR] Pipeline halted: Could not retrieve data for {ticker}.")
        sys.exit(1)

    # Step 3: Run debate
    debate_result = run_nvidia_debate(deal_context, rag_context) or {"debate_status": "BYPASSED", "debate_transcript": []}

    # Step 4: IC Decision
    ic_decision = run_nvidia_ic_decision(deal_context, debate_result) or {"decision": "BYPASSED", "thesis_pillars": ["N/A"]}

    # Step 5: Final Summary
    print_final_summary(ticker, deal_context, ic_decision, debate_result)
