import os
import re
import json
import logging
import math
from typing import List, Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

SECTOR_FALLBACK_MAP = {
    "Discount Stores": ["COST", "TGT", "DG", "DLTR", "BJ"],
    "Credit Services": ["DFS", "COF", "SYF", "ALLY", "OMF", "V", "MA"],
    "Semiconductors": ["NVDA", "AVGO", "QCOM", "TXN", "AMD", "INTC"],
    "Aerospace & Defense": ["LMT", "NOC", "RTX", "GD", "BA"],
    "Software - Infrastructure": ["MSFT", "ORCL", "CRM", "NOW", "ADBE"],
    "Software - Application": ["ADBE", "INTU", "CDNS", "SNPS", "ANSS"],
    "Banks - Diversified": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
    "Banks - Regional": ["PNC", "USB", "TFC", "FITB", "HBAN"],
    "Insurance - Diversified": ["BRK-B", "AIG", "MET", "PRU", "ALL"],
    "Internet Content & Information": ["GOOGL", "META", "SNAP", "PINS", "TTD"],
    "Drug Manufacturers": ["JNJ", "LLY", "PFE", "MRK", "ABBV"],
    "Oil & Gas Integrated": ["XOM", "CVX", "SHEL", "TTE", "BP"],
    "Consumer Electronics": ["AAPL", "SONY", "HPQ", "DELL"],
    "Restaurants": ["MCD", "SBUX", "CMG", "YUM", "DPZ"],
    "Specialty Retail": ["HD", "LOW", "TJX", "ROST", "BBY"],
    "Beverages": ["KO", "PEP", "MNST", "STZ", "BF-B"],
    "Household Products": ["PG", "CL", "KMB", "CHD", "CLX"],
    "REITs": ["PLD", "AMT", "EQIX", "SPG", "O"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP"],
    "Telecom": ["T", "VZ", "TMUS", "CMCSA", "CHTR"],
    "Auto Manufacturers": ["TM", "F", "GM", "TSLA", "HMC"],
    "Medical Devices": ["MDT", "SYK", "ABT", "BSX", "ISRG"],
    "Capital Markets": ["GS", "MS", "SCHW", "BLK", "ICE", "RJF"],
    "Exchanges": ["ICE", "CME", "NDAQ", "CBOE", "SPGI"],
    "Payments/Networks": ["V", "MA", "FIS", "FISV", "GPN"],
    "Internet Retail": ["AMZN", "BABA", "EBAY", "JD", "PDD"],
    "Asset Management": ["BLK", "BX", "KKR", "APO", "ARES", "BAM"]
}

_METRICS_CACHE: Dict[str, Dict] = {}
_DISCOVERY_CACHE: Dict[str, Dict] = {}
REFERENCE_FINANCIAL_PEERS = {"V", "MA", "PYPL", "FIS", "GPN"}

class PeerDiscoveryEngine:
    """
    Multi-source peer discovery following Fix 1 specification.
    """
    @staticmethod
    def clear_cache():
        """Clears global peer and metrics caches to ensure fresh data for new deal runs."""
        global _METRICS_CACHE, _DISCOVERY_CACHE
        _METRICS_CACHE.clear()
        _DISCOVERY_CACHE.clear()
        # Also clear session cache in case it was used in other modules
        if hasattr(PeerDiscoveryEngine, '_static_peer_cache'):
            PeerDiscoveryEngine._static_peer_cache.clear()
    
    def __init__(
        self,
        capiq_directory: str = None,
        tavily_client=None,
        llm_client=None,
    ):
        self.capiq_dir = capiq_directory or os.environ.get("CAPIQ_DIR", "data")
        self.tavily = tavily_client
        self.llm = llm_client
        self.capiq_data = self._load_all_capiq_files()

    def discover_peers(self, ticker: str, num_peers: int = 5) -> Dict:
        """
        FIX 1: Robust Peer Discovery Logic.
        """
        cache_key = ticker.upper()
        if cache_key in _DISCOVERY_CACHE:
            return _DISCOVERY_CACHE[cache_key]

        target_info = self._get_target_info(ticker)
        target_metrics = self._get_target_metrics(ticker)
        
        logger.info(f"[PEERS] Starting robust discovery for {ticker}...")
        
        # Step 1 & 2: LLM Suggestion + yfinance validation
        suggested_peers = []
        if self.llm:
            suggested_peers = self._infer_peers_via_llm(
                ticker=ticker,
                company_name=target_info["name"],
                industry=target_info["industry"],
                sector=target_info["sector"],
                market_cap=target_info["market_cap"],
                num_peers=10
            )
        
        # Validate and filter
        valid_peers = []
        for p in suggested_peers:
            p_metrics = self._get_target_metrics(p)
            if p_metrics and p_metrics.get("revenue_ttm_M"):
                valid_peers.append(p)
        
        # Step 3 & 4: Similarity Scoring & Top 5
        final_peers = self._rank_peers_by_similarity(target_metrics, valid_peers)[:5]
        
        # Step 5: Fallback Map if < 3 survivors
        if len(final_peers) < 3:
            logger.info(f"[PEERS] Step 5 Fallback: Insufficient peers ({len(final_peers)}). Checking Fallback Map...")
            industry = target_info["industry"]
            
            # Robust lookup: check exact match then partial match
            fallback_list = SECTOR_FALLBACK_MAP.get(industry, [])
            if not fallback_list:
                for key in SECTOR_FALLBACK_MAP:
                    if key in industry or industry in key:
                        fallback_list = SECTOR_FALLBACK_MAP[key]
                        break
            
            for p in fallback_list:
                if p.upper() != ticker.upper() and p not in final_peers:
                    final_peers.append(p)
            final_peers = self._rank_peers_by_similarity(target_metrics, list(set(final_peers)))[:5]
            
        # Step 6: Broaden GICS if still < 3
        if len(final_peers) < 3:
            logger.info(f"[PEERS] Step 6 Fallback: Still insufficient ({len(final_peers)}). Broadening GICS...")
            # Simple broadening: using CapIQ or search for broader sector peers
            capiq_peers = self._search_capiq_by_industry(ticker, target_info["industry"], "broad", target_info["sector"])
            for p in capiq_peers:
                if p not in final_peers: final_peers.append(p)
            final_peers = self._rank_peers_by_similarity(target_metrics, list(set(final_peers)))[:5]

        # Final critical check
        if len(final_peers) < 3:
            logger.warning(f"[CRITICAL] Unable to establish peer set for {ticker}. Valuation unreliable. Manual peer input required.")
            result = {
                "peers": [],
                "peer_tickers": [],
                "confidence": "LOW",
                "error": "INSUFFICIENT_PEERS"
            }
            _DISCOVERY_CACHE[cache_key] = result
            return result

        # Fetch multiples for ranked survivors
        peer_multiples = self._fetch_multiples_for_peers(final_peers, target_ticker=ticker)
        
        result = {
            "peers": peer_multiples,
            "peer_tickers": [p["ticker"] for p in peer_multiples],
            "confidence": "HIGH",
            "method": "robust_fallback_chain",
            "target_info": target_info
        }
        _DISCOVERY_CACHE[cache_key] = result
        return result

    def _rank_peers_by_similarity(self, target: Dict, peer_tickers: List[str]) -> List[str]:
        """
        FIX 1: Similarity Scoring Specification.
        """
        is_fin = target.get("is_financial", False)
        scores = []
        for p_ticker in peer_tickers:
            peer = self._get_target_metrics(p_ticker)
            if not peer: continue
            
            try:
                if is_fin:
                    # BANK SIMILARITY: ROE, Assets, P/Book
                    t_roe = target.get("roe_pct", 10.0) or 10.0
                    p_roe = peer.get("roe_pct", 10.0) or 10.0
                    roe_diff = abs(t_roe - p_roe) / max(abs(t_roe), 1.0)
                    
                    t_mcap = target.get("market_cap_M", 1)
                    p_mcap = peer.get("market_cap_M", 1)
                    size_diff = abs(math.log(max(1, t_mcap)) - math.log(max(1, p_mcap))) / math.log(max(2, t_mcap))
                    
                    score = 1.0 - (0.60 * roe_diff + 0.40 * size_diff)
                else:
                    # INDUSTRIAL SIMILARITY: Margin, Growth, Capex, Size
                    t_ebitda_margin = (target.get("ebitda_adj_M", 0) / target.get("revenue_ttm_M", 1))
                    p_ebitda_margin = (peer.get("ebitda_adj_M", 0) / peer.get("revenue_ttm_M", 1))
                    
                    t_rev_growth = (target.get("revenue_growth_pct", 0) / 100)
                    p_rev_growth = (peer.get("revenue_growth_pct", 0) / 100)
                    
                    t_revenue = target.get("revenue_ttm_M", 1)
                    p_revenue = peer.get("revenue_ttm_M", 1)
                    
                    t_capex = abs(target.get("capex_M", t_revenue * 0.03))
                    p_capex = abs(peer.get("capex_M", p_revenue * 0.03))
                    
                    t_capex_intensity = t_capex / t_revenue
                    p_capex_intensity = p_capex / p_revenue
                    
                    t_mcap = target.get("market_cap_M", 1)
                    p_mcap = peer.get("market_cap_M", 1)
                    
                    margin_diff = abs(t_ebitda_margin - p_ebitda_margin) / max(abs(t_ebitda_margin), 0.01)
                    growth_diff = abs(t_rev_growth - p_rev_growth) / max(abs(t_rev_growth), 0.01)
                    capex_diff = abs(t_capex_intensity - p_capex_intensity) / max(t_capex_intensity, 0.01)
                    size_diff = abs(math.log(max(1, t_mcap)) - math.log(max(1, p_mcap))) / math.log(max(2, t_mcap))
                    
                    score = 1.0 - (0.30 * margin_diff + 0.30 * growth_diff + 0.20 * capex_diff + 0.20 * size_diff)
                
                scores.append((p_ticker, max(score, 0)))
            except Exception as e:
                logger.debug(f"Similarity score failed for {p_ticker}: {e}")
                continue
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scores]

    def _get_target_metrics(self, ticker: str) -> Dict:
        cache_key = ticker.upper()
        if cache_key in _METRICS_CACHE:
            return _METRICS_CACHE[cache_key]
        try:
            from project_veritas.tools.financials import get_financials_summary
            metrics = get_financials_summary(ticker)
            _METRICS_CACHE[cache_key] = metrics
            return metrics
        except:
            return {}

    def _get_target_info(self, ticker: str) -> Dict:
        try:
            info = yf.Ticker(ticker).info
            return {
                "ticker": ticker.upper(),
                "name": info.get("longName", ticker),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "market_cap": info.get("marketCap", 0)
            }
        except: return {"ticker": ticker.upper(), "name": ticker, "sector": "Unknown", "industry": "Unknown", "market_cap": 0}

    def _infer_peers_via_llm(self, ticker: str, company_name: str, industry: str, sector: str, market_cap: float, num_peers: int) -> List[str]:
        try:
            prompt = f"Identify {num_peers} US-listed valuation peers for {company_name} ({ticker}) in {industry}. Return ONLY a JSON array of tickers."
            response = self.llm.chat.completions.create(
                model="meta/llama-3.3-70b-instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            match = re.search(r'\[.*\]', response.choices[0].message.content.strip())
            if match:
                return [p.upper().strip() for p in json.loads(match.group()) if p.upper() != ticker.upper()]
        except: pass
        return []

    def _fetch_multiples_for_peers(self, peer_tickers: List[str], target_ticker: str) -> List[Dict]:
        results = []
        target_info = self._get_target_info(target_ticker)
        # Check if target is financial
        target_metrics = self._get_target_metrics(target_ticker)
        is_fin = target_metrics.get("is_financial", False)
        
        for t in peer_tickers:
            if t.upper() == target_ticker.upper(): continue
            try:
                metrics = self._get_target_metrics(t)
                if not metrics: continue
                
                if is_fin:
                    peer_type = "REFERENCE" if t.upper() in REFERENCE_FINANCIAL_PEERS else "PRIMARY"
                    results.append({
                        "ticker": t.upper(),
                        "entity_name": metrics.get("long_name", t),
                        "price_to_book": f"{metrics.get('price_to_book', 0):.2f}x",
                        "raw_pb": metrics.get("price_to_book"),
                        "pe_ratio": f"{metrics.get('pe_ratio', 0):.1f}x",
                        "raw_pe": metrics.get("pe_ratio"),
                        "roe_pct": f"{metrics.get('roe_pct', 0):.1f}%",
                        "raw_roe": metrics.get("roe_pct"),
                        "peer_type": peer_type,
                        "note": "asset-light network, reference only" if peer_type == "REFERENCE" else "",
                        "similarity_score": "N/A"
                    })
                else:
                    results.append({
                        "ticker": t.upper(),
                        "entity_name": metrics.get("long_name", t),
                        "ev_ebitda": f"{metrics.get('ev_ebitda', 0):.1f}x",
                        "raw_ev_ebitda": metrics.get("ev_ebitda"),
                        "ev_rev": f"{metrics.get('ev_rev', 0):.1f}x",
                        "rev_growth": f"{metrics.get('revenue_growth_pct', 0):.1f}%",
                        "ebitda_margin": f"{metrics.get('ebitda_adj_M', 0) / metrics.get('revenue_ttm_M', 1) * 100:.1f}%",
                        "similarity_score": "N/A"
                    })
            except: continue
        return results

    def _load_all_capiq_files(self) -> pd.DataFrame:
        if not os.path.exists(self.capiq_dir): return pd.DataFrame()
        all_data = []
        for root, dirs, files in os.walk(self.capiq_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    if filename.endswith(('.xlsx', '.xls')):
                        df = pd.read_excel(filepath)
                        all_data.append(df)
                    elif filename.endswith('.csv'):
                        df = pd.read_csv(filepath)
                        all_data.append(df)
                except: continue
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    def _search_capiq_by_industry(self, target_ticker: str, target_industry: str, industry_group: str, target_sector: str) -> List[str]:
        # Simplified for now, just searching company_name/industry columns
        if self.capiq_data.empty: return []
        df = self.capiq_data
        matches = []
        # Look for industry keywords in any string column
        for col in df.select_dtypes(include=[object]).columns:
            mask = df[col].astype(str).str.contains(target_industry.split(' ')[0], case=False, na=False)
            matches.extend(df[mask]['ticker'].dropna().tolist() if 'ticker' in df.columns else [])
        return list(set(matches))

    @staticmethod
    def calculate_premium_discount(target: Dict, peers: List[Dict]) -> Dict:
        """
        FIX 3: Independent Fair Value Multiple.
        Derives a fair multiple based on the target's specific economics relative to its peer group.
        """
        is_fin = target.get("is_financial", False)
        if not peers:
            return {"implied_fair_multiple": 1.0 if is_fin else 10.0, "narrative": "No peers found; using default conservative multiple."}

        # 1. Calculate Median Peer Multiple
        if is_fin:
            peer_multiples = [
                p['raw_pb'] for p in peers
                if p.get('peer_type', 'PRIMARY') == 'PRIMARY' and p.get('raw_pb') and p['raw_pb'] > 0
            ]
            default_mult = 1.0
            mult_name = "P/Book"
        else:
            peer_multiples = [p['raw_ev_ebitda'] for p in peers if p.get('raw_ev_ebitda') and p['raw_ev_ebitda'] > 0]
            default_mult = 10.0
            mult_name = "EV/EBITDA"

        if not peer_multiples:
            return {"implied_fair_multiple": default_mult, "narrative": "No valid peer multiples; using default."}
            
        median_mult = sorted(peer_multiples)[len(peer_multiples)//2]
        
        # 2. Performance-Based Adjustments
        if is_fin:
            # ROE Adjustment for Banks
            t_roe = target.get("roe_pct", 0) or 0
            peer_roes = []
            for p in peers:
                r_str = p.get("roe_pct", "0%").replace('%', '')
                try: peer_roes.append(float(r_str))
                except: pass
            
            avg_peer_roe = sum(peer_roes) / len(peer_roes) if peer_roes else t_roe
            roe_spread = t_roe - avg_peer_roe
            
            # Adjustment: +0.1x P/Book for every 1% ROE spread
            adj_mult = (roe_spread / 1.0) * 0.1
            fair_mult = median_mult + adj_mult
            fair_mult = max(0.5, min(fair_mult, 4.0)) # Sanity for banks
            
            premium_pct = ((fair_mult - median_mult) / median_mult) * 100 if median_mult > 0 else 0
            narrative = (
                f"Target is assigned a {abs(premium_pct):.1f}% {'premium' if premium_pct > 0 else 'discount'} "
                f"to median peer {mult_name} ({median_mult:.2f}x) due to its "
                f"{'superior' if roe_spread > 0 else 'inferior'} ROE profile ({t_roe:.1f}% vs {avg_peer_roe:.1f}%)."
            )
        else:
            # Growth Adjustment (Weight: 50%)
            t_growth = target.get("revenue_growth_pct", 0) or 0
            peer_growths = []
            for p in peers:
                g_str = p.get("rev_growth", "0%").replace('%', '')
                try: peer_growths.append(float(g_str))
                except: pass
            
            avg_peer_growth = sum(peer_growths) / len(peer_growths) if peer_growths else t_growth
            growth_spread = t_growth - avg_peer_growth
            
            # Margin Adjustment (Weight: 50%)
            t_rev = target.get("revenue_ttm_M", 1) or 1
            t_margin = (target.get("ebitda_adj_M", 0) / t_rev) * 100
            peer_margins = []
            for p in peers:
                m_str = p.get("ebitda_margin", "0%").replace('%', '')
                try: peer_margins.append(float(m_str))
                except: pass
            
            avg_peer_margin = sum(peer_margins) / len(peer_margins) if peer_margins else t_margin
            margin_spread = t_margin - avg_peer_margin
            
            adj_mult = 0
            adj_mult += (growth_spread / 5.0) * 0.5
            adj_mult += (margin_spread / 5.0) * 0.5
            
            fair_mult = median_mult + adj_mult
            fair_mult = min(fair_mult, median_mult * 1.5, 40.0)
            fair_mult = max(fair_mult, median_mult * 0.7, 5.0)
            
            premium_pct = ((fair_mult - median_mult) / median_mult) * 100 if median_mult > 0 else 0
            narrative = (
                f"Target {'commands' if premium_pct > 0 else 'is assigned'} a "
                f"{abs(premium_pct):.1f}% {'premium' if premium_pct > 0 else 'discount'} "
                f"to median peer {mult_name} ({median_mult:.1f}x) due to its "
                f"{'superior' if growth_spread > 0 else 'inferior'} growth profile ({t_growth:.1f}% vs {avg_peer_growth:.1f}%) "
                f"and {'higher' if margin_spread > 0 else 'lower'} EBITDA margins ({t_margin:.1f}% vs {avg_peer_margin:.1f}%)."
            )
        
        return {
            "implied_fair_multiple": round(fair_mult, 2),
            "median_peer_multiple": round(median_mult, 2),
            "premium_pct": round(premium_pct, 1),
            "narrative": narrative
        }
