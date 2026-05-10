
Project Veritas — Complete Build Specification for Codex
File: CODEX_BUILD_SPEC.md
# PROJECT VERITAS — Complete Build & Deployment Specification
# For: Codex (AI coding agent)
# Date: May 9, 2026
# Owner: Moosa
# Deadline: May 19, 2026

---

## TABLE OF CONTENTS
1. Project Context & Current State
2. Remaining Backend Fixes (Priority Ordered)
3. Frontend Build (Streamlit + HTML Report)
4. Pipeline Refactor (Connect Backend to Frontend)
5. GitHub Repository Setup
6. Knowledge Base Distribution (HuggingFace)
7. Deployment Instructions
8. File-by-File Specification
9. Testing Checklist

---

## 1. PROJECT CONTEXT & CURRENT STATE

### What This Project Is
Project Veritas is a multi-agent AI system that produces institutional-grade Private Equity due diligence reports for any public company. It uses:
- RAG (ChromaDB + BGE-M3 embeddings) over 40+ finance textbooks
- Live market data (yfinance)
- Precedent transaction data (S&P Capital IQ Excel exports)
- Multi-agent LLM debate (NVIDIA NIM API — Llama 3.3 70B)
- Tavily web search for market intelligence

### Current Architecture (Working)
User inputs ticker (e.g., "PG") → Step 1: RAG retrieves relevant knowledge chunks from ChromaDB → Step 2: Pulls live financial data from yfinance + loads CapIQ peers/precedents → Step 3: RAG Math Agent computes fair valuation multiple → Step 4: Multi-agent IC debate (Deal Champion vs Risk Partner, 2 rounds) → Step 5: IC Chair makes final decision (APPROVE / HOLD / REJECT) → Report renderer outputs formatted investment memo

### What Currently Works
- Full pipeline runs end-to-end from terminal: `python test_full_pipeline.py TICKER`
- Correctly routes banks (P/Book valuation) vs industrials (EV/EBITDA valuation)
- Produces executive summary, peer comps, valuation scenarios, IC memo, entry strategy
- Data accuracy verified for: AXP, PG, MS, BABA
- ChromaDB has ~6000 chunks embedded from 40+ books
- CapIQ has 11 precedent transaction files + 11 public comp files (global, all sectors)

### What Needs to Be Built
1. Backend fixes (formatting, logic bugs) — detailed in Section 2
2. Streamlit frontend with live agent progress — detailed in Section 3
3. HTML report export (professional, downloadable) — detailed in Section 3
4. Pipeline refactor to support both terminal and web UI — detailed in Section 4
5. GitHub repo structure with proper secrets handling — detailed in Section 5
6. Knowledge base hosted on HuggingFace for public access — detailed in Section 6

### Technical Environment
- Python: 3.14 (Windows)
- Location: C:\Users\Moosa\Downloads\Project_Veritas\
- Key packages: torch, transformers, FlagEmbedding, chromadb, yfinance, pandas, openai, tavily-python, streamlit
- LLM: NVIDIA NIM API (meta/llama-3.3-70b-instruct) via OpenAI-compatible endpoint
- Embeddings: BAAI/bge-m3 (1024 dimensions, runs on CPU)
- ChromaDB: Local persistent storage

---

## 2. REMAINING BACKEND FIXES

### FIX 1: "What Must Go Right / What Can Go Wrong" — Prompt Fix
**Priority:** P0 (must fix)
**Location:** The module that generates the IC memo text (likely in the IC agent or report renderer)
**Problem:** These columns output raw financial numbers ($24,382M, 489,486.7M) or truncated sentences instead of analytical content.

**Implementation:**
- Find the LLM prompt that generates "What Must Go Right" and "What Can Go Wrong"
- Replace with this exact prompt structure:

WHAT MUST GO RIGHT (generate exactly 3 bullets): Rules:

Each bullet is a SPECIFIC ASSUMPTION the bull case depends on
Format: "[Assumption] — [why it matters to valuation]"
Must reference the company's actual business/sector
DO NOT list financial metrics or monitoring actions
Minimum 40 characters per bullet
Good example: "Pricing power holds through recession — supports 28% EBITDA margin assumption" Bad example: "Adjusted EBITDA: $24,382M" (this is a data point, not an assumption) Bad example: "Monitor the company" (this is an action, not an assumption)

WHAT CAN GO WRONG (generate exactly 3 bullets): Rules:

Each bullet is a SPECIFIC DOWNSIDE SCENARIO that causes capital loss
Format: "[Event] → [financial impact] → [valuation impact]"
Must be company-specific, not generic
DO NOT repeat numbers from the financial snapshot
Minimum 50 characters per bullet
Good example: "Input cost inflation +300bps → EBITDA drops 15% → stock to $125 (25% downside)" Bad example: "Market conditions worsen" (too generic) Bad example: "$24,382.0M EBITDA" (this is just a number)

- Also increase the display column width to 80 characters (or switch to stacked vertical layout instead of side-by-side columns if truncation persists)
- Add validation: if any generated bullet is <30 characters or starts with "$", regenerate that bullet

### FIX 2: Entry Strategy — Handle "Below Fair Value" Case
**Priority:** P0
**Location:** Entry strategy computation module
**Problem:** When stock trades BELOW fair value (e.g., PG at $146 vs fair $199), the system outputs "Aggressive Entry: $219" which is above fair value. This is contradictory.

**Implementation:**
```python
def compute_entry_strategy(current_price, implied_fair_value, verdict):
    if current_price < implied_fair_value:
        # Stock is BELOW fair value — attractive entry
        discount_pct = (implied_fair_value - current_price) / implied_fair_value * 100
        return {
            "status": "BELOW FAIR VALUE — ATTRACTIVE ENTRY",
            "fair_value": implied_fair_value,
            "current_price": current_price,
            "discount": f"{discount_pct:.1f}%",
            "max_entry": implied_fair_value,  # Don't pay above fair value even on rally
            "accumulate_below": current_price * 0.90,  # Add on 10% dips
            "action": f"BUY at current levels ({discount_pct:.0f}% below fair value)"
        }
    else:
        # Stock is ABOVE fair value — wait for pullback
        premium_pct = (current_price - implied_fair_value) / implied_fair_value * 100
        return {
            "status": "ABOVE FAIR VALUE — WAIT FOR PULLBACK",
            "fair_value": implied_fair_value,
            "current_price": current_price,
            "premium": f"{premium_pct:.1f}%",
            "recommended_entry": implied_fair_value * 0.90,  # 10% margin of safety
            "aggressive_entry": implied_fair_value * 1.10,  # Accept 10% premium for quality
            "walk_away_above": implied_fair_value * 1.33,  # Never pay 33%+ premium
            "action": f"WAIT — currently {premium_pct:.0f}% above fair value"
        }
FIX 3: Number Formatting in All LLM-Facing and Display Sections
Priority: P0 Location: Everywhere numbers appear in the final report and in data passed to LLM prompts Problem: Raw decimals: "34.419%", "6.3401275x", "$489,486.7M"

Implementation: Create a utility function used everywhere:

def fmt_number(value, num_type):
    """Format numbers consistently throughout the system."""
    if value is None:
        return "N/A"
    if num_type == 'pct':
        return f"{value:.1f}%"
    elif num_type == 'multiple':
        return f"{value:.1f}x"
    elif num_type == 'price':
        return f"${value:,.2f}"
    elif num_type == 'money':
        if abs(value) >= 1_000_000:
            return f"${value/1_000_000:,.1f}T"
        elif abs(value) >= 1_000:
            return f"${value/1_000:,.1f}B"
        else:
            return f"${value:,.0f}M"
    elif num_type == 'ratio':
        return f"{value:.2f}"
    return str(value)
Apply this:

Before injecting data into ANY LLM prompt (so the LLM sees "34.4% ROE" not "34.419234%")
In all report display sections
In the sensitivity table
In peer comp tables
FIX 4: Forensic Sub-Scores Must Sum to Total
Priority: P0 Location: Forensic scoring module Problem: Shows "Cash Conversion:100 | Margin Safety:100 | Leverage Safety:100" but total is 85.

Implementation: The forensic score must be computed as:

# Each sub-component scored out of its max
cash_conversion_score = compute_cash_conversion(data)  # returns 0-33
margin_safety_score = compute_margin_safety(data)      # returns 0-33
leverage_safety_score = compute_leverage_safety(data)  # returns 0-34

# Total is sum of sub-components
forensic_total = cash_conversion_score + margin_safety_score + leverage_safety_score

# Display shows individual scores AND they sum to total
display = f"FORENSIC: {forensic_total} (Cash:{cash_conversion_score}/33 | Margin:{margin_safety_score}/33 | Leverage:{leverage_safety_score}/34)"
If the current code computes sub-scores on a 0-100 scale, convert for display:

# Alternative: sub-scores are 0-100, total is average
forensic_total = (cash_score + margin_score + leverage_score) // 3
display = f"FORENSIC: {forensic_total}/100 (Cash:{cash_score} | Margin:{margin_score} | Leverage:{leverage_score})"
Either way: the displayed total MUST equal the mathematical combination of sub-scores. Add assertion.

FIX 5: Tier Classification — Remove or Fix
Priority: P1 Location: Sector/tier assignment Problem: Everything non-financial shows "Tier 4: General Industrial" which is meaningless.

Implementation (simplest — just remove): Replace the tier display with just the sector:

# Instead of: "Consumer Defensive | Tier 4: General Industrial"
# Show: "Consumer Defensive | Household & Personal Products"
sector_display = f"{ticker_info['sector']} | {ticker_info['industry']}"
If you want to keep tiers, use data quality tiers:

TIER_MAP = {
    # Tier 1: Best data coverage, most reliable valuation
    "Technology": 1, "Healthcare": 1, "Financial Services": 1,
    "Consumer Cyclical": 1, "Communication Services": 1,
    # Tier 2: Good coverage
    "Consumer Defensive": 2, "Industrials": 2, "Energy": 2,
    # Tier 3: Moderate coverage
    "Basic Materials": 3, "Utilities": 3, "Real Estate": 3,
}
tier = TIER_MAP.get(sector, 3)
FIX 6: Risks Section — Use Debate Output, Not Raw Data
Priority: P1 Location: IC memo renderer, RISKS section Problem: Lists "$24,382M" and "Base Case EV: $489,486.7M" as risks instead of actual risk scenarios.

Implementation:

During Step 4 (debate), store the Risk Partner's final argument as a structured field
In the memo, the RISKS section should pull DIRECTLY from Risk Partner's output
Do NOT let the LLM regenerate risks from the data context — it will just dump numbers
# After debate completes:
risk_partner_arguments = debate_results['risk_partner']['final_arguments']

# In memo section:
memo['risks'] = risk_partner_arguments  # Use directly, don't regenerate
FIX 7: Cost of Equity Determinism
Priority: P1 Location: WACC/CoE computation module Problem: Same company produces different CoE across runs (9.12%, 10.26%, 10.63%)

Implementation:

def compute_cost_of_equity(ticker_info):
    """Deterministic CoE computation. Call ONCE per pipeline run."""
    # Fixed inputs
    RISK_FREE_RATE = 0.043  # 4.3% — US 10Y yield (pin this, don't pull live)
    EQUITY_RISK_PREMIUM = 0.055  # 5.5% — Damodaran 2025
    
    # Beta from yfinance (with fallback)
    beta = ticker_info.get('beta', None)
    if beta is None or beta <= 0:
        # Sector default betas
        SECTOR_BETAS = {
            "Financial Services": 1.1, "Technology": 1.25,
            "Healthcare": 0.95, "Consumer Defensive": 0.70,
            "Consumer Cyclical": 1.10, "Industrials": 1.00,
            "Energy": 1.05, "Utilities": 0.55,
            "Communication Services": 0.95, "Real Estate": 0.75,
            "Basic Materials": 1.00,
        }
        beta = SECTOR_BETAS.get(ticker_info.get('sector', ''), 1.0)
    
    # Country risk premium (0 for US, use Damodaran for others)
    country = ticker_info.get('country', 'United States')
    COUNTRY_RISK = {
        "United States": 0.0, "United Kingdom": 0.005,
        "China": 0.015, "India": 0.02, "Brazil": 0.025,
    }
    crp = COUNTRY_RISK.get(country, 0.01)
    
    coe = RISK_FREE_RATE + beta * EQUITY_RISK_PREMIUM + crp
    
    return {
        "coe": coe,
        "components": {
            "risk_free": RISK_FREE_RATE,
            "beta": beta,
            "erp": EQUITY_RISK_PREMIUM,
            "crp": crp
        }
    }
Store result in data object at Step 2. Never recompute. All downstream modules read from stored value.

FIX 8: Precedent Transactions — Filter for Available Multiples
Priority: P1 Location: Precedent transaction display module Problem: All shown deals have "N/A" for multiples, adding no analytical value.

Implementation:

def get_precedent_transactions(sector_file, sub_industry=None, min_deals=3):
    df = load_clean_transactions(sector_file)
    
    # First: try to get deals WITH multiples
    with_multiples = df[df['SPTR_TV_TO_EBITDA'].notna() & (df['SPTR_TV_TO_EBITDA'] > 0)]
    
    if len(with_multiples) >= min_deals:
        # Return top deals by recency, with multiples
        result = with_multiples.sort_values('SPTR_ANN_DATE', ascending=False).head(5)
        return result, "full"
    else:
        # Not enough with multiples — show what we have + note
        all_deals = df.sort_values('SPTR_ANN_DATE', ascending=False).head(5)
        # Also compute historical median from whatever HAS multiples
        if len(with_multiples) > 0:
            historical_median = with_multiples['SPTR_TV_TO_EBITDA'].median()
            note = f"Limited disclosed multiples. Historical sector median: {historical_median:.1f}x (n={len(with_multiples)})"
        else:
            note = "No disclosed transaction multiples available for this sector."
        return all_deals, note
FIX 9: Peer Comp Caching (Stop 3x Processing)
Priority: P1 Location: Peer data fetching module Problem: Same peers computed 3 times in a single run (visible in earlier logs)

Implementation:

# Module-level cache (persists for entire pipeline run)
_PEER_CACHE = {}

def get_peer_financials(ticker_symbol):
    """Fetch peer data with caching. Each ticker computed only once."""
    if ticker_symbol in _PEER_CACHE:
        return _PEER_CACHE[ticker_symbol]
    
    data = _fetch_peer_data_from_yfinance(ticker_symbol)  # expensive call
    _PEER_CACHE[ticker_symbol] = data
    return data

def clear_peer_cache():
    """Call at start of each pipeline run."""
    global _PEER_CACHE
    _PEER_CACHE = {}
FIX 10: Math Agent JSON Parse Error
Priority: P1 Location: RAG Math Agent (Step 3) — where it parses LLM response Problem: [!] Math Agent JSON parse failed: Invalid format specifier

Implementation: Root cause: The LLM prompt likely contains Python f-string with curly braces that conflict with JSON braces in the expected response.

Fix approach:

# Option 1: Use string.Template instead of f-strings for prompts containing JSON
from string import Template
prompt_template = Template("""
Analyze this company and respond with ONLY valid JSON:
{
    "fair_multiple": <number>,
    "methodology": "",
    "confidence": ""
}

Company data:
$company_data
""")
prompt = prompt_template.substitute(company_data=data_string)

# Option 2: If using f-strings, escape the JSON braces
prompt = f"""
Analyze {company_name} and respond with ONLY valid JSON:
{{
    "fair_multiple": ,
    "methodology": "",
    "confidence": ""
}}
"""

# Option 3: Add retry on parse failure
import json

def parse_math_agent_response(response_text, company_data):
    try:
        # Try to extract JSON from response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(response_text[json_start:json_end])
    except json.JSONDecodeError:
        pass
    
    # Retry with simpler prompt
    retry_response = call_llm("Your previous response was not valid JSON. Please respond with ONLY a JSON object: {"fair_multiple": }")
    try:
        return json.loads(retry_response)
    except:
        # Final fallback: use peer median
        return {"fair_multiple": company_data.get('peer_median_multiple', 15.0), "source": "fallback"}
3. FRONTEND BUILD SPECIFICATION
Architecture Overview
┌─────────────────────────────────────────────────────────┐
│                    STREAMLIT APP (app.py)                 │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Input Panel │→ │ Progress View│→ │ Results View  │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│         │                                     │          │
│         ▼                                     ▼          │
│  ┌─────────────────┐              ┌──────────────────┐  │
│  │pipeline_wrapper │              │ report_generator │  │
│  │ (runs backend)  │              │ (HTML export)    │  │
│  └────────┬────────┘              └──────────────────┘  │
│           │                                              │
│           ▼                                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │     EXISTING BACKEND (test_full_pipeline.py)     │    │
│  │  Step 1-5 agents, ChromaDB, yfinance, etc.       │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
File: app.py (Main Streamlit Application)
"""
Project Veritas — Streamlit Frontend
Run with: streamlit run app.py
"""
import streamlit as st
import time
import tempfile
import os
from pathlib import Path

# Page config — MUST be first Streamlit command
st.set_page_config(
    page_title="Project Veritas | PE Due Diligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional appearance
st.markdown("""

    /* Dark professional theme overrides */
    .stApp {
        background-color: #0a0a0f;
    }
    .main-header {
        font-family: 'Georgia', serif;
        color: #c9a84c;  /* Gold accent */
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0;
    }
    .sub-header {
        color: #8a8a9a;
        font-size: 1.1rem;
        margin-top: 0;
    }
    .verdict-approve {
        background: linear-gradient(135deg, #0d4b2e, #1a7a4e);
        border: 1px solid #2ecc71;
        border-radius: 8px;
        padding: 20px;
        color: white;
    }
    .verdict-hold {
        background: linear-gradient(135deg, #4a3800, #7a5f00);
        border: 1px solid #f1c40f;
        border-radius: 8px;
        padding: 20px;
        color: white;
    }
    .verdict-reject {
        background: linear-gradient(135deg, #4b0d0d, #7a1a1a);
        border: 1px solid #e74c3c;
        border-radius: 8px;
        padding: 20px;
        color: white;
    }
    .metric-card {
        background: #1a1a2e;
        border: 1px solid #2a2a4e;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
    }
    .agent-status {
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
    }

""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown("---")
    
    # API Key status indicators
    nvidia_key = os.getenv('NVIDIA_API_KEY', '')
    tavily_key = os.getenv('TAVILY_API_KEY', '')
    
    st.markdown(f"NVIDIA NIM: {'✅ Connected' if nvidia_key else '❌ Not Set'}")
    st.markdown(f"Tavily: {'✅ Connected' if tavily_key else '❌ Not Set'}")
    
    st.markdown("---")
    st.markdown("### 📊 Model")
    model_choice = st.selectbox(
        "LLM Backend",
        ["NVIDIA NIM (Llama 3.3 70B)", "Fireworks AI (DeepSeek-V3)"],
        index=0
    )
    
    st.markdown("---")
    st.markdown("### 📖 About")
    st.markdown("""
    **Project Veritas** produces PE-grade 
    due diligence reports using multi-agent 
    AI with RAG-enhanced financial analysis.
    
    Built for AMD Pervasive AI Hackathon 2026.
    """)

# --- MAIN CONTENT ---
st.markdown('PROJECT VERITAS', unsafe_allow_html=True)
st.markdown('AI-Powered Private Equity Due Diligence', unsafe_allow_html=True)

# --- INPUT SECTION ---
col1, col2 = st.columns([2, 3])

with col1:
    ticker = st.text_input(
        "Company Ticker",
        placeholder="e.g., AAPL, PG, MS",
        help="Enter any publicly traded company's ticker symbol"
    ).upper().strip()

with col2:
    uploaded_files = st.file_uploader(
        "Upload Documents (Optional)",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload annual reports, investor presentations, etc. These will be analyzed alongside our knowledge base."
    )

# Run button
run_disabled = not ticker or not nvidia_key
run_button = st.button(
    "🚀 Run Full Analysis",
    disabled=run_disabled,
    use_container_width=True,
    type="primary"
)

if run_disabled and not nvidia_key:
    st.warning("⚠️ Set NVIDIA_API_KEY environment variable before running. See README for instructions.")

# --- PIPELINE EXECUTION ---
if run_button and ticker:
    # Handle uploaded files
    uploaded_paths = []
    if uploaded_files:
        temp_dir = tempfile.mkdtemp()
        for uf in uploaded_files:
            path = os.path.join(temp_dir, uf.name)
            with open(path, 'wb') as f:
                f.write(uf.getbuffer())
            uploaded_paths.append(path)
    
    # Import pipeline (delayed import to avoid loading BGE-M3 on page load)
    from pipeline_wrapper import PipelineRunner
    
    # Progress display
    st.markdown("---")
    st.markdown("### 🔄 Analysis in Progress")
    
    # Create status containers for each agent
    status_containers = {}
    agent_steps = [
        ("rag", "📚 Agent 1: Knowledge Retrieval (RAG)", "Querying embedded finance textbooks..."),
        ("data", "📊 Agent 2: Live Market Data", "Pulling financials from yfinance + CapIQ..."),
        ("math", "🧮 Agent 3: Valuation Math", "Computing fair multiple & building scenarios..."),
        ("debate", "⚔️ Agent 4: IC Debate", "Deal Champion vs Risk Partner (2 rounds)..."),
        ("decision", "⚖️ Agent 5: IC Decision", "Final verdict & entry strategy..."),
    ]
    
    for key, label, description in agent_steps:
        status_containers[key] = st.status(label, expanded=False)
        with status_containers[key]:
            st.write(description)
    
    # Progress callback function
    def update_progress(step_name, status, detail):
        if step_name in status_containers:
            with status_containers[step_name]:
                if status == "running":
                    st.write(f"⏳ {detail}")
                elif status == "complete":
                    st.write(f"✅ {detail}")
            if status == "complete":
                status_containers[step_name].update(
                    label=f"✅ {dict(agent_steps)[step_name] if step_name in dict([(k,l) for k,l,_ in agent_steps]) else step_name}",
                    state="complete",
                    expanded=False
                )
    
    # Run pipeline
    try:
        runner = PipelineRunner(ticker, uploaded_docs=uploaded_paths)
        results = runner.run(progress_callback=update_progress)
        
        # --- RESULTS DISPLAY ---
        st.markdown("---")
        
        # Executive Summary Banner
        verdict = results['verdict']['decision']
        fair_value = results['valuation']['implied_fair_value']
        current_price = results['financials']['current_price']
        upside = results['valuation']['upside_pct']
        
        verdict_class = f"verdict-{verdict.lower()}"
        verdict_emoji = {"APPROVE": "✅", "HOLD": "⏸️", "REJECT": "❌"}.get(verdict, "❓")
        
        st.markdown(f"""
        
            {verdict_emoji} {results['company_name']} ({ticker}) — {verdict}
            
                Current: ${current_price:,.2f} | 
                Fair Value: ${fair_value:,.2f} | 
                Implied: {upside:+.1f}%
            
        
        """, unsafe_allow_html=True)
        
        st.markdown("")
        
        # Key Metrics Row
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        with m1:
            st.metric("Revenue", f"${results['financials']['revenue']/1000:.1f}B")
        with m2:
            st.metric("Growth", f"{results['financials']['growth']:.1f}%")
        with m3:
            if results['mode'] == 'bank':
                st.metric("ROE", f"{results['financials']['roe']:.1f}%")
            else:
                st.metric("EBITDA", f"${results['financials']['ebitda']/1000:.1f}B")
        with m4:
            st.metric("Forensic", f"{results['forensic']['total']}/100")
        with m5:
            st.metric("Management", f"{results['management']['total']}/100")
        with m6:
            st.metric("FCF Margin", f"{results['financials'].get('fcf_margin', 0):.1f}%")
        
        # Tabs for detailed sections
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Valuation", "👥 Peers & Comps", "📝 IC Memo", "🎯 Entry Strategy", "📄 Full Report"
        ])
        
        with tab1:
            st.markdown("#### Valuation Cross-Check")
            vcol1, vcol2, vcol3 = st.columns(3)
            with vcol1:
                st.metric("Bear Case", f"${results['valuation']['bear']/1000:.1f}B")
            with vcol2:
                st.metric("Base Case", f"${results['valuation']['base']/1000:.1f}B")
            with vcol3:
                st.metric("Bull Case", f"${results['valuation']['bull']/1000:.1f}B")
            
            st.markdown("#### Sensitivity Table")
            # Display sensitivity as dataframe
            if results.get('sensitivity'):
                import pandas as pd
                st.dataframe(
                    pd.DataFrame(results['sensitivity']['table'],
                                columns=results['sensitivity']['columns'],
                                index=results['sensitivity']['index']),
                    use_container_width=True
                )
        
        with tab2:
            st.markdown("#### Peer Comparables")
            import pandas as pd
            peers_df = pd.DataFrame(results['peers'])
            st.dataframe(peers_df, use_container_width=True, hide_index=True)
            
            if results.get('precedents'):
                st.markdown("#### Precedent Transactions")
                prec_df = pd.DataFrame(results['precedents'])
                st.dataframe(prec_df, use_container_width=True, hide_index=True)
        
        with tab3:
            st.markdown("#### Investment Committee Memo")
            
            st.markdown(f"**Verdict:** {verdict} ({results['verdict']['conviction']} conviction)")
            st.markdown(f"**Debate:** Champion {results['debate']['champion_score']}/10 vs Risk Partner {results['debate']['risk_score']}/10")
            
            st.markdown("**Thesis Pillars:**")
            for pillar in results['memo'].get('pillars', []):
                st.markdown(f"- {pillar}")
            
            col_r, col_w = st.columns(2)
            with col_r:
                st.markdown("**What Must Go Right:**")
                for item in results['memo'].get('must_go_right', []):
                    st.markdown(f"- {item}")
            with col_w:
                st.markdown("**What Can Go Wrong:**")
                for item in results['memo'].get('can_go_wrong', []):
                    st.markdown(f"- {item}")
            
            st.markdown("**Reasoning:**")
            for r in results['verdict'].get('reasoning', []):
                st.markdown(f"- {r}")
            
            st.markdown("**Conditions:**")
            for c in results['verdict'].get('conditions', []):
                st.markdown(f"- {c}")
        
        with tab4:
            st.markdown("#### Entry Strategy")
            entry = results.get('entry_strategy', {})
            
            st.markdown(f"**Status:** {entry.get('status', 'N/A')}")
            st.markdown(f"**Fair Value:** ${entry.get('fair_value', 0):,.2f}")
            st.markdown(f"**Current Price:** ${entry.get('current_price', 0):,.2f}")
            
            if entry.get('action'):
                st.info(f"💡 **Action:** {entry['action']}")
            
            if entry.get('recommended_entry'):
                st.markdown(f"- Recommended Entry: ${entry['recommended_entry']:,.2f}")
            if entry.get('aggressive_entry'):
                st.markdown(f"- Aggressive Entry: ${entry['aggressive_entry']:,.2f}")
            if entry.get('walk_away_above'):
                st.markdown(f"- Walk Away Above: ${entry['walk_away_above']:,.2f}")
            if entry.get('accumulate_below'):
                st.markdown(f"- Accumulate Below: ${entry['accumulate_below']:,.2f}")
            
            if results.get('catalysts'):
                st.markdown("**Catalyst Watch:**")
                for cat in results['catalysts']:
                    st.markdown(f"- {cat}")
        
        with tab5:
            # Full text report (same as terminal output)
            st.markdown("#### Complete Analysis Report")
            st.code(results.get('full_text_report', 'Report generation pending...'), language=None)
            
            # Download buttons
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                # HTML report download
                from report_generator import generate_html_report
                html_report = generate_html_report(results)
                st.download_button(
                    "📥 Download HTML Report",
                    data=html_report,
                    file_name=f"Veritas_{ticker}_Report.html",
                    mime="text/html",
                    use_container_width=True
                )
            with dcol2:
                # Text report download
                st.download_button(
                    "📥 Download Text Report",
                    data=results.get('full_text_report', ''),
                    file_name=f"Veritas_{ticker}_Report.txt",
                    mime="text/plain",
                    use_container_width=True
                )
        
        # Competitive Moat & Market Intel (below tabs)
        st.markdown("---")
        st.markdown("#### 🏰 Competitive Moat")
        st.markdown(results.get('moat', 'N/A'))
        
        st.markdown(f"**TAM/SAM/SOM:** {results.get('tam_sam_som', 'N/A')}")
        
        # Limitations footer
        st.markdown("---")
        st.caption("""
        ⚠️ **Limitations:** This is an automated screening tool, not a replacement for full due diligence. 
        Forensic scores use public data only. Peer sets are algorithmic. 
        Use as IC preparation, not final investment sign-off.
        """)
    
    except Exception as e:
        st.error(f"❌ Pipeline Error: {str(e)}")
        st.exception(e)
    
    finally:
        # Cleanup temp files
        if uploaded_paths:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
File: pipeline_wrapper.py (Backend Adapter)
Purpose: Wraps the existing pipeline to support Streamlit's progress callbacks and structured output.

Specification:

"""
Pipeline Wrapper — Adapts existing backend for Streamlit frontend.
Provides:
  1. Progress callbacks for real-time UI updates
  2. Structured dict output (instead of print statements)
  3. Uploaded document handling (temporary RAG injection)
"""
import time
from pathlib import Path

class PipelineRunner:
    def __init__(self, ticker: str, uploaded_docs: list = None):
        """
        Args:
            ticker: Stock ticker symbol (e.g., 'PG', 'AAPL')
            uploaded_docs: List of file paths to user-uploaded PDFs
        """
        self.ticker = ticker
        self.uploaded_docs = uploaded_docs or []
        self.results = {}
    
    def run(self, progress_callback=None):
        """
        Execute full pipeline with progress updates.
        
        Args:
            progress_callback: Function(step_name, status, detail_message)
                step_name: one of ['rag', 'data', 'math', 'debate', 'decision']
                status: one of ['running', 'complete', 'error']
                detail: human-readable status message
        
        Returns:
            dict with ALL report data structured for frontend rendering
        """
        cb = progress_callback or (lambda *args: None)
        
        # ============ STEP 1: RAG ============
        cb("rag", "running", "Loading BGE-M3 and querying ChromaDB...")
        try:
            # Import your existing RAG module
            from agents.rag_agent import retrieve_context
            
            rag_results = retrieve_context(
                self.ticker,
                extra_documents=self.uploaded_docs  # Handle uploaded docs
            )
            self.results['rag'] = rag_results
            cb("rag", "complete", f"Retrieved {rag_results.get('chunk_count', 0)} relevant chunks")
        except Exception as e:
            cb("rag", "error", str(e))
            self.results['rag'] = {"chunks": [], "error": str(e)}
        
        # ============ STEP 2: DATA ============
        cb("data", "running", "Pulling live financials from yfinance...")
        try:
            from agents.data_agent import pull_live_data
            
            data_results = pull_live_data(self.ticker)
            self.results['data'] = data_results
            self.results['financials'] = data_results['financials']
            self.results['peers'] = data_results['peers']
            self.results['mode'] = data_results['mode']  # 'bank' or 'industrial'
            self.results['company_name'] = data_results['company_name']
            cb("data", "complete", f"{data_results['company_name']} — {len(data_results['peers'])} peers found")
        except Exception as e:
            cb("data", "error", str(e))
            raise
        
        # ============ STEP 3: MATH ============
        cb("math", "running", "Computing fair valuation multiple...")
        try:
            from agents.math_agent import compute_valuation
            
            math_results = compute_valuation(
                self.ticker,
                data=self.results['data'],
                rag_context=self.results['rag']
            )
            self.results['valuation'] = math_results['valuation']
            self.results['forensic'] = math_results['forensic']
            self.results['precedents'] = math_results.get('precedents', [])
            self.results['sensitivity'] = math_results.get('sensitivity', {})
            cb("math", "complete", f"Fair multiple: {math_results['valuation']['fair_multiple']:.1f}x")
        except Exception as e:
            cb("math", "error", str(e))
            raise
        
        # ============ STEP 4: DEBATE ============
        cb("debate", "running", "Deal Champion vs Risk Partner — Round 1...")
        try:
            from agents.debate_agent import run_ic_debate
            
            debate_results = run_ic_debate(
                self.ticker,
                data=self.results['data'],
                valuation=self.results['valuation'],
                forensic=self.results['forensic']
            )
            self.results['debate'] = debate_results
            cb("debate", "complete", 
               f"Champion: {debate_results['champion_score']}/10 | Risk: {debate_results['risk_score']}/10")
        except Exception as e:
            cb("debate", "error", str(e))
            raise
        
        # ============ STEP 5: DECISION ============
        cb("decision", "running", "IC Chair rendering final verdict...")
        try:
            from agents.ic_agent import make_decision
            
            decision_results = make_decision(
                self.ticker,
                data=self.results['data'],
                valuation=self.results['valuation'],
                debate=self.results['debate'],
                forensic=self.results['forensic']
            )
            self.results['verdict'] = decision_results['verdict']
            self.results['entry_strategy'] = decision_results['entry_strategy']
            self.results['memo'] = decision_results['memo']
            self.results['management'] = decision_results.get('management', {})
            self.results['moat'] = decision_results.get('moat', '')
            self.results['tam_sam_som'] = decision_results.get('tam_sam_som', '')
            self.results['catalysts'] = decision_results.get('catalysts', [])
            cb("decision", "complete", f"Verdict: {decision_results['verdict']['decision']}")
        except Exception as e:
            cb("decision", "error", str(e))
            raise
        
        # ============ GENERATE TEXT REPORT ============
        from core.report_renderer import render_text_report
        self.results['full_text_report'] = render_text_report(self.results)
        
        return self.results
IMPORTANT NOTE FOR CODEX: The imports above (from agents.rag_agent import ...) assume a specific module structure. The actual import paths depend on how the existing code is organized. Codex should:

Look at the existing test_full_pipeline.py to see how each step is currently called
Extract the logic from each step into the appropriate function call
The wrapper's job is to call the SAME logic that currently runs, but capture outputs in a dict instead of printing
If the existing code is all in one file (test_full_pipeline.py), the wrapper should import functions from that file or refactor the key steps into callable functions.

File: report_generator.py (HTML Report Export)
Purpose: Generates a beautiful standalone HTML report file for download.

Specification:

"""
Report Generator — Creates downloadable HTML investment memo.
Design: Investment bank aesthetic (navy/white/gold).
Output: Standalone HTML file with embedded CSS, no external dependencies.
"""

def generate_html_report(results: dict) -> str:
    """
    Generate a complete standalone HTML report from pipeline results.
    
    Args:
        results: Full pipeline output dictionary
    
    Returns:
        Complete HTML string ready for download/browser display
    """
    # Extract key data
    company = results.get('company_name', 'Unknown')
    ticker = results.get('ticker', '')
    verdict = results.get('verdict', {})
    financials = results.get('financials', {})
    valuation = results.get('valuation', {})
    peers = results.get('peers', [])
    memo = results.get('memo', {})
    entry = results.get('entry_strategy', {})
    forensic = results.get('forensic', {})
    management = results.get('management', {})
    
    # Verdict color
    verdict_colors = {
        "APPROVE": ("#0d4b2e", "#2ecc71"),
        "HOLD": ("#4a3800", "#f1c40f"),
        "REJECT": ("#4b0d0d", "#e74c3c")
    }
    bg_color, border_color = verdict_colors.get(verdict.get('decision', ''), ("#333", "#666"))
    
    html = f"""


    
    
    Project Veritas | {company} ({ticker}) — Due Diligence Report
    
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Georgia', 'Times New Roman', serif;
            background: #0a0a0f;
            color: #e8e8e8;
            line-height: 1.6;
            padding: 40px;
            max-width: 1100px;
            margin: 0 auto;
        }}
        .header {{
            border-bottom: 2px solid #c9a84c;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #c9a84c;
            font-size: 2.2rem;
            margin-bottom: 5px;
        }}
        .header .subtitle {{
            color: #8a8a9a;
            font-size: 1rem;
        }}
        .verdict-banner {{
            background: {bg_color};
            border: 2px solid {border_color};
            border-radius: 8px;
            padding: 25px;
            margin: 25px 0;
            text-align: center;
        }}
        .verdict-banner h2 {{
            font-size: 1.8rem;
            margin-bottom: 10px;
        }}
        .verdict-banner .price-line {{
            font-size: 1.2rem;
            color: #ccc;
        }}
        .section {{
            margin: 30px 0;
            padding: 20px;
            background: #12121a;
            border: 1px solid #2a2a3e;
            border-radius: 8px;
        }}
        .section h3 {{
            color: #c9a84c;
            font-size: 1.3rem;
            margin-bottom: 15px;
            border-bottom: 1px solid #2a2a3e;
            padding-bottom: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        th {{
            background: #1a1a2e;
            color: #c9a84c;
            padding: 10px 12px;
            text-align: left;
            font-size: 0.85rem;
            text-transform: uppercase;
        }}
        td {{
            padding: 8px 12px;
            border-bottom: 1px solid #2a2a3e;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .metric-box {{
            background: #1a1a2e;
            border: 1px solid #2a2a3e;
            border-radius: 6px;
            padding: 15px;
            text-align: center;
        }}
        .metric-box .value {{
            font-size: 1.4rem;
            color: #ffffff;
            font-weight: bold;
        }}
        .metric-box .label {{
            font-size: 0.75rem;
            color: #8a8a9a;
            text-transform: uppercase;
            margin-top: 5px;
        }}
        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .bullet-list {{
            list-style: none;
            padding: 0;
        }}
        .bullet-list li {{
            padding: 5px 0;
            padding-left: 20px;
            position: relative;
        }}
        .bullet-list li::before {{
            content: "•";
            color: #c9a84c;
            position: absolute;
            left: 0;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #2a2a3e;
            color: #6a6a7a;
            font-size: 0.8rem;
        }}
        @media print {{
            body {{ background: white; color: black; }}
            .section {{ border-color: #ddd; background: #fafafa; }}
            .header h1 {{ color: #1a3a5c; }}
        }}
    


    
        PROJECT VERITAS
        Private Equity Due Diligence Report | Generated {time.strftime('%B %d, %Y')}
    
    
    
        {verdict.get('decision', 'N/A')} — {company} ({ticker})
        
            Current: ${financials.get('current_price', 0):,.2f} | 
            Fair Value: ${valuation.get('implied_fair_value', 0):,.2f} | 
            Implied: {valuation.get('upside_pct', 0):+.1f}%
        
        Conviction: {verdict.get('conviction', 'N/A')} | 
        Debate: Champion {results.get('debate', {}).get('champion_score', 0)}/10 vs Risk {results.get('debate', {}).get('risk_score', 0)}/10
    
    
    
    
        Financial Snapshot
        
            
                ${financials.get('revenue', 0)/1000:.1f}B
                Revenue (TTM)
            
            
                {financials.get('growth', 0):.1f}%
                Growth
            
            
                {financials.get('fcf_margin', 0):.1f}%
                FCF Margin
            
            
                {forensic.get('total', 0)}/100
                Forensic Score
            
            
                {management.get('total', 0)}/100
                Management
            
            
                {financials.get('roe', financials.get('fcf_margin', 0)):.1f}%
                ROE
            
        
    
    
    
    
        Peer Comparables
        
                {''.join(f"" for p in peers)}
            
            
                
                    Ticker
                    {'P/E' if results.get('mode') == 'bank' else 'EV/EBITDA'}
                    {'P/Book' if results.get('mode') == 'bank' else 'EV/Rev'}
                    {'ROE' if results.get('mode') == 'bank' else 'Growth'}
                
            
            {p.get('ticker','')}{p.get('primary_multiple','N/A')}{p.get('secondary_multiple','N/A')}{p.get('growth_or_roe','N/A')}
        
    
    
    
    
        Valuation Scenarios
        
            
                ${valuation.get('bear', 0)/1000:.1f}B
                Bear Case
            
            
                ${valuation.get('base', 0)/1000:.1f}B
                Base Case
            
            
                ${valuation.get('bull', 0)/1000:.1f}B
                Bull Case
            
        
    
    
    
    
        Investment Committee Memo
        Thesis:
        
            {''.join(f"{p}" for p in memo.get('pillars', ['N/A']))}
        
        
        
            
                What Must Go Right:
                
                    {''.join(f"{item}" for item in memo.get('must_go_right', ['N/A']))}
                
            
            
                What Can Go Wrong:
                
                    {''.join(f"{item}" for item in memo.get('can_go_wrong', ['N/A']))}
                
            
        
        
        Reasoning:
        
            {''.join(f"{r}" for r in verdict.get('reasoning', ['N/A']))}
        
    
    
    
    
        Entry Strategy
        Status: {entry.get('status', 'N/A')}
        Action: {entry.get('action', 'N/A')}
        
            
                ${entry.get('fair_value', 0):,.2f}
                Fair Value
            
            
                ${entry.get('max_entry', entry.get('recommended_entry', 0)):,.2f}
                Max Entry
            
            
                ${entry.get('walk_away_above', entry.get('aggressive_entry', 0)):,.2f}
                Walk Away
            
        
    
    
    
    
        Competitive Moat
        {results.get('moat', 'N/A')}
        Market Sizing: {results.get('tam_sam_som', 'N/A')}
    
    
    
    
        Data Provenance: Financials from yfinance (TTM) | Peers from CapIQ/Algorithmic | 
        Valuation via Damodaran Methodology + RAG | Search via Tavily | 
        Decision via Multi-Agent NVIDIA NIM (Llama 3.3 70B)
        Limitations: Automated screening estimate only. 
        Does not replace full QoE engagement, management reference checks, or legal due diligence. 
        Use as IC preparation material.
        Generated by Project Veritas | {time.strftime('%Y-%m-%d %H:%M')}
    

"""
    
    return html
4. PIPELINE REFACTOR SPECIFICATION
Goal
Currently test_full_pipeline.py prints everything to stdout. We need it to ALSO (or instead) return a structured dictionary that both Streamlit and the terminal renderer can consume.

Approach: Keep Terminal Working, Add Wrapper Layer
DO NOT rewrite test_full_pipeline.py from scratch. Instead:

Extract the core logic of each step into callable functions (if not already)
Create pipeline_wrapper.py that calls those same functions
The wrapper captures outputs in a dict instead of printing
The original test_full_pipeline.py continues to work for terminal testing
Minimal Refactor Pattern
If test_full_pipeline.py currently looks like:

# Step 1
rag_results = some_rag_function(ticker)
print(f"  RAG STATUS: OK")

# Step 2  
data = pull_data(ticker)
print(f"  Revenue: {data['revenue']}M")
The wrapper just calls the same functions but stores results:

# In pipeline_wrapper.py
results['rag'] = some_rag_function(ticker)
results['data'] = pull_data(ticker)
# No printing — Streamlit handles display
Key Requirement: The Return Dictionary Schema
The pipeline wrapper MUST return a dict matching this exact schema (Streamlit app.py expects this):

{
    "company_name": "The Procter & Gamble Company",
    "ticker": "PG",
    "sector": "Consumer Defensive",
    "mode": "industrial",  # or "bank"
    
    "financials": {
        "revenue": 86718.0,         # in millions
        "ebitda": 24888.0,          # in millions (None for banks)
        "ebitda_adj": 24382.0,      # in millions (None for banks)
        "net_income": 14000.0,      # in millions
        "growth": 7.4,              # percentage
        "fcf_margin": 17.3,         # percentage
        "roe": 31.1,                # percentage
        "net_debt": 25705.0,        # in millions
        "current_price": 146.42,    # USD
        "market_cap": 345000.0,     # in millions
        "dividend_yield": 2.5,      # percentage
        "book_value_per_share": 49.85,  # USD (for banks)
        "efficiency_ratio": None,   # percentage (for banks, None if unavailable)
    },
    
    "peers": [
        {"ticker": "CL", "type": "PRIMARY", "ev_ebitda": 20.6, "ev_rev": 3.7, "growth": 8.4, "pe": None, "pb": None, "roe": None},
        {"ticker": "KMB", "type": "PRIMARY", "ev_ebitda": 12.8, "ev_rev": 2.4, "growth": 2.7, "pe": None, "pb": None, "roe": None},
        # ... more peers
    ],
    
    "valuation": {
        "fair_multiple": 21.1,          # EV/EBITDA for industrial, P/Book for bank
        "multiple_type": "EV/EBITDA",   # or "P/Book"
        "implied_fair_value": 199.17,   # per share USD
        "upside_pct": 36.0,             # percentage
        "bear": 391600.0,               # in millions
        "base": 489500.0,               # in millions
        "bull": 587400.0,               # in millions
        "wacc": 9.5,                    # percentage (or "coe" for banks)
        "methodology_note": "EV/EBITDA with peer-relative and DCF cross-check"
    },
    
    "sensitivity": {
        "columns": ["-10% EBITDA", "Base EBITDA", "+10% EBITDA"],
        "index": ["19.1x", "20.1x", "21.1x", "22.1x", "23.1x"],
        "table": [
            [419800, 466400, 513100],
            [441700, 490800, 539900],
            [463700, 515200, 566700],  # <- base row
            [485600, 539600, 593500],
            [507600, 564000, 620400],
        ],
        "base_row_index": 2  # which row is the base case
    },
    
    "precedents": [
        {"target": "B.F. S.p.A.", "date": "2026-04-21", "multiple": None, "value": 1407.0},
        # ... more deals
    ],
    
    "debate": {
        "champion_score": 9,
        "risk_score": 6,
        "winner": "DEAL_CHAMPION",
        "champion_headline": "PG Investment",
        "risk_headline": "PG Overvalued",
        "rounds": 2
    },
    
    "verdict": {
        "decision": "APPROVE",       # APPROVE | HOLD | REJECT
        "conviction": "HIGH",        # HIGH | MEDIUM | LOW
        "reasoning": [
            "Deal Champion's 9/10 conviction reflects strong fundamental case",
            "ROE of 31.1% with stable margins indicates durable competitive advantage",
            "Forensic score of 85 confirms earnings quality",
        ],
        "conditions": [
            "Monitor EU antitrust investigation outcome",
            "Verify FCF conversion remains above 80%",
        ]
    },
    
    "entry_strategy": {
        "status": "BELOW FAIR VALUE — ATTRACTIVE ENTRY",
        "fair_value": 199.17,
        "current_price": 146.42,
        "action": "BUY at current levels (27% below fair value)",
        "max_entry": 199.17,
        "accumulate_below": 131.78,
        # OR (if above fair value):
        # "recommended_entry": 179.25,
        # "aggressive_entry": 219.08,
        # "walk_away_above": 264.89,
    },
    
    "memo": {
        "pillars": [
            "High ROE of 31.1% with stable operating margins suggests durable moat",
            "Forensic score of 85 confirms strong earnings quality and cash conversion",
        ],
        "must_go_right": [
            "Pricing power holds through economic slowdown — supports 28% EBITDA margin",
            "Emerging market volume growth continues (India, China, Africa)",
            "SKU rationalization yields 100bps margin expansion by 2027",
        ],
        "can_go_wrong": [
            "Input cost inflation (oil, pulp) +300bps → EBITDA drops 15% → stock to $125",
            "EU antitrust fine materialization → €500M+ one-time charge → -3% EPS",
            "Private label share gains in recession → volume decline 5% → negative growth",
        ]
    },
    
    "forensic": {
        "total": 85,
        "sub_scores": {
            "cash_conversion": {"score": 33, "max": 33, "explanation": "FCF/NI ratio of 107% indicates excellent cash conversion"},
            "margin_safety": {"score": 30, "max": 33, "explanation": "EBITDA margin stable within 100bps of 3-year average"},
            "leverage_safety": {"score": 22, "max": 34, "explanation": "Net Debt/EBITDA of 1.03x — moderate but manageable"},
        }
    },
    
    "management": {
        "total": 80,
        "sub_scores": {"vision": 90, "execution": 80, "governance": 70}
    },
    
    "moat": "Procter & Gamble's competitive moat is anchored in intangible assets and scale economics...",
    "tam_sam_som": "TAM: $2.75T | SAM: $386.3B | SOM: $65.6B",
    "catalysts": [
        "EU antitrust resolution — removes overhang",
        "Emerging market penetration acceleration",
        "SKU rationalization margin benefits H2 2026",
    ],
    
    "full_text_report": "======= FULL TEXT OUTPUT AS CURRENTLY PRINTED ======="
}
5. GITHUB REPOSITORY SETUP
Step-by-Step Instructions
Step 1: Create .gitignore (DO THIS FIRST — before any git commands)

Create file C:\Users\Moosa\Downloads\Project_Veritas\.gitignore with this exact content:

# ===========================
# PROJECT VERITAS .gitignore
# ===========================

# ----- SECRETS (NEVER COMMIT) -----
.env
*.env
.env.*
secrets/
api_keys.py
config/local_settings.py

# ----- DATA (proprietary/large) -----
data/capiq/**/*.xlsx
data/capiq/**/*.csv
data/capiq/precedent_transactions/
data/capiq/public_comps/
data/knowledge_base/**/*.pdf
data/knowledge_base/**/*.epub
!data/**/.gitkeep
!data/**/README.md

# ----- VECTOR STORE (user rebuilds locally) -----
chroma_db/
chromadb_store/
*.sqlite3
!memory.sqlite3.example

# ----- ML MODELS (download from HuggingFace) -----
.cache/
models/
*.bin
*.safetensors
*.onnx

# ----- PYTHON -----
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.venv/
venv/
env/
.eggs/

# ----- IDE -----
.vscode/settings.json
.vscode/launch.json
.idea/
*.swp
*.swo

# ----- OS -----
.DS_Store
Thumbs.db
Desktop.ini

# ----- OUTPUT/TEMP -----
outputs/
reports/*.html
reports/*.pdf
*.log
tmp/
temp/

# ----- NOTEBOOKS -----
.ipynb_checkpoints/
Step 2: Create .env.example

# ============================================
# PROJECT VERITAS — Environment Configuration
# ============================================
# Copy this file to .env: cp .env.example .env
# Then fill in your actual API keys below.
# NEVER commit the .env file to git.

# ----- REQUIRED -----

# NVIDIA NIM API Key (for LLM inference)
# Sign up free at: https://build.nvidia.com/
# Used for: Multi-agent debate, IC decision, forensic analysis
NVIDIA_API_KEY=your-nvidia-nim-api-key-here

# Tavily Search API Key (for market intelligence)
# Sign up free at: https://tavily.com/ (1000 searches/month free)
# Used for: Competitive moat analysis, TAM/SAM/SOM, risk discovery
TAVILY_API_KEY=your-tavily-api-key-here

# ----- OPTIONAL -----

# HuggingFace Token (faster BGE-M3 model downloads, avoids rate limits)
# Get at: https://huggingface.co/settings/tokens
# HF_TOKEN=your-huggingface-token-here

# Fireworks AI (alternative LLM backend)
# FIREWORKS_API_KEY=your-fireworks-key-here

# ----- MODEL CONFIGURATION -----

# LLM Model (via NVIDIA NIM)
LLM_MODEL=meta/llama-3.3-70b-instruct
LLM_BASE_URL=https://integrate.api.nvidia.com/v1

# Embedding Model (downloaded from HuggingFace, runs locally)
EMBEDDING_MODEL=BAAI/bge-m3

# ----- PATHS (modify only if your directory structure differs) -----
CAPIQ_DATA_PATH=./data/capiq
KNOWLEDGE_BASE_PATH=./data/knowledge_base
CHROMADB_PATH=./chroma_db
Step 3: Create directory structure with placeholder files

Create these empty directories with .gitkeep files:

data/capiq/.gitkeep
data/capiq/precedent_transactions/.gitkeep
data/capiq/public_comps/.gitkeep
data/knowledge_base/.gitkeep
reports/.gitkeep
Step 4: Create data/README.md

# Data Directory

This folder contains the data sources for Project Veritas. Due to licensing and size constraints, the actual data files are NOT included in the repository.

## Setup Instructions

### Knowledge Base (Required)
Place finance/PE textbooks (PDF format) in `knowledge_base/`. Then run:
```bash
python scripts/rebuild_chromadb.py
This embeds all PDFs using BGE-M3 and stores them in ChromaDB locally.

Recommended books (you provide your own copies):

Investment Banking (Rosenbaum & Pearl)
Valuation (McKinsey / Koller)
Private Equity at Work (Cendrowski)
Financial Modeling & Valuation (Pignataro)
The Intelligent Investor (Graham)
Damodaran on Valuation
CapIQ Data (Optional — Enhances Output)
If you have S&P Capital IQ access, export:

Precedent Transactions → place in capiq/precedent_transactions/
Public Comps → place in capiq/public_comps/
See docs/CAPIQ_EXPORT_GUIDE.md for exact export settings.

Pre-built ChromaDB (Alternative)
If you don't want to build from scratch, download the pre-built vector store: [Link to HuggingFace Dataset — see Section 6] Extract to ./chroma_db/ in the project root.

**Step 5: Create `scripts/verify_setup.py`**

```python
"""
Project Veritas — Setup Verification
Run this first to check everything is configured correctly.
Usage: python scripts/verify_setup.py
"""
import sys
import os
from pathlib import Path

def check_python_version():
    v = sys.version_info
    if v.major >= 3 and v.minor >= 11:
        return True, f"Python {v.major}.{v.minor}.{v.micro}"
    return False, f"Python {v.major}.{v.minor} (need 3.11+)"

def check_packages():
    required = [
        'torch', 'transformers', 'FlagEmbedding', 'chromadb',
        'yfinance', 'pandas', 'openai', 'tavily', 'streamlit',
        'openpyxl', 'dotenv'
    ]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return len(missing) == 0, missing

def check_env_file():
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        return False, ".env file not found. Copy .env.example to .env"
    return True, str(env_path)

def check_api_keys():
    from dotenv import load_dotenv
    load_dotenv()
    issues = []
    nvidia = os.getenv('NVIDIA_API_KEY', '')
    tavily = os.getenv('TAVILY_API_KEY', '')
    if not nvidia or 'your-' in nvidia:
        issues.append("NVIDIA_API_KEY not set")
    if not tavily or 'your-' in tavily:
        issues.append("TAVILY_API_KEY not set")
    return len(issues) == 0, issues

def check_chromadb():
    chroma_path = Path(__file__).parent.parent / 'chroma_db'
    if not chroma_path.exists():
        return False, "ChromaDB not found. Run: python scripts/rebuild_chromadb.py"
    # Check if it has collections
    import chromadb
    client = chromadb.PersistentClient(path=str(chroma_path))
    collections = client.list_collections()
    if len(collections) == 0:
        return False, "ChromaDB exists but has no collections. Run rebuild script."
    total_docs = sum(c.count() for c in collections)
    return True, f"{len(collections)} collections, {total_docs} total chunks"

def check_bge_m3():
    cache_path = Path.home() / '.cache' / 'huggingface' / 'hub' / 'models--BAAI--bge-m3'
    if cache_path.exists():
        return True, "Cached locally"
    return False, "Not downloaded yet (will download on first run, ~4.5GB)"

def main():
    print("\n" + "="*60)
    print("  PROJECT VERITAS — Setup Verification")
    print("="*60 + "\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Required Packages", check_packages),
        ("Environment File", check_env_file),
        ("API Keys", check_api_keys),
        ("ChromaDB Vector Store", check_chromadb),
        ("BGE-M3 Embedding Model", check_bge_m3),
    ]
    
    all_pass = True
    for name, check_fn in checks:
        try:
            passed, detail = check_fn()
            status = "✅ PASS" if passed else "❌ FAIL"
            if not passed:
                all_pass = False
            print(f"  {status} | {name}")
            if isinstance(detail, list):
                for d in detail:
                    print(f"         → {d}")
            else:
                print(f"         → {detail}")
        except Exception as e:
            all_pass = False
            print(f"  ❌ ERROR | {name}")
            print(f"         → {str(e)}")
        print()
    
    print("="*60)
    if all_pass:
        print("  ✅ ALL CHECKS PASSED — Ready to run!")
        print("  Try: streamlit run app.py")
        print("  Or:  python test_full_pipeline.py AAPL")
    else:
        print("  ❌ SOME CHECKS FAILED — Fix issues above before running.")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
Step 6: Create scripts/rebuild_chromadb.py

"""
Project Veritas — ChromaDB Knowledge Base Rebuild
Processes all PDFs in data/knowledge_base/ and creates vector embeddings.

Usage: python scripts/rebuild_chromadb.py

Time: ~30-60 minutes on CPU for 40+ books
Disk: ~2-3GB for the vector store

This only needs to be run ONCE (or again if you add new books).
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("\n" + "="*60)
    print("  PROJECT VERITAS — ChromaDB Knowledge Base Rebuild")
    print("="*60)
    
    kb_path = project_root / 'data' / 'knowledge_base'
    chroma_path = project_root / 'chroma_db'
    
    # Find all PDFs
    pdfs = list(kb_path.glob('**/*.pdf'))
    if not pdfs:
        print(f"\n  ❌ No PDFs found in {kb_path}")
        print(f"  Place your finance textbooks (PDF format) in that directory.")
        print(f"  Then run this script again.")
        sys.exit(1)
    
    print(f"\n  Found {len(pdfs)} PDFs to process:")
    for p in pdfs[:10]:
        print(f"    - {p.name}")
    if len(pdfs) > 10:
        print(f"    ... and {len(pdfs)-10} more")
    
    print(f"\n  Output directory: {chroma_path}")
    print(f"  Embedding model: BAAI/bge-m3 (1024 dimensions)")
    print(f"\n  This will take 30-60 minutes on CPU. Starting...\n")
    
    # Import the existing embedding/chunking logic
    # CODEX: Import from wherever the existing rebuild logic lives
    # This might be in core/embeddings.py or a standalone script
    from core.embeddings import BGEM3Embedding
    from core.chromadb_manager import rebuild_all_collections
    
    # Run the rebuild
    rebuild_all_collections(
        pdf_directory=kb_path,
        chroma_path=chroma_path,
        embedding_function=BGEM3Embedding()
    )
    
    print("\n  ✅ Rebuild complete!")
    print(f"  Vector store saved to: {chroma_path}")
    print(f"  Run 'python scripts/verify_setup.py' to confirm.\n")

if __name__ == "__main__":
    main()
Step 7: Git Commands (Run in PowerShell)

# Navigate to project
cd C:\Users\Moosa\Downloads\Project_Veritas

# Initialize repository
git init

# Add .gitignore FIRST
git add .gitignore
git commit -m "Add .gitignore"

# Stage everything else
git add .

# CRITICAL: Verify nothing secret/large is staged
git status

# Look for any of these in the staged files (should NOT be there):
#   .env (your actual keys)
#   *.xlsx (CapIQ data)
#   *.pdf (books)
#   chroma_db/ (vector store)
#   .cache/ (model files)

# If something bad IS staged, remove it:
# git rm --cached path/to/bad/file
# git rm --cached -r chroma_db/

# Once clean, commit
git commit -m "Project Veritas v9.4 - Multi-agent PE due diligence system

- Multi-agent architecture: RAG, Data, Math, Debate, IC Decision
- Supports both bank (P/Book) and industrial (EV/EBITDA) valuation
- Live data from yfinance, CapIQ, Tavily
- BGE-M3 embeddings + ChromaDB for knowledge retrieval
- NVIDIA NIM API (Llama 3.3 70B) for agent intelligence
- Streamlit frontend with live agent progress
- HTML report export (investment bank design)
- Built for AMD Pervasive AI Hackathon 2026"

# Create GitHub repository:
# 1. Go to https://github.com/new
# 2. Repository name: Project-Veritas (or Project_Veritas)
# 3. Description: "Multi-agent AI system for PE-grade due diligence reports"
# 4. Set to PUBLIC
# 5. Do NOT initialize with README (you already have one)
# 6. Do NOT add .gitignore (you already have one)
# 7. Click "Create repository"
# 8. Copy the URL (e.g., https://github.com/YourUsername/Project-Veritas.git)

# Connect and push
git remote add origin https://github.com/YourUsername/Project-Veritas.git
git branch -M main
git push -u origin main

# Verify: Go to your GitHub repo URL in browser — files should be there
Step 8: After pushing, verify these are NOT on GitHub:

No .env file visible
No .xlsx files in data/capiq/
No .pdf files in data/knowledge_base/
No chroma_db/ folder
No .cache/ or model files
6. KNOWLEDGE BASE DISTRIBUTION (HUGGINGFACE)
What This Solves
Your ChromaDB vector store (~2-3GB) contains embedded chunks from 40+ books. Users can't easily rebuild this without having the same books. Hosting the pre-built database on HuggingFace lets users download and use it directly.

Step-by-Step: Upload to HuggingFace Datasets
Step 1: Create HuggingFace Account

Go to: https://huggingface.co/join
Create a free account
Go to: https://huggingface.co/settings/tokens
Create a new token (Write access) — save this token
Step 2: Install HuggingFace CLI

pip install huggingface_hub
Step 3: Login

huggingface-cli login
# Paste your token when prompted
Step 4: Create a Dataset Repository

# This creates a new dataset repo on HuggingFace
huggingface-cli repo create project-veritas-knowledge-base --type dataset
Step 5: Prepare the Upload

Your ChromaDB stores data in a local folder. You need to zip it:

# Navigate to project
cd C:\Users\Moosa\Downloads\Project_Veritas

# Zip the ChromaDB folder
Compress-Archive -Path .\chroma_db\* -DestinationPath .\chroma_db_export.zip
Step 6: Upload to HuggingFace

# Upload the zip file to your dataset repo
huggingface-cli upload YourUsername/project-veritas-knowledge-base chroma_db_export.zip . --repo-type dataset
Or use Python:

from huggingface_hub import HfApi
api = HfApi()
api.upload_file(
    path_or_fileobj="chroma_db_export.zip",
    path_in_repo="chroma_db_export.zip",
    repo_id="YourUsername/project-veritas-knowledge-base",
    repo_type="dataset"
)
Step 7: Create a README for the Dataset

Create a file called README.md in the upload:

---
license: mit
task_categories:
  - text-retrieval
language:
  - en
tags:
  - finance
  - private-equity
  - due-diligence
  - embeddings
  - bge-m3
---

# Project Veritas — Knowledge Base (ChromaDB)

Pre-built vector store for the Project Veritas PE due diligence system.

## Contents
- ~6,000 embedded text chunks from finance/PE textbooks
- Embedded using BAAI/bge-m3 (1024 dimensions)
- Stored in ChromaDB format

## Usage
1. Download `chroma_db_export.zip`
2. Extract to `./chroma_db/` in your Project Veritas directory
3. Run `python scripts/verify_setup.py` to confirm

## Built With
- Embedding Model: BAAI/bge-m3
- Vector Store: ChromaDB (persistent client)
- Chunk Size: 500 tokens, 50 token overlap
Step 8: Link From Your GitHub README

In your main project README, add:

### Quick Start: Pre-built Knowledge Base
Download the pre-built ChromaDB vector store (avoids needing to process PDFs yourself):

1. Download from [HuggingFace](https://huggingface.co/datasets/YourUsername/project-veritas-knowledge-base)
2. Extract `chroma_db_export.zip` to `./chroma_db/` in the project root
3. Run `python scripts/verify_setup.py` to confirm
Alternative: Upload ChromaDB Files Directly (Without Zip)
If ChromaDB uses SQLite internally, you can also upload the raw files:

# Upload entire directory
huggingface-cli upload YourUsername/project-veritas-knowledge-base ./chroma_db/ chroma_db/ --repo-type dataset
Users would then clone:

# Users download with:
git lfs install
git clone https://huggingface.co/datasets/YourUsername/project-veritas-knowledge-base
# Then copy/symlink chroma_db/ folder to project
What About the PDFs Themselves?
DO NOT upload the PDF books to HuggingFace or GitHub. They are copyrighted. Only upload the EMBEDDINGS (ChromaDB vectors), which are transformations of the text that cannot be reversed back into the original content. This is legally similar to how Google Books stores indices but not full texts.

The embeddings are numerical vectors (arrays of 1024 floats). They cannot be decoded back into readable text. This is the standard approach used by all RAG projects.

7. DEPLOYMENT OPTIONS
Option A: Streamlit Cloud (Free, Recommended for Demo)
Push repo to GitHub (public)
Go to: https://share.streamlit.io/
Click "New app"
Select your GitHub repo → main branch → app.py
In "Advanced settings" → "Secrets", add:
NVIDIA_API_KEY = "your-actual-key"
TAVILY_API_KEY = "your-actual-key"
Click "Deploy"
Limitations:

1GB memory limit (BGE-M3 needs ~2-3GB → may not work on free tier)
Cold starts take 60+ seconds
If memory is an issue: use a lighter embedding model for the deployed version, or pre-compute embeddings and load only the ChromaDB client
Workaround for memory: On Streamlit Cloud, instead of loading BGE-M3 at runtime, pre-compute all embeddings and store them in ChromaDB. At query time, use a lighter model (e.g., all-MiniLM-L6-v2 at 384 dimensions) or call an API-based embedding service.

Option B: Local Demo (For Video Recording)
cd C:\Users\Moosa\Downloads\Project_Veritas
streamlit run app.py
# Opens http://localhost:8501 in browser
# Record screen with OBS or Windows Game Bar (Win+G)
This is the most reliable option for the hackathon demo video. No deployment issues, full memory available, fast response times.

Option C: HuggingFace Spaces (Alternative to Streamlit Cloud)
HuggingFace Spaces supports Streamlit apps with more memory (up to 16GB on free CPU):

Go to: https://huggingface.co/spaces
Create new Space → select "Streamlit"
Upload your code
Add secrets in Space settings
This might be better than Streamlit Cloud due to higher memory limits.

8. COMPLETE FILE LIST (What Should Exist After All Fixes)
Project_Veritas/
├── README.md                              # Project overview, setup, demo
├── requirements.txt                       # All Python dependencies  
├── .env.example                           # API key template
├── .gitignore                             # Excludes data/secrets/models
├── app.py                                 # Streamlit frontend (main entry)
├── pipeline_wrapper.py                    # Adapts backend for frontend
├── report_generator.py                    # HTML report export
├── test_full_pipeline.py                  # Terminal-based test (existing, keep working)
│
├── config/
│   ├── __init__.py
│   ├── settings.py                        # Loads .env, validates config
│   └── sector_mappings.py                 # Industry → sector → file mappings
│
├── agents/                                # Existing agent modules
│   ├── __init__.py
│   ├── rag_agent.py                       # Step 1: ChromaDB retrieval
│   ├── data_agent.py                      # Step 2: yfinance + CapIQ
│   ├── math_agent.py                      # Step 3: Valuation computation
│   ├── debate_agent.py                    # Step 4: IC debate
│   ├── ic_agent.py                        # Step 5: Decision
│   └── forensic_agent.py                  # Forensic scoring
│
├── core/                                  # Shared utilities
│   ├── __init__.py
│   ├── embeddings.py                      # BGE-M3 wrapper class
│   ├── chromadb_manager.py                # ChromaDB operations
│   ├── report_renderer.py                 # Terminal text report formatter
│   └── utils.py                           # fmt_number(), sector routing, etc.
│
├── data/
│   ├── README.md                          # Setup instructions for data
│   ├── capiq/
│   │   ├── .gitkeep
│   │   ├── precedent_transactions/.gitkeep
│   │   └── public_comps/.gitkeep
│   └── knowledge_base/
│       └── .gitkeep
│
├── scripts/
│   ├── rebuild_chromadb.py                # Build vector store from PDFs
│   ├── verify_setup.py                    # First-run validation
│   └── clean_capiq_transactions.py        # Clean raw CapIQ exports
│
├── docs/
│   ├── ARCHITECTURE.md                    # System design documentation
│   ├── CAPIQ_EXPORT_GUIDE.md             # How to export from CapIQ
│   └── KNOWLEDGE_BASE_GUIDE.md           # Which books, how to structure
│
├── reports/                               # Generated reports land here
│   └── .gitkeep
│
└── tests/
    └── test_pipeline_unit.py              # Unit tests for key functions
9. TESTING CHECKLIST (Before Submission)
Run these checks after all fixes are implemented:

Terminal Tests
# Industrial company (Consumer Staples)
python test_full_pipeline.py PG

# Bank (Capital Markets)  
python test_full_pipeline.py MS

# Credit Services (tests bank-mode peer selection)
python test_full_pipeline.py AXP

# Tech (tests currency conversion for non-US)
python test_full_pipeline.py AAPL

# Chinese company (tests currency conversion)
python test_full_pipeline.py BABA
For Each Test, Verify:
 No contradictory verdicts in report
 Numbers are formatted (no raw decimals like 34.419%)
 "What Must Go Right / Wrong" contains sentences, not data points
 Entry strategy logic matches (below fair value = BUY, above = WAIT)
 Forensic sub-scores sum to total
 Sensitivity table center = base case value (±1%)
 No JSON/Python list artifacts in report text
 CoE/WACC is same across multiple runs of same ticker
 Precedent transactions section shows deals (>0) or gracefully states unavailable
Streamlit Tests
streamlit run app.py
 Page loads without error
 Entering ticker and clicking Run starts analysis
 Progress indicators update for each agent
 Results display correctly after completion
 Download buttons produce valid HTML/text files
 Uploaded PDF gets incorporated (test with any finance PDF)
 Error handling: enter invalid ticker → shows friendly error
GitHub Verification
 .env is NOT in the repository
 No .xlsx files visible
 No .pdf files visible
 No chroma_db/ folder
 README renders properly
 .env.example is present with placeholder keys
 scripts/verify_setup.py works after fresh clone
END OF SPECIFICATION
This document is the complete blueprint for finalizing Project Veritas. Priority order:

Backend fixes (Section 2) — 2-3 hours
Pipeline wrapper (Section 4) — 1-2 hours
Streamlit app (Section 3) — 3-4 hours
HTML report generator (Section 3) — 2 hours
GitHub push (Section 5) — 30 minutes
HuggingFace upload (Section 6) — 30 minutes
Testing (Section 9) — 1-2 hours
Demo video recording — 1 hour
Total estimated time: 12-16 hours across remaining days.

