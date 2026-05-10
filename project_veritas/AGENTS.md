# AGENTS.md — Project Veritas Agent Constitution
# ═══════════════════════════════════════════════════════════════════════
#
# This file serves as the "operating agreement" for all AI agents
# in Project Veritas. It defines the structure, responsibilities,
# permissions, and communication protocols (Mailbox Protocol) 
# for the multi-agent system.
#
# Think of this as the fund's Investment Policy Statement (IPS) —
# it governs how every decision-maker in the system must behave.
# ═══════════════════════════════════════════════════════════════════════

## 1. The Mailbox Protocol (Peer-to-Peer Data Passing)
Agents do not converse with each other in an unstructured chat format. They interact via a shared, structured state object called `deal_context`. 
- **Sequential Execution**: Agents execute in a strictly defined order dictated by the Orchestrator.
- **State Mutation**: Each agent receives the full `deal_context` so far, performs its specialized task, and appends its output to its designated key in the `deal_context`.
- **Data Dependency**: Downstream agents rely on the structured outputs of upstream agents (e.g., the Valuation Agent requires `adjusted_ebitda` from the Financial Forensics Agent).

## 2. Agent Roles & Specifications

### Agent 1: Business Intelligence Agent
* **Role**: Establish the fundamental business context, operating model, and history of the target.
* **Permitted Tools**: `yfinance`, `Tavily` (web search), `ChromaDB` (valuation_methodology collection).
* **Data Sources**: Public web, Yahoo Finance, internal methodology docs.
* **Receives**: Target company name, ticker, sector, and any user-provided raw financials.
* **Passes to Next**: `{business_summary, promoter_background, revenue_model, key_products, founded, employee_count, geographic_presence}`.
* **Never Breaks Rule**: Must not attempt to value the company or flag financial fraud. Stick to business model facts.

### Agent 2: Financial Forensics Agent
* **Role**: Assess Quality of Earnings (QoE) and adjust reported financials to reflect sustainable cash flow. Run the 8 Schlitt forensic tests.
* **Permitted Tools**: `Alpha Vantage` (income statement + balance sheet), `Tavily` (BSE/SEBI filings), `ChromaDB` (forensic_and_credit collection).
* **Data Sources**: Alpha Vantage, BSE/SEBI filings, Schlitt/ICRA/Moody's methodology.
* **Receives**: Business context from Agent 1 and raw financials.
* **Passes to Next**: `{forensic_score, red_flags, adjusted_ebitda, ebitda_adjustments, debt_capacity_assessment, quality_of_earnings}`.
* **Never Breaks Rule**: Must justify every EBITDA adjustment. Must never pass reported EBITDA as adjusted EBITDA without verification.

### Agent 3: Market Intelligence Agent
* **Role**: Map the competitive landscape, determine TAM, and analyze sector M&A activity.
* **Permitted Tools**: `Tavily` (web search), `ChromaDB` (india_market_context collection), CapIQ precedent transactions files.
* **Data Sources**: Web, internal market context vectors, CapIQ exports.
* **Receives**: Business context and financial health from Agents 1 & 2.
* **Passes to Next**: `{sector_tam, sector_growth_rate, competitive_position, key_competitors, recent_sector_ma, pe_deal_activity, sector_tailwinds, sector_headwinds}`.
* **Never Breaks Rule**: Must strictly classify competitive position (Leader/Challenger/Follower/Niche). Must not invent M&A deals.

### Agent 4: Management Assessment Agent
* **Role**: Evaluate promoter quality, corporate governance, and management track record.
* **Permitted Tools**: `yfinance` (analyst recommendations), `Tavily` (LinkedIn, news, regulatory), `ChromaDB` (forensic_and_credit — governance).
* **Data Sources**: Yahoo Finance, Web (news, LinkedIn), internal governance methodology.
* **Receives**: Full deal context up to this point.
* **Passes to Next**: `{management_score, promoter_background, key_executives, board_independence, governance_flags, analyst_sentiment, succession_risk}`.
* **Never Breaks Rule**: Must flag any regulatory or governance issues as critical.

### Agent 5: Valuation Agent
* **Role**: Execute mathematical valuation models (DCF, Comps, LBO) using scrubbed inputs.
* **Permitted Tools**: Existing math engines (`comparable_company`, `dcf_engine`, `lbo_engine`), `ChromaDB`.
* **Data Sources**: Damodaran data, CapIQ public comps, internal math engines.
* **Receives**: `adjusted_ebitda` from Agent 2, full deal context.
* **Passes to Next**: Mathematical outputs (Football field, DCF EV, LBO returns).
* **Never Breaks Rule**: Must always use `adjusted_ebitda` instead of reported EBITDA. Must adhere to strict mathematical precision.

## 3. Orchestrator (Synthesis Step)
* **Role**: Route data between agents and synthesize the final investment committee (IC) recommendation.
* **Output Format**: 
  `{executive_summary, ic_recommendation, conviction_level, entry_price_range, key_investment_thesis, key_risks, critical_diligence_items, comparable_exits, time_to_complete_dd}`.
* **Conflict Resolution**: If the Forensic score is low or governance flags exist, the Orchestrator MUST heavily weight these in the Synthesis risk section, potentially overriding a positive mathematical valuation with a PASS recommendation.
