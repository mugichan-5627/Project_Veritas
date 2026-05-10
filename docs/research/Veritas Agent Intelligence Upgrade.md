Veritas Agent Intelligence Upgrade Plan
Summary
Refactor Veritas from an India-specific fetch + summarize pipeline into a global, evidence-first diligence system where each agent produces analyst-grade judgment artifacts, not just flat fields in deal_context. Keep the existing mailbox/orchestrator pattern and math engines, but change the contract so every agent must return: hypotheses, supporting evidence, counter-evidence, confidence, explicit diligence gaps, and source citations. Default behavior for private companies with sparse data is a gap-aware memo: no invented valuation, no fake precision, and a clear request list for missing diligence materials.

Key Changes
Replace the current flat deal_context shape in orchestrator.py with structured sections: company_identity, source_registry, business_model, forensics, market, management, valuation, red_team, open_questions, confidence_summary, ic_recommendation.
Add a common per-agent output contract used by all agents:
conclusion
key_hypotheses
supporting_evidence
counter_evidence
facts
inferences
missing_evidence
red_flags
confidence
sources
Add a shared evidence schema used across agents and memory retrieval:
source_id, url_or_path, publisher, doc_type, jurisdiction, company, as_of_date, evidence_tier, excerpt, claim_tags
evidence_tier default order: official filing/regulator > audited report > rating report > earnings transcript > reputable press > general web
Split Chroma usage into two logical families:
methodology_* collections for Damodaran / McKinsey / Rosenbaum / Schilit style reasoning support
evidence_* collections for company-specific filings, transcripts, rating reports, regulatory orders, press releases, and prior deal memos
Upgrade memory_agent.py to support retrieval filters by company, jurisdiction, doc_type, date range, and evidence_tier, plus dedupe and citation formatting. Retrieval should return chunks plus metadata, never plain text only.
Replace India-only source assumptions in prompts and tools. Global source routing should work in this order:
Public company: SEC/EDGAR, Companies House, exchange filings, company IR, annual reports, earnings transcripts, public rating reports, regulator actions
Private company: company site, official registries where available, court/regulatory records, press, employee/customer signals, public comps, debt/rating reports if any
If jurisdiction-specific official data is unavailable, fall back to reputable public web and lower confidence rather than failing silently
Remove hardwired “Indian PE fund” framing from agent prompts and AGENTS constitution; replace with “global private equity diligence analyst” plus jurisdiction-aware source selection.
Introduce a shared agent reasoning loop in all agents:
form hypotheses
retrieve evidence
test confirming evidence
test disconfirming evidence
classify claim quality
write conclusion with confidence and gaps
Add a new Red Team / IC Challenge agent after valuation. Its mandate is to attack the draft deal case, identify weak assumptions, challenge comp selection, question EBITDA quality, and surface what could make the fund walk away.
Add synthesis rules in the orchestrator:
poor forensics or governance can override attractive valuation
missing data lowers conviction and can force PENDING FURTHER DILIGENCE
private-company outputs without usable financials must emit operating/business/governance diligence plus explicit missing-data requests, and valuation only if enough evidence exists for a range with labeled assumptions
Agent-by-Agent Behavior
Business Intelligence Agent:
change output from descriptive brief to business model map
require explicit statements on revenue model, unit economics drivers, customer types, supplier dependencies, recurring vs transactional revenue, geography, cyclicality, and possible moat
add a business_quality_view and what must be true for this thesis to hold
Financial Forensics Agent:
keep Schilit but expand to triangulation across cash flow, receivables, inventory, margins, capex, related parties, auditor behavior, restatements, and adjustments language
output an earnings_quality_bridge from reported EBITDA to normalized EBITDA with justification per adjustment
permit INSUFFICIENT TO UNDERWRITE EBITDA as a first-class outcome
Market Intelligence Agent:
stop assuming CapIQ precedent coverage exists
focus on market structure, value chain, sector drivers, substitutes, cyclicality, and public comps reasoning
require a comp inclusion memo for each peer: why comparable, why not, key gaps, include/exclude
only provide transaction comps when source-backed; otherwise emit transaction evidence insufficient
Management Assessment Agent:
frame as governance/stewardship agent, not LinkedIn scraper
score integrity, execution, capital allocation, minority treatment, and succession risk
always output a management diligence question list
Valuation Agent:
keep DCF/comps/LBO tools, but make them downstream of business and forensics outputs
require scenario ranges and a do not exceed price where assumptions stop underwriting target returns
refuse precise valuation when normalized EBITDA or comp set quality is weak
explain divergence across methods instead of only reporting spread
Red Team Agent:
challenge hidden assumptions, fragile evidence, overfit comps, accounting optimism, governance blind spots, and unsupported valuation steps
output deal breakers, questions before IC, and what would change our mind
Public Interfaces And Types
Update AGENTS.md so each agent’s “passes to next” contract uses the new structured schema instead of mostly scalar fields.
Add shared Python types or Pydantic models for:
EvidenceItem
AgentFinding
AgentMemo
DiligenceGap
CompAssessment
NormalizedAdjustment
FinalICMemo
Preserve existing Phase 0 math tool interfaces where possible; wrap them with richer inputs rather than rewriting their internals first.
Add an orchestrator result mode enum:
FULL_PUBLIC_UNDERWRITE
GAP_AWARE_PRIVATE_MEMO
LIMITED_EVIDENCE_SCREEN
DO_NOT_UNDERWRITE
Test Plan
Add unit tests for evidence ranking and retrieval filtering in memory_agent.
Add agent contract tests that fail if an agent returns a conclusion without sources, confidence, or missing-evidence sections.
Add regression tests for:
public company with strong filings coverage
private company with sparse evidence and no usable financials
bad comp universe case modeled after Vishal Mega Mart
positive valuation but low forensic confidence leading to downgraded IC outcome
governance red flags overriding an otherwise attractive valuation
Add one end-to-end orchestrator test asserting that final memo contains: conclusion, supporting evidence, counter-evidence, diligence gaps, and jurisdiction-aware source citations.
Assumptions
No paid APIs are required for the target design; paid-vendor-only logic should become optional adapters, not core dependencies.
Veritas should optimize for globally available public evidence first, and explicitly degrade confidence when coverage is weak.
For private companies, the default output is the previously selected Gap-Aware Memo: useful diligence, transparent limitations, and no invented precision.
Existing valuation math engines remain trusted and should be reused; the main upgrade is agent reasoning quality, evidence handling, and orchestration policy.