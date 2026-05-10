PS C:\Users\Moosa\Downloads\Project_Veritas> python -u test_full_pipeline.py MS      

======================================================================
  PROJECT VERITAS — Full Pipeline Test (LIVE DATA)
  Target: MS
  LLM Backend: NVIDIA NIM API
======================================================================

============================================================
  STEP 1: Dynamic ChromaDB RAG Retrieval
============================================================
Loading BGE-M3 model (BAAI/bge-m3)...
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
Fetching 30 files: 100%|███████████████████████████████████████████████████████████████████████████| 30/30 [00:00<00:00, 255231.48it/s]
Loading weights: 100%|██████████████████████████████████████████████████████████████████████████████| 391/391 [00:00<00:00, 647.32it/s] 
BGE-M3 loaded. Embedding dimension: 1024                                                               | 5/391 [00:00<00:41,  9.31it/s]
pre tokenize: 100%|█████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00, 202.29it/s]
Inference Embeddings: 100%|██████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00, 11.36it/s]
  Query: 'How to value a Capital Markets company with high S...'                                                 | 0/1 [00:00<?, ?it/s]
pre tokenize: 100%|████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00, 1634.57it/s]
Inference Embeddings: 100%|██████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00,  9.76it/s] 
  Query: 'Common accounting red flags and forensic adjustmen...'█████████████████████████████████████████| 1/1 [00:00<00:00,  9.81it/s]
pre tokenize: 100%|████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00, 1466.54it/s]
Inference Embeddings: 100%|██████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00, 11.06it/s] 
  Query: 'What are the terminal growth rate (TGR) assumption...'                                                 | 0/1 [00:00<?, ?it/s]
  RAG STATUS: OK

============================================================
  STEP 2: Pulling LIVE Data (yfinance + CapIQ)
============================================================
    [FIX 7] BS Override: Net Debt $289,228M (vs EV-derived $-72,945M)

  --------------------------------------------------
  DATA VALIDATION REPORT
  --------------------------------------------------
  [PASS] Revenue: $68,773M
  [PASS] Growth Rate: 16.3%
  [PASS] P/S Ratio: P/S of 4.4x
  [WARN] FCF Margin: -5.7% — negative FCF, verify capex cycle
  Confidence: HIGH

Download complete: : 0.00B [00:04, ?B/s]
    [FIX 7] BS Override: Net Debt $289,228M (vs EV-derived $-72,945M)
    [PEERS] Starting robust discovery for MS...
    [FIX 7] BS Override: Net Debt $221,891M (vs EV-derived $-277,019M)
    [FIX 5] SBC suspiciously low for Large Cap. Applying 0.5% Rev Floor: $934.7M
    [FIX 7] BS Override: Net Debt $156,644M (vs EV-derived $-241,096M)
    [FIX 7] BS Override: Net Debt $126,585M (vs EV-derived $-20,302M)
    [FIX 5] SBC suspiciously low for Large Cap. Applying 0.5% Rev Floor: $425.1M
    [FIX 7] BS Override: Net Debt $18,126M (vs EV-derived $-561,916M)
    [FIX 5] SBC suspiciously low for Large Cap. Applying 0.5% Rev Floor: $423.7M
    [FIX 5] SBC suspiciously low for Large Cap. Applying 0.5% Rev Floor: $72.4M
    [FIX 7] BS Override: Net Debt $-102,399M (vs EV-derived $0M)
    [FIX 7] BS Override: Net Debt $-94,371M (vs EV-derived $-161,469M)
    [FIX 7] BS Override: Net Debt $221,891M (vs EV-derived $-277,019M)
    [FIX 5] SBC suspiciously low for Large Cap. Applying 0.5% Rev Floor: $934.7M
    [FIX 7] BS Override: Net Debt $156,644M (vs EV-derived $-241,096M)
    [FIX 7] BS Override: Net Debt $126,585M (vs EV-derived $-20,302M)
    [FIX 5] SBC suspiciously low for Large Cap. Applying 0.5% Rev Floor: $425.1M
    [FIX 7] BS Override: Net Debt $18,126M (vs EV-derived $-561,916M)
    [FIX 5] SBC suspiciously low for Large Cap. Applying 0.5% Rev Floor: $423.7M
    [FIX 5] SBC suspiciously low for Large Cap. Applying 0.5% Rev Floor: $72.4M
    [FIX 7] BS Override: Net Debt $-102,399M (vs EV-derived $0M)
    [FIX 7] BS Override: Net Debt $-94,371M (vs EV-derived $-161,469M)
    [PEERS] Step 5 Fallback: Insufficient peers (0). Checking Fallback Map...
    [FIX 7] BS Override: Net Debt $-15,079M (vs EV-derived $-52,350M)
    [FIX 7] BS Override: Net Debt $221,891M (vs EV-derived $-277,019M)
    [PEERS] Step 6 Fallback: Still insufficient (0). Broadening GICS...
    [CRITICAL] Unable to establish peer set for MS. Valuation unreliable. Manual peer input required.

============================================================
  STEP 3: Triggering RAG Math Agent
============================================================
Loading BGE-M3 model (BAAI/bge-m3)...
Fetching 30 files: 100%|███████████████████████████████████████████████████████████████████████████| 30/30 [00:00<00:00, 433893.52it/s]
Loading weights: 100%|██████████████████████████████████████████████████████████████████████████████| 391/391 [00:00<00:00, 405.79it/s] 
BGE-M3 loaded. Embedding dimension: 1024███████████████████████████████████████████▋                | 309/391 [00:00<00:00, 588.30it/s]
pre tokenize: 100%|█████████████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00, 268.02it/s]
Inference Embeddings: 100%|██████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00,  7.15it/s]
Download complete: : 0.00B [00:14, ?B/s]█████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00,  7.19it/s]
    [TAVILY] Enriching MS business intel...

  Final Deal Context Built for MS
    - Fair Multiple: 10.0x
    - Forensic Score: 75/100
    - Precedents Found: 0

============================================================
  STEP 4: Multi-Agent Investment Committee Debate
============================================================
  LLM: NVIDIA NIM (meta/llama-3.3-70b-instruct)

  --- Round 1/2 ---
  [DEAL CHAMPION] Arguing...
    Headline: Invest in MS
    Conviction: 8/10
  [RISK PARTNER] Rebutting...
    Headline: MS Overvalued
    Conviction: 8/10

  --- Round 2/2 ---
  [DEAL CHAMPION] Arguing...
    Headline: Invest in MS
    Conviction: 8/10
  [RISK PARTNER] Rebutting...
    Headline: Overvalued MS
    Conviction: 8/10

  DEBATE RESULT: CONTESTED
    Champion: 8/10 | Risk Partner: 8/10

============================================================
  STEP 5: Investment Committee Decision
  LLM: NVIDIA NIM (meta/llama-3.3-70b-instruct)
============================================================

======================================================================
  PIPELINE COMPLETE - FINAL SUMMARY (ALL LIVE DATA)
======================================================================

  REPORT GENERATED: 2026-05-09 10:16:45
  Company:          Morgan Stanley (MS)
  Sector/Tier:      Financial Services | Tier 1: Banks/Insurance

------------------------------
  FINANCIAL SNAPSHOT (Bank Metrics)
------------------------------
  Revenue (TTM):    $68,773.0M (Growth: 16.3%)
  Net Income (TTM): $18,113.0M
  ROE:              16.4%
  Efficiency Ratio: 12.9%
  Book Value/Share: $66.18
  Dividend Yield:   2.07%

----------------------------------------
  PEER COMPARABLES (Bank Metrics)
----------------------------------------
  Ticker   | P/E Ratio      | P/Book   | ROE
  ----------------------------------------------
  MS       | 17.474207      | 2.917737 | 16.4%

  MARKET INTEL
  TAM/SAM/SOM:      TAM: $2.5T | SAM: $1.2T | SOM: $450B
  Competitive Moat: Microsoft's competitive moat is forged by its entrenched enterprise ecosystem, leadership in generative artificial intelligence, high customer switching costs, massive economies of scale in its Azure cloud, and powerful network effects across its products. The company's global data center infrastructure is a significant barrier to entry, allowing it to offer services at a cost and scale that new entrants cannot match. Microsoft's massive and growing backlog of contracted revenue provides exceptional visibility into future performance and signals a very stable business model.

------------------------------
  SCORING AUDIT (0-100)
------------------------------
  FORENSIC:    15 (Cash:40 | Margin:30 | Lev:10)
  MANAGEMENT:  90 (Vision:95 | Exec:92 | Gov:88)

------------------------------
  VALUATION SCENARIOS (EV)
------------------------------
  WACC (Cost of Capital): 9.0% (Damodaran Logic)
  BEAR CASE:   $0.0M
  BASE CASE:   $0.0M (ENTRY CEILING)

  BULL CASE:   $0M

------------------------------
  ACTIONABLE VALUATION (PRICE)
------------------------------
  Current Price: $193.09
  Implied Fair Value: $-183.37
  Implied Upside/Downside: -195.0%

======================================================================
  EXECUTIVE INVESTMENT MEMO
======================================================================
  IC VERDICT:  REJECT (HIGH CONVICTION)
  DEBATE:      CONTESTED

  THESIS PILLARS:
  • N/A

  --------------------------------------------------
  WHAT MUST GO RIGHT       | WHAT CAN GO WRONG
  --------------------------------------------------

[REASONING]
  Accounting and leverage risks are too high for institutional capital.

[RISKS]
  N/A

[CONDITIONS]
  • Verify TTM FCF accuracy vs quarterly capex lumpy-ness.

======================================================================
  DATA PROVENANCE & FOOTNOTES
======================================================================
  • Financials: yfinance (TTM Summation Logic)
  • Peer Sets: CapIQ (Primary) / Sector fallbacks
  • Valuation: Damodaran/IB Methodology via RAG Math Agent
  • Search: Tavily (Market Intel & Competitive Moats)
  • Decision: Multi-Agent NVIDIA NIM (meta/llama-3.3-70b-instruct)
======================================================================