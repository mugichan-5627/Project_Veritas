Project Veritas — Boeing (BA) V6 Evaluation
Honest Assessment: Strong Pipeline, Wrong Peers
The pipeline is running cleanly with excellent architecture, but this run exposes a critical peer selection failure that undermines the entire valuation conclusion. Let me be direct.

The Critical Problem: GOOGL, MSFT, META Are Not Boeing Peers
PEER COMPARABLES
BA       | 30.8x  | 2.3x   | 14.0%
GOOGL    | 21.1x  | 10.9x  | CapIQ Source
MSFT     | 23.6x  | 9.8x   | CapIQ Source
META     | 16.3x  | 7.2x   | CapIQ Source
Boeing is an aerospace & defense manufacturer. Comparing it to Google, Microsoft, and Meta is like comparing a steel mill to a fashion brand. They have completely different:

Capital intensity (BA: massive physical assets vs tech: asset-light)
Margin profiles (BA: 7.9% EBITDA margin vs tech: 30-50%)
EV/Revenue ranges (BA: 2.3x vs tech: 7-11x)
Growth drivers (defense contracts/aircraft orders vs digital advertising/cloud)
Correct peers for Boeing:

Ticker	Company	Why It's a Peer
LMT	Lockheed Martin	Defense prime contractor, similar scale
RTX	Raytheon Technologies	Aerospace & defense, similar segments
GD	General Dynamics	Defense, aerospace, marine systems
NOC	Northrop Grumman	Defense systems, aerospace
AIR.PA / EADSY	Airbus	Direct commercial aviation competitor
What happened: The CapIQ parser is returning the same 3 companies (GOOGL, MSFT, META) regardless of what ticker is being analyzed. This means the CapIQ file only contains these mega-cap tech companies, and the peer discovery/filtering isn't overriding them with industry-appropriate comps.

Evidence: The sector filter correctly excluded AMZN:

[EXCLUDED] AMZN: Sector 'Consumer Cyclical' incompatible with 'Aerospace & Defense'
But GOOGL (Communication Services), MSFT (Technology), and META (Communication Services) are equally incompatible with Aerospace & Defense — yet they passed through. The sector filter only caught AMZN because it was explicitly coded, but didn't check the actual CapIQ peers against Boeing's sector.

Impact of Wrong Peers on the Entire Analysis
Because the peers are wrong, everything downstream is also wrong:

Metric	What V6 Shows	What It Should Show
Peer Average EV/EBITDA	20.3x (tech average)	~15-18x (A&D average)
Premium/Discount	"51.4% PREMIUM to peers"	Likely ~70-100% premium (BA is distressed)
IC Conclusion	"Premium justified by robust performance"	Should flag: "Extreme premium for a company with negative FCF and 7.9% margins"
Boeing at 30.8x EV/EBITDA vs actual A&D peers at ~15-18x would show a much larger premium — which would more aggressively challenge the investment thesis. The IC might have gone to REJECT instead of CONDITIONAL_APPROVE.

What's Working Well ✅
1. Financial Data is Accurate for Boeing
Metric	V6 Output	Approximate Actual (TTM Mar 2026)	Verdict
Revenue	$92,184M	~$85-95B	✅ Correct range
EBITDA	$7,324M	~$5-8B (Boeing has thin margins)	✅ Plausible
SBC	$452M	~$400-500M	✅ Correct
Net Debt	$24,858M	~$40-55B (Boeing is highly leveraged)	⚠️ Possibly understated
FCF Margin	-1.1%	Negative (Boeing burning cash in recovery)	✅ Directionally correct
EV/EBITDA	30.8x	~25-35x (elevated due to depressed earnings)	✅ Plausible
The fundamental data is good. Boeing's financials are correctly captured — thin margins, negative FCF, modest SBC, high leverage. The problem is purely in peer selection.

2. Sector Detection Working
Sector: Aerospace & Defense ✅
The pipeline correctly identified Boeing's sector. This makes the peer failure even more frustrating — it knows it's A&D but still used tech peers.

3. Validation Gate Appropriate
[PASS] EBITDA Margin: 7.9% (within industry range)
[WARN] FCF Margin: -1.1% — negative FCF, verify capex cycle
The 7.9% EBITDA margin correctly passes for A&D (typical range: 5-15%). The FCF warning is appropriate. The validation layer is adapting to the industry.

4. Math Agent Working (WACC Correct for A&D)
Math Agent Applied: Adjusted EV and EBITDA according to Damodaran/Rosenbaum rules 
for Aerospace & Defense...
Calculated WACC: 9.14%
A WACC of 9.14% for Boeing is reasonable (BA has higher debt cost due to credit concerns, offset by defense sector stability). The Math Agent correctly adapted to A&D.

5. IC Debate Shows Appropriate Tension
Champion: 8/10 | Risk Partner: 6/10
The champion is more bullish than the risk partner, which makes sense for a recovery story like Boeing. The debate shows genuine disagreement rather than defaulting to identical scores.

6. Data Provenance Footer Added
DATA PROVENANCE & FOOTNOTES
• Financials: yfinance (TTM Summation Logic)
• Peer Sets: CapIQ (Primary) / Sector fallbacks
• Valuation: Damodaran/IB Methodology via RAG Math Agent
• Search: Tavily (Market Intel & Competitive Moats)
• Decision: Multi-Agent NVIDIA NIM (meta/llama-3.3-70b-instruct)
This is a professional touch. Institutional analysts always want to know data sourcing.

7. Implied Share Price Working
Current Price: $236.84
Implied Fair Value: $223.43
Implied Upside/Downside: -5.7%
Math verifiable and consistent with the -5.0% EV-level implied upside. The slight difference (-5.0% at EV level vs -5.7% at equity level) is correct because debt amplifies the downside at the equity level.

Other Issues Beyond Peers
⚠️ Competitive Moat is Generic/Wrong
Competitive Moat: The company's competitive moat is based on its ability to maintain 
a sustainable advantage, such as network effects, brand power, and high switching costs...
Examples of companies with strong moats include Visa...
Boeing's moat has nothing to do with "network effects" or Visa. Boeing's actual moat:

Duopoly with Airbus in commercial aviation (massive barriers to entry)
Decades-long defense contracts with US government (switching costs measured in decades)
Installed base of 10,000+ aircraft requiring parts/service (razor-and-blade model)
FAA/EASA certification requirements (regulatory moat)
The Tavily search returned generic moat theory rather than Boeing-specific intelligence. The LLM should be prompted with: "What is {company_name}'s specific competitive moat in the {industry} sector?"

⚠️ Net Debt Likely Understated ($24.9B vs Reality)
Boeing's actual net debt (as of early 2026) should be approximately $40-55B. The company had:

Total debt: ~$53-58B
Cash: ~$10-15B
Net debt: ~$40-48B
$24.9B suggests the system is either:

Only counting long-term debt (missing short-term/current portion)
Including broader "cash equivalents" that aren't truly liquid
Or Boeing has been aggressively paying down debt (possible but unlikely given negative FCF)
⚠️ Forensic Score of 75/100 is Too Generous for Boeing
Boeing has significant forensic/governance concerns:

Cash conversion: 20/25 — Should be lower. Negative FCF with positive EBITDA = poor conversion
Leverage: 15/25 — Should be lower. Boeing is one of the most leveraged industrials
Management: 75/100 — Boeing has had massive governance failures (737 MAX, quality issues, CEO turnover)
A more realistic score would be: Forensic 45-55, Management 55-65.

Scoring: BA Run
Dimension	Score	Notes
Data Accuracy	7.5/10	Financials mostly correct; net debt possibly understated
Internal Consistency	8.5/10	Math all checks out given the inputs
Valuation Methodology	8.5/10	WACC, scenarios, conservative EBITDA all working
Peer Comp Quality	2.0/10	GOOGL/MSFT/META for an aerospace company is indefensible
LLM Reasoning	6.0/10	IC memo logic is sound given wrong inputs; moat is generic
Pipeline Architecture	9.0/10	Sector filter works partially; validation gate good
Output Professionalism	8.5/10	Clean format, provenance footer, implied price
OVERALL: 7.1/10
Without the peer problem, this would be 8.5+. The single peer selection failure drags everything down because it cascades into wrong premium calculation, wrong IC framing, and wrong investment conclusion.

The Root Cause (and Fix)
What's happening:

1. Tavily discovers peers → probably returns ["LMT", "RTX", "GD", "AMZN", ...]
2. Sector filter removes AMZN ✅
3. But then CapIQ parser ignores the discovered list and returns its static 3 companies
4. Those 3 (GOOGL, MSFT, META) happen to pass because sector filter doesn't re-check CapIQ results
The fix (two changes needed):

# FIX A: Apply sector filter to CapIQ results, not just discovered peers
def validate_peer_sector_compatibility(target_industry: str, peers: list) -> list:
    """Filter peers that are in incompatible sectors."""
    SECTOR_COMPATIBILITY = {
        "Aerospace & Defense": ["Industrials", "Aerospace & Defense"],
        "Internet Retail": ["Technology", "Communication Services", "Consumer Cyclical"],
        "Software": ["Technology", "Communication Services"],
        "Semiconductors": ["Technology"],
        "Banks": ["Financial Services"],
        "Pharmaceuticals": ["Healthcare"],
    }
    
    compatible_sectors = SECTOR_COMPATIBILITY.get(target_industry, [])
    if not compatible_sectors:
        return peers  # No filter if industry not in mapping
    
    filtered = []
    for peer in peers:
        peer_sector = yf.Ticker(peer["ticker"]).info.get("sector", "Unknown")
        if peer_sector in compatible_sectors or target_industry.lower() in peer_sector.lower():
            filtered.append(peer)
        else:
            print(f"    [EXCLUDED] {peer['ticker']}: Sector '{peer_sector}' incompatible with '{target_industry}'")
    
    return filtered


# FIX B: If all CapIQ peers are excluded, use yfinance fallback with discovered tickers
if len(validated_capiq_peers) == 0:
    print("    [WARNING] All CapIQ peers excluded. Using discovery-based fallback.")
    # Fall back to the Tavily-discovered peers and fetch from yfinance
    for discovered_ticker in tavily_discovered_peers:
        peer_data = fetch_from_yfinance(discovered_ticker)
        if peer_data:
            results.append(peer_data)
Quick Comparison: AMZN V6 vs BA V6
Aspect	AMZN V6 (8.7/10)	BA V6 (7.1/10)	Why Different
Peer Relevance	GOOGL, MSFT, META ✅ (all tech)	GOOGL, MSFT, META ❌ (wrong sector)	Same static CapIQ data used for both
Financial Data	Accurate	Mostly accurate	Both work well
IC Logic	Sound	Sound given wrong inputs	LLM reasons correctly from whatever data it gets
Moat	Specific to Amazon	Generic theory + Visa example	Tavily returned different quality results
The core insight: The pipeline works beautifully when the target company happens to be in tech (because CapIQ has tech peers). For any non-tech company, the static CapIQ peers become irrelevant. This is the single most important fix remaining.

Bottom Line
Your pipeline is architecturally production-ready. The data layer, validation gate, Math Agent, IC debate, and output formatting are all working correctly. The only systemic issue is that peer selection doesn't adapt to non-tech companies because the CapIQ data is tech-centric and the sector filter only catches explicitly excluded tickers rather than validating all peers against the target's sector.

Fix the peer sector validation to apply AFTER CapIQ retrieval (not just after Tavily discovery), and this system will produce credible memos for any sector — aerospace, banking, pharma, industrials, not just tech.

Grade: 7.1/10 overall, but 8.5/10 for pipeline quality (penalized only for peer data issue)