import streamlit as st
import os
import sys
import logging
import warnings

# --- SILENCE TRANSFORMERS NOISE ---
# This stops Streamlit from scanning every single model in the transformers library
logging.getLogger("transformers").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from pathlib import Path
import time
import base64

# UI Config
st.set_page_config(
    page_title="Project Veritas | Institutional DD",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Look & Animations
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        * { font-family: 'Inter', sans-serif; }
        
        .main { background-color: #0f172a; color: #f8fafc; }
        
        /* Premium Pipeline CSS */
        .pipeline-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 40px 20px;
            background: rgba(30, 41, 59, 0.5);
            border-radius: 16px;
            border: 1px solid #334155;
            margin-bottom: 30px;
        }
        
        .agent-node {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
            z-index: 2;
            flex: 1;
        }
        
        .node-icon {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #1e293b;
            border: 2px solid #334155;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 20px;
            transition: all 0.5s ease;
            box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
        }
        
        .node-icon.active {
            background: #1d4ed8;
            border-color: #60a5fa;
            box-shadow: 0 0 20px 5px rgba(59, 130, 246, 0.4);
            transform: scale(1.2);
        }
        
        .node-icon.completed {
            background: #059669;
            border-color: #34d399;
            color: white;
        }
        
        .node-label {
            margin-top: 12px;
            font-size: 12px;
            font-weight: 600;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .node-label.active { color: #f8fafc; }
        
        .pipeline-connector {
            height: 2px;
            background: #334155;
            flex-grow: 1;
            margin: 0 -25px;
            margin-top: -25px;
            position: relative;
            z-index: 1;
        }
        
        .connector-progress {
            height: 100%;
            background: linear-gradient(90deg, #3b82f6, #60a5fa);
            width: 0%;
            transition: width 1s ease;
        }
        
        /* Baton/Flame Animation */
        .flame {
            position: absolute;
            top: -15px;
            font-size: 24px;
            animation: flicker 0.5s infinite alternate;
            z-index: 3;
            transition: all 1s ease;
        }
        
        @keyframes flicker {
            from { transform: translateY(0) scale(1); opacity: 0.8; }
            to { transform: translateY(-5px) scale(1.1); opacity: 1; }
        }

        .stButton>button { 
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white; border-radius: 8px; 
            border: none; padding: 12px 28px; font-weight: 700;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            transition: all 0.2s;
        }
        .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2); }
        
        .stMetric { background: #1e293b; padding: 15px; border-radius: 12px; border: 1px solid #334155; }

        /* Prettify RAG Context */
        .rag-source {
            background: #0f172a;
            padding: 15px;
            border-left: 4px solid #3b82f6;
            margin: 10px 0;
            font-size: 0.9rem;
            color: #cbd5e1;
            border-radius: 0 8px 8px 0;
        }
    </style>
""", unsafe_allow_html=True)

# --- PIPELINE VISUALIZATION COMPONENT ---
def render_agent_pipeline(current_step):
    steps = [
        {"id": "RAG_RETRIEVAL", "label": "RAG", "icon": "📚"},
        {"id": "DATA_PROCESS", "label": "Data", "icon": "📁"},
        {"id": "MATH_AGENT", "label": "Math", "icon": "🧮"},
        {"id": "INTEL_AGENT", "label": "Intel", "icon": "🌐"},
        {"id": "DEBATE", "label": "Debate", "icon": "⚔️"},
        {"id": "IC_DECISION", "label": "Decision", "icon": "🏛️"},
        {"id": "FINALIZING", "label": "Memo", "icon": "📄"}
    ]
    
    # Calculate step index
    step_ids = [s["id"] for s in steps]
    try:
        active_idx = step_ids.index(current_step) if current_step in step_ids else -1
    except:
        active_idx = -1
        
    if current_step == "COMPLETE": active_idx = len(steps)
    
    # We use a standalone HTML component to avoid Streamlit's "Magic" text formatting
    pipeline_html = f"""
    <style>
        .pipeline-container {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            background: #1e293b;
            border-radius: 12px;
            border: 1px solid #334155;
            font-family: sans-serif;
            color: #f8fafc;
        }}
        .agent-node {{
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
        }}
        .node-icon {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #0f172a;
            border: 2px solid #334155;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 18px;
            transition: all 0.3s;
        }}
        .node-icon.active {{
            background: #1d4ed8;
            border-color: #60a5fa;
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.5);
            transform: scale(1.1);
        }}
        .node-icon.completed {{
            background: #059669;
            border-color: #34d399;
        }}
        .node-label {{
            margin-top: 8px;
            font-size: 10px;
            font-weight: 600;
            color: #94a3b8;
            text-transform: uppercase;
        }}
        .node-label.active {{ color: #f8fafc; }}
        .connector {{
            height: 2px;
            background: #334155;
            flex-grow: 1;
            margin-top: -18px;
        }}
        .progress {{
            height: 100%;
            background: #3b82f6;
            width: 0%;
        }}
    </style>
    <div class="pipeline-container">
    """
    
    for i, step in enumerate(steps):
        status = ""
        if i < active_idx: status = "completed"
        elif i == active_idx: status = "active"
        
        icon = step['icon'] if status != "completed" else "✅"
        pipeline_html += f"""
        <div class="agent-node">
            <div class="node-icon {status}">{icon}</div>
            <div class="node-label {'active' if status == 'active' else ''}">{step['label']}</div>
        </div>
        """
        if i < len(steps) - 1:
            w = "100%" if i < active_idx else ("50%" if i == active_idx else "0%")
            pipeline_html += f'<div class="connector"><div class="progress" style="width: {w}"></div></div>'
            
    pipeline_html += "</div>"
    # Future-proof HTML rendering (replaces deprecated components.html)
    try:
        st.html(pipeline_html)
    except AttributeError:
        st.markdown(pipeline_html, unsafe_allow_html=True)

# App Title
st.title("⚖️ Project Veritas")
st.subheader("Institutional-Grade Multi-Agent Due Diligence Engine")

# --- INITIALIZATION ---
@st.cache_resource
def get_pipeline():
    from pipeline_wrapper import VeritasPipeline
    return VeritasPipeline()

# Sidebar
with st.sidebar:
    st.header("🔑 Credentials")
    
    # Check st.secrets (Streamlit Cloud best practice)
    s_nv_key = st.secrets.get("NVIDIA_API_KEY") or st.secrets.get("FIREWORKS_API_KEY")
    s_tv_key = st.secrets.get("TAVILY_API_KEY")
    
    if s_nv_key:
        os.environ["NVIDIA_API_KEY"] = s_nv_key
        if s_nv_key.startswith("fw_"):
            os.environ["FIREWORKS_API_KEY"] = s_nv_key
        st.success("LLM Key loaded from Secrets")
        ui_nv_key = s_nv_key
    else:
        ui_nv_key = st.text_input("NVIDIA / Fireworks API Key", type="password", help="Enter your nvapi- or fw_ key")
        if ui_nv_key:
            os.environ["NVIDIA_API_KEY"] = ui_nv_key
            if ui_nv_key.startswith("fw_"):
                os.environ["FIREWORKS_API_KEY"] = ui_nv_key

    if s_tv_key:
        os.environ["TAVILY_API_KEY"] = s_tv_key
        st.success("Search Key loaded from Secrets")
        ui_tv_key = s_tv_key
    else:
        ui_tv_key = st.text_input("Tavily API Key", type="password", help="Enter your tvly- key")
        if ui_tv_key:
            os.environ["TAVILY_API_KEY"] = ui_tv_key
    
    st.header("System Status")
    # We check os.environ directly to confirm the backend sees them
    nv_active = "NVIDIA_API_KEY" in os.environ or "FIREWORKS_API_KEY" in os.environ
    tv_active = "TAVILY_API_KEY" in os.environ
    
    if nv_active: 
        provider = "Fireworks" if os.environ.get("NVIDIA_API_KEY", "").startswith("fw_") else "NVIDIA"
        st.success(f"LLM: {provider} Active")
    else: 
        st.warning("LLM: Disconnected")
    
    if tv_active: st.success("Search: Tavily Active")
    else: st.warning("Search: Disconnected")
    
    st.divider()
    st.header("Analysis Parameters")
    ticker = st.text_input("Ticker Symbol", value="AXP").upper()
    
    # Auto-detect sector from yfinance and show it (Fix requested)
    sector_default_idx = 0
    sectors = [
        "Financial Services", "Technology", "Healthcare", "Industrials", 
        "Consumer Cyclical", "Energy", "Communication Services", "Consumer Defensive",
        "Utilities", "Real Estate", "Basic Materials"
    ]
    # Auto-detect sector from yfinance and show it
    # Let user override if needed
    if ticker:
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            auto_sector = info.get('sector', 'Unknown')
            st.caption(f"Auto-detected sector: {auto_sector}")
            sector_default = auto_sector
        except:
            sector_default = "Industrials"
    else:
        sector_default = "Technology"

    sector = st.selectbox("Industry Sector", sectors, index=sectors.index(sector_default) if sector_default in sectors else 0)
    
    if st.button("Reset Session & Model"):
        st.cache_resource.clear()
        st.session_state.results = None
        st.session_state.init_complete = False
        st.rerun()

    with st.sidebar.expander("⚡ Infrastructure Metrics", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("LLM Provider", "Fireworks AI")
            st.metric("Hardware", "AMD GPU")
        with col2:
            st.metric("Model", "Llama 3.3 70B")
            st.metric("Embeddings", "BGE-M3 1024d")
        st.metric("Knowledge Base", "~6,000 chunks")
        st.metric("Agents", "6 specialized")

    st.sidebar.warning("""
⚠️ DISCLAIMER

Project Veritas is a research and screening tool 
for educational purposes. 

Outputs are algorithmically generated and have NOT 
been verified by a licensed financial analyst. 
Do not make investment decisions based on this output.

This tool is a demonstration of multi-agent AI 
applied to financial analysis workflows.
""")

    st.sidebar.success("🔴 AMD GPU Inference Active")
    st.sidebar.caption(
        "Powered by Fireworks AI serverless GPU infrastructure\n"
        "Model: Llama 3.3 70B Instruct\n"
        "Hardware: AMD Instinct GPUs"
    )

# Pipeline State
if "results" not in st.session_state:
    st.session_state.results = None
if "init_complete" not in st.session_state:
    st.session_state.init_complete = False
if "error_log" not in st.session_state:
    st.session_state.error_log = None
if "current_step" not in st.session_state:
    st.session_state.current_step = None
if "status_msg" not in st.session_state:
    st.session_state.status_msg = "Ready for analysis."
if "report_path" not in st.session_state:
    st.session_state.report_path = None

# Initialization Phase
if not st.session_state.init_complete:
    if not (nv_active and tv_active):
        st.warning("Please provide API keys in the sidebar to initialize the engine.")
        st.stop()
        
    with st.status("Initializing Institutional Engine (Loading BGE-M3 Model)...", expanded=True) as status:
        try:
            pipeline = get_pipeline()
            st.session_state.init_complete = True
            status.update(label="Engine Ready!", state="complete", expanded=False)
        except Exception as e:
            st.error(f"Initialization Failed: {e}")
            st.stop()

# Progress Tracker Area
pipeline_placeholder = st.empty()
status_placeholder = st.empty()

def progress_callback(step, message):
    st.session_state.current_step = step
    st.session_state.status_msg = message
    with pipeline_placeholder.container():
        render_agent_pipeline(step)
    with status_placeholder:
        st.info(f"**Current Phase:** {message}")

# Action
if st.button("Initialize Deep Analysis", type="primary"):
    if not (nv_active and tv_active):
        st.error("API Keys missing. Enter them in the sidebar.")
    else:
        st.session_state.results = None
        st.session_state.error_log = None
        st.session_state.current_step = "RAG_RETRIEVAL"
        st.session_state.status_msg = "Initializing knowledge retrieval..."
        
        from report_generator import ReportGenerator
        
        pipeline = get_pipeline()
        pipeline.progress_callback = progress_callback
        
        try:
            results = pipeline.run(ticker, sector)
            if results:
                st.session_state.results = results
                gen = ReportGenerator()
                report_path = gen.generate_html(results)
                st.session_state.report_path = report_path
                st.session_state.current_step = "COMPLETE"
                with pipeline_placeholder: render_agent_pipeline("COMPLETE")
            else:
                st.error("Pipeline returned no results. Check backend logs.")
        except Exception as e:
            st.session_state.error_log = str(e)
            st.error(f"Critical Pipeline Error: {e}")

# If not running, show initial state
if not st.session_state.results and st.session_state.current_step is None:
    with pipeline_placeholder:
        render_agent_pipeline(None)

if st.session_state.error_log:
    with st.expander("Debug Error Details"):
        st.code(st.session_state.error_log)

# Display Results
if st.session_state.results:
    res = st.session_state.results
    verdict = res["final_verdict"]
    context = res["deal_context"]
    
    # Summary Header
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Final Verdict", verdict["decision"])
    with col2: st.metric("Fair Value Price", f"${(verdict.get('fair_price') or 0):,.2f}", delta=f"{(verdict.get('implied_return_pct') or 0):+.1f}%")
    with col3: st.metric("Forensic Score", f"{(context.get('forensics', {}).get('forensic_score') or 0)}/100")

    # Data Quality Flags
    data_quality_flags = res.get('data_quality_flags', [])
    if data_quality_flags:
        st.caption(f"⚠️ Data quality notes: " + " | ".join(data_quality_flags[:3]))

    st.divider()
    
    tabs = st.tabs([
        "🎯 Decision Rationale", "⚔️ Agent Debate", "🧮 Math Detail", 
        "🌐 Business Intel", "📚 Knowledge Base"
    ])
    
    with tabs[0]:
        st.write("### IC Final Reasoning")
        st.info("\n".join([f"• {r}" for r in verdict.get("reasoning", [])]))
        
        st.write("### Critical Risks")
        for r in verdict.get("risks", []): 
            st.markdown(f"⚠️ **{r}**")
            
    with tabs[1]:
        st.write("### Bull vs Bear Debate Transcript")
        debate_res = res.get("debate_results", {})
        transcript = debate_res.get("debate_transcript", [])
        for entry in transcript:
            role_icon = "📈" if entry["role"] == "DEAL_CHAMPION" else "📉"
            with st.expander(f"{role_icon} {entry['role']} - {entry.get('headline', 'Argument')} (Conviction: {entry.get('conviction_score', 5)}/10)", expanded=True):
                st.write(entry.get("argument", "No content"))
                
    with tabs[2]:
        st.write("### Valuation & Mathematical Rationale")
        rationale = context.get("forensics", {}).get("math_agent_rationale", "No math data.")
        st.markdown(rationale)
        
        f_comm = context.get("forensics", {}).get("forensic_commentary", {})
        if f_comm:
            st.info(f"**Forensic Note:** {f_comm.get('cash_conversion', '')} | {f_comm.get('margin_safety', '')}")

        with st.expander("🔍 View Detailed Forensic Decomposition"):
            decomp = context.get("forensics", {}).get("forensic_decomposition", {})
            st.table([{"Factor": k.replace('_', ' ').title(), "Value": v} for k, v in decomp.items()])
        
    with tabs[3]:
        st.write("### Competitive Landscape & Market TAM")
        intel = context.get("market_intel", {})
        colA, colB = st.columns(2)
        with colA:
            st.subheader("Moat Analysis")
            st.write(intel.get("competitive_moat", "N/A"))
        with colB:
            st.subheader("TAM/SAM/SOM")
            st.write(intel.get("tam_sam_som", "N/A"))
        
        st.divider()
        st.write("### Management & Governance Quality")
        mgmt = context.get("management", {})
        ma, mb, mc = st.columns(3)
        decomp = mgmt.get("management_decomposition", {})
        ma.metric("Vision", f"{decomp.get('vision', 70)}%")
        mb.metric("Execution", f"{decomp.get('execution', 70)}%")
        mc.metric("Governance", f"{decomp.get('governance', 70)}%")
        
        if context.get("forensics", {}).get("red_flags"):
            st.error("### Forensic Red Flags Detected")
            for flag in context["forensics"]["red_flags"]:
                st.write(f"🚩 {flag}")

    with tabs[4]:
        st.write("### RAG Knowledge Retrieval")
        
        rag_data = context.get('rag', {})
        chunks = rag_data.get('chunks', [])
        
        if chunks:
            st.success(
                f"Retrieved {len(chunks)} relevant passages "
                f"from {len(set(c['source'] for c in chunks))} "
                f"sources"
            )
            
            for chunk in chunks[:5]:
                with st.expander(
                    f"📖 {chunk['source']} "
                    f"(relevance: {chunk['relevance']:.0%})"
                ):
                    st.markdown(f"**Query that found this:**")
                    st.caption(chunk.get('query_used',''))
                    st.markdown("**Retrieved passage:**")
                    st.markdown(f"> {chunk['text']}")
        else:
            st.error(
                "No knowledge base passages retrieved. "
                "Check that ChromaDB is loading correctly."
            )
            
            # Show diagnostic info
            st.code(f"""
Debugging steps:
1. Run: py -c "import chromadb; c = chromadb.PersistentClient('project_veritas/memory/chroma_db'); [print(col.name, col.count()) for col in c.list_collections()]"
2. Verify collections exist and have >0 chunks
3. Check chroma_db path in config matches actual location
            """)
                
    # Download Report
    if st.session_state.report_path:
        with open(st.session_state.report_path, "rb") as f:
            st.download_button(
                label="📥 Download Institutional Investment Memo (HTML)",
                data=f,
                file_name=Path(st.session_state.report_path).name,
                mime="text/html",
                use_container_width=True
            )

st.divider()
with st.expander("⚡ Infrastructure Metrics"):
    colI1, colI2, colI3 = st.columns(3)
    with colI1:
        st.metric("LLM Provider", "Fireworks AI")
        st.metric("Hardware", "AMD GPU")
    with colI2:
        st.metric("Model", "Llama 3.3 70B")
        st.metric("Embeddings", "BGE-M3 1024d")
    with colI3:
        st.metric("Knowledge Base", "~6,000 chunks")
        st.metric("Agents", "6 specialized")
