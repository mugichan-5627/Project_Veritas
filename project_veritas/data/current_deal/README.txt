DROP ZONE FOR CURRENT DEAL DOCUMENTS

Purpose:
Place company-specific documents (Annual Reports, DRHP, Investor Presentations) 
for the target being valued right now in this folder.

Workflow:
1. Drop the PDF(s) here.
2. Run: py -m project_veritas.memory.pdf_ingestion --collection current_deal --clear-first
3. The valuation agent will now query this specific document alongside global methodology.

The --clear-first flag ensures there is no cross-contamination between different deals.
