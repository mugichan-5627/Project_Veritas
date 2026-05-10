# Project Veritas

**Institutional-Grade Multi-Agent RAG System for Private Equity Due Diligence**

---

## What Is This?

Project Veritas is an AI-powered due diligence platform that replicates how a top-tier PE fund's deal team operates — but with AI agents instead of junior analysts.

Given a target company, the system will:
1. **Value it** using DCF, Comparable Companies, and LBO models
2. **Stress-test** the financials for manipulation (forensic analysis)
3. **Assess** the business quality and competitive position
4. **Contextualize** it against sector benchmarks and credit ratings
5. **Remember** past analyses to build institutional knowledge over time

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   USER QUERY                         │
│         "Evaluate XYZ Corp for acquisition"          │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  ORCHESTRATOR   │  ← Decides which agents to deploy
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
  ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
  │ Valuation │  │ Forensic  │  │ Market    │
  │   Agent   │  │   Agent   │  │   Agent   │
  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
        │              │              │
  ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
  │  DCF      │  │ Schilit   │  │ ICRA      │
  │  Comps    │  │ Red Flag  │  │ Sector    │
  │  LBO      │  │ Detector  │  │ Analysis  │
  │  (Tools)  │  │ (Tools)   │  │ (Tools)   │
  └───────────┘  └───────────┘  └───────────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
              ┌────────▼────────┐
              │  ChromaDB       │  ← Institutional Memory
              │  (RAG Memory)   │     Damodaran data, PDFs,
              │                 │     past analyses
              └─────────────────┘
```

## Data Foundation

| Source | Files | Purpose |
|--------|-------|---------|
| **Damodaran Datasets** | 48 .xls files (India + Emerging Markets) | Betas, WACC, margins, multiples, growth rates |
| **CapIQ Public Comps** | 10 .xlsx files (India, all GICS sectors) | Sector peer multiples: EV/EBITDA, EV/Revenue, P/B, EBITDA margins |
| **CapIQ Precedent Transactions** | 10 .xlsx files (India M&A) | Implied deal multiples, transaction values, buyer/seller data |
| **CapIQ PE Buyouts** | 4 .xlsx files (Consumer, Financials, Industrials, Real Estate) | PE-specific deal data with investor type classification |
| **Knowledge Base** | 21 PDFs (Damodaran, McKinsey, Rosenbaum, Pignataro, Schilit) | Methodology reference for agent reasoning |
| **ICRA Methodologies** | 14 sector-specific rating frameworks | Credit risk and sector-specific assessment criteria |

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 0** | Math validation -- DCF, Comps, LBO engines with reverse-validation tests | Complete |
| **Phase 1** | Agent construction -- LangChain agents calling validated tools | Next |
| **Phase 2** | RAG memory -- ChromaDB ingestion of Damodaran data + PDF knowledge base | Planned |
| **Phase 3** | Agent constitution -- AGENTS.md governance, conflict resolution, escalation | Planned |
| **Phase 4** | Integration -- End-to-end due diligence pipeline with output formatting | Planned |

## Phase 0 -- Complete

Three valuation tools built and validated:
- **comparable_company.py:** Rosenbaum & Pearl Ch.3 percentile methodology. Peer universe selection logic with confidence scoring.
- **dcf_engine.py:** McKinsey Value Driver Formula terminal value with Gordon Growth cross-check. 3x3 sensitivity table. TV% flag at 75%.
- **lbo_engine.py:** Full debt schedule with cash sweep. Three-scenario returns. Value creation bridge with reconciliation.

Two test cases:
- **test_vishal_mega_mart.py:** PRESERVED as peer selection failure case. 1046% spread demonstrates judgment requirement in comp selection. Per Rosenbaum Ch.3 p.115.
- **test_mankind_pharma.py:** PRIMARY validation. 56% spread (DCF floor Rs 18,932 Cr / LBO Rs 24,000 Cr / Comps Rs 29,463 Cr). Real CapIQ peers. TEV reconstructed from Market Cap + Debt - Cash. Reverse validation PASS. 78% operational returns.

Known limitation: DCF RONIC defaults to WACC -- will be resolved in Phase 1 via Damodaran roeIndia.xlsx lookup.

## Tech Stack

- **Language:** Python 3.11+
- **Math:** NumPy, Pandas, SciPy
- **Agents:** LangChain (Phase 1)
- **Memory:** ChromaDB (Phase 2)
- **LLM:** OpenAI GPT-4 (Phase 1)
- **Testing:** pytest with reverse-validation methodology

## Project Author

Built as a personal project to demonstrate the intersection of **quantitative finance** and **AI engineering** — the kind of systems that PE funds and investment banks are actively building in-house.

---

*"Veritas" — Latin for "truth." Because in due diligence, the only thing that matters is the truth behind the numbers.*
