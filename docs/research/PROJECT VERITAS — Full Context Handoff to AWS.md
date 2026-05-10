PROJECT VERITAS — Full Context Handoff
Copy everything below and paste it into your next session:

PROJECT OVERVIEW
Project Veritas is an automated due diligence report generator designed to produce PE/IB-grade investment memos. The goal is quality high enough that private equity shops would use it without hesitation.

ARCHITECTURE (Pipeline Steps)
Dynamic ChromaDB RAG Retrieval — Uses BGE-M3 embeddings (BAAI/bge-m3, 1024-dim) with ChromaDB vector store. Queries cover valuation methodology, accounting red flags, and terminal growth assumptions.
Live Data Pull — yfinance for financials + CapIQ for peer sets
RAG Math Agent — Computes valuation using Damodaran/IB methodology. Outputs JSON (has a known parse failure bug with control characters).
Multi-Agent IC Debate — Deal Champion vs Risk Partner, 2 rounds, scored by conviction (1-10). Determines CONTESTED/CONSENSUS.
Investment Committee Decision — Final HOLD/BUY/PASS verdict
LLM BACKEND
Provider: Fireworks AI
Model: accounts/fireworks/models/llama-v3p3-70b-instruct
Labeled as "NVIDIA NIM" in logs (likely a naming artifact)
SECTOR CLASSIFICATION
Tier-based system (e.g., "Tier 1: Banks/Insurance")
Financial services companies use P/Book + P/E valuation
Efficiency ratio tracked for banks (but returning N/A for AXP)
VALUATION METHODOLOGY
Cost of Equity via Damodaran logic (CAPM-based)
P/Book justified multiple (target: ROE-driven)
P/E cross-check
Blended fair value from both methods
Sensitivity table: P/Book multiple vs ROE scenarios (±20%)
Bear/Base/Bull equity value scenarios
OUTPUT STRUCTURE
Financial Snapshot (bank metrics variant)
Peer Comparables table
TAM/SAM/SOM + Competitive Moat
Forensic Score (Earnings Quality + Capital Adequacy + Credit Risk)
Management Score (Vision + Execution + Governance)
Valuation Scenarios + Cross-Check + Sensitivity
Precedent Transactions
Entry Strategy (fair value, aggressive entry, walk-away price)
Executive Investment Memo (verdict, thesis pillars, what must go right/wrong)
Risks, Conditions, Reasoning
Limitations & Data Provenance
CRITICAL ISSUES I IDENTIFIED (from AXP test run)
P0 — Deal Breakers
Precedent transactions are irrelevant — pulling generic FIG M&A (ORIX Bank, Miluna, etc.) with all P/Book = N/A. Need relevance scoring or curated deals.
Revenue figure likely wrong — $74.17B doesn't match AXP's actual ~$60-65B TTM. Possible double-counting or gross vs net interest issue.
No DDM (Dividend Discount Model) — the standard primary valuation for financials is missing.
Text truncation in IC memo — "What Must Go Right" column entries cut off mid-sentence.
Justified P/Book derivation is opaque — the 5.2x "Fair P/Book" is never shown as (ROE - g)/(CoE - g).
P1 — Requires Rework
Math Agent JSON parse failure — no retry logic, unclear what degrades.
Forensic sub-scores unexplained — Earnings Quality 23/100 is alarming with no drivers listed.
COF peer outlier (58.1x P/E) — no outlier detection, distorts analysis.
Mastercard (MA) missing from reference peer set.
Efficiency Ratio = N/A for a Tier 1 financial company.
P2 — Should Fix
Debate agents don't actually update — static 9/10 vs 8/10 both rounds.
TAM/SOM definitions inconsistent — SOM $72.8B vs AXP's actual $1.5T+ billings.
Sensitivity table shows equity values not per-share prices.
No probability weighting on scenarios.
P3 — Nice to Have
Sum-of-parts for hybrid models (issuer + network)
Regulatory capital analysis (CET1 equivalent)
WHAT WORKS WELL
Pipeline architecture mirrors real PE workflow
Entry strategy section is practical and actionable
Data provenance/audit trail is proper
Moat narrative is accurate for AXP
ROE-based valuation is conceptually correct for financials
Limitations section is appropriately humble
NEXT STEPS WE DISCUSSED
I offered to:

Audit backend code (FastAPI/Flask routes + orchestration)
Audit frontend components (React/Next.js rendering)
Write stress test scripts (concurrent requests, edge cases, adversarial inputs)
Cross-validate multiple ticker outputs for systematic bugs
Design full test matrix (frontend, API, RAG, Math Agent, LLM, E2E)
MY ROLE
Acting as a critical reviewer simulating a PE Managing Director / senior associate reviewing an IC memo — flagging anything that wouldn't survive scrutiny in a real investment committee at a top-tier fund.

End of context. Paste this at the start of your next session and say "continuing Project Veritas" and I'll pick up exactly where we left off.

