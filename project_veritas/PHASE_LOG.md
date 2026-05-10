# Project Veritas -- Phase Log

## Phase 0: Math Validation (Complete)

### What was built
- **comparable_company.py** -- EV/EBITDA and EV/Revenue comps engine. Percentile methodology per Rosenbaum & Pearl.
- **dcf_engine.py** -- 5-year FCF projection with McKinsey Value Driver terminal value and sensitivity analysis.
- **lbo_engine.py** -- Entry structure, debt schedule, three-scenario returns, value creation bridge.

### Architect decisions made (Moosa -- System Architect)
- Chose Mankind Pharma as primary test case: real PE history (Carlyle), active sector, verifiable public data
- Chose to KEEP Vishal Mega Mart failure case: demonstrates peer selection judgment over blind model execution
- Tiered NA handling: fill -> default -> flag -> never drop blindly
- Web search stubbed as Phase 2 priority: local data first, hallucination never
- TEV reconstruction from Market Cap + Debt - Cash when CapIQ direct TEV column was empty: analyst judgment applied

### Key findings
- Mankind Pharma football field: Rs 18,932 -- Rs 29,463 Cr
- LBO base: 2.69x MOIC / 21.9% IRR (clears PE hurdle)
- Value creation: 78% from EBITDA growth (high quality signal)
- Known gap: DCF RONIC = WACC (conservative). Phase 1 fix: connect Damodaran roeIndia.xlsx for sector ROE lookup.

### Sources used
- Rosenbaum & Pearl, Investment Banking (Wiley)
- McKinsey & Company, Valuation 6th Ed.
- Damodaran, Investment Valuation 3rd Ed.
- Reinard, PE Value Creation Analysis Vol.I
- Zeisberger, Mastering Private Equity
- CapIQ: india_healthcare_peers.xlsx (public comps)

---
## Phase 1: Valuation Agent API Wrapper (In Progress)

### What was built
- **valuation_agent.py** -- Agent brain with dual execution modes:
  - **Live mode**: Claude API tool-use loop (requires ANTHROPIC_API_KEY)
  - **Local simulation**: Deterministic tool execution for validation
- **run_agent.py** -- Runner script with Mankind Pharma brief
- **RONIC lookup function** -- Reads Damodaran roeIndia.xls, fuzzy-matches
  sector name to industry row, returns sector ROE as RONIC

### Architect decisions made (Moosa -- System Architect)
- Chose Claude over GPT-4 for tool-use: native structured tool calling,
  no LangChain dependency needed
- Built dual-mode architecture: local simulation proves the math works
  without API cost; live mode adds Claude's judgment layer
- RONIC lookup from Damodaran roeIndia.xls before DCF runs --
  this is the fix for Phase 0's 56% convergence spread
- Fuzzy matching for sector names: user says "Pharmaceuticals",
  Damodaran labels it "Drugs (Pharmaceutical)" -- SequenceMatcher
  handles the mismatch

### Key findings
- Damodaran Drugs (Pharmaceutical) ROE = 15.6%
- Phase 0 DCF with RONIC = WACC (11.5%): Rs 18,932 Cr
- Phase 1 DCF with RONIC = 15.6%: DCF EV increases, closing gap
- Expected convergence improvement: 56% -> ~25-30%

### Sources used
- Damodaran roeIndia.xls (Industry Averages sheet, col 2)
- Anthropic Claude API (tool-use pattern, model: claude-opus-4-5)
- Tavily API (web search fallback, restricted domains)
- yfinance (Indian market data fallback)

### yfinance integration (Phase 1 addition)
- Added yfinance as data source priority #4 for Indian market data.
- Provides real-time market cap, EV/EBITDA, beta, and price data for NSE/BSE listed companies.
- Ticker format: COMPANY.NS (NSE) or COMPANY.BO (BSE).

### Architect decision (Moosa)
- Chose yfinance (12k+ stars, actively maintained Python library) over third-party Vercel API wrapper (single-maintainer, uptime risk).
- Same underlying Yahoo Finance data, zero dependency on external deployment stability.
- Alpha Vantage removed (focused on global; poor coverage for Indian .BSE/.NSE fundamentals).
- yfinance fills the live fundamentals gap between static CapIQ exports and last-resort Tavily search.

### Web search fallback (Phase 1 addition)
- Web search fallback implemented via Tavily API.
- Permitted domains: Damodaran (stern.nyu.edu), BSE (bseindia.com), SEBI (sebi.gov.in), RBI (rbi.org.in), ICRA (icra.in), CRISIL (crisil.com).
- Priority: Local → CapIQ → Web → Never hallucinate.
- Architect decision (Moosa): Web search reads full page content (2000 chars per source, 5 sources max) from verified domains. Added NSE, Screener, Moneycontrol as additional verified Indian financial sources. Authentication-gated content (BSE login, SEBI EDGAR restricted filings) remains inaccessible — flagged as known limitation.
- Data source provenance logged for every tool call: Damodaran ✓ / CapIQ ✓ / Web fallback ✓ / Default ⚠

### Architect decision (Moosa): 
Local simulation removed.
Live Claude API is the only execution mode.
Rationale: Simulation masked real agent behaviour 
and produced misleading peer selection results.
API credits confirmed working — simulation no longer 
needed.

## Phase 3: Multi-Agent Orchestration (In Progress)
 - **Status**: Commenced development of the 5-agent orchestrator system.
 - **Design Pattern**: Mailbox Protocol (Peer-to-Peer data passing via a shared deal_context object).
 - **Execution Flow**: Strictly sequential (Biz Intel -> Forensics -> Market Intel -> Management -> Valuation -> Synthesis) to ensure data dependencies (e.g., Valuation requires Adjusted EBITDA from Forensics) are respected.
 - **Agent Built**: 
     - Orchestrator skeleton (Pending logic implementation).
     - Agent 1 (Business Intelligence): COMPLETE
       - Live tested on Mankind Pharma
       - yfinance market data: working
       - Tavily web search: working  
       - ChromaDB india_market_context: working
       - Analyst sentiment: working
       - Orchestrator wiring: confirmed
       - deal_context populated correctly
     - Agent 2 (Financial Forensics): COMPLETE — Tavily verified
       Test results on Mankind Pharma:
         Forensic Score: 84/100 (MEDIUM reliability)
         PASS: 4 | WARN: 1 | FAIL: 0 | INSUFFICIENT: 3
         yfinance: working (revenue ₹13,914 Cr confirmed)
         Tavily filing search: 4 searches completed
         Score reliability: MEDIUM — 3 data gaps flagged
         Debt coverage: WARN (proxied interest at 9%)
         Receivables/DSO: INSUFFICIENT — requires MCA filing
         Live Claude test: pending API credit top-up

       Architect decision (Moosa): INSUFFICIENT_DATA 
       preferred over false PASS when data unavailable.
       Agent correctly identifies which gaps require 
       manual retrieval from annual report or MCA filing
       before IC presentation.
       
     - Agent 3 (Market Intelligence): BUILT
       - Sector landscape: Tavily (4 searches)
       - Precedent transactions: CapIQ files
       - Competitive position: Damodaran marginIndia
       - Implied entry multiple: passed to deal_context
       - Live test: pending API credit top-up