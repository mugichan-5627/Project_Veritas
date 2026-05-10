from typing import Dict, List, Tuple
from dataclasses import dataclass, field

@dataclass
class ValidationCheck:
    name: str
    passed: bool
    severity: str  # CRITICAL, WARNING, INFO
    message: str

@dataclass 
class ValidationReport:
    checks: List[ValidationCheck] = field(default_factory=list)
    
    @property
    def passed_all_critical(self) -> bool:
        return not any(c.severity == "CRITICAL" and not c.passed for c in self.checks)
    
    @property
    def confidence(self) -> str:
        criticals = sum(1 for c in self.checks if c.severity == "CRITICAL" and not c.passed)
        warnings = sum(1 for c in self.checks if c.severity == "WARNING" and not c.passed)
        if criticals > 0:
            return "LOW"
        elif warnings > 2:
            return "MEDIUM"
        return "HIGH"
    
    def get_quality_flags(self) -> List[str]:
        """Returns list of failed check messages for UI display."""
        return [c.message for c in self.checks if not c.passed]
    
    def print_summary(self):
        print(f"\n  {'-'*50}")
        print(f"  DATA VALIDATION REPORT")
        print(f"  {'-'*50}")
        for c in self.checks:
            icon = "[PASS]" if c.passed else ("[FAIL]" if c.severity == "CRITICAL" else "[WARN]")
            print(f"  {icon} {c.name}: {c.message}")
        print(f"  Confidence: {self.confidence}\n")

# Industry-specific margin expectations
INDUSTRY_MARGINS = {
    "Internet Retail": {"ebitda_low": 5, "ebitda_high": 30, "fcf_low": -5, "fcf_high": 20},
    "Software—Infrastructure": {"ebitda_low": 15, "ebitda_high": 55, "fcf_low": 10, "fcf_high": 45},
    "Software—Application": {"ebitda_low": 15, "ebitda_high": 50, "fcf_low": 10, "fcf_high": 40},
    "Semiconductors": {"ebitda_low": 20, "ebitda_high": 55, "fcf_low": 5, "fcf_high": 40},
    "Consumer Electronics": {"ebitda_low": 15, "ebitda_high": 35, "fcf_low": 10, "fcf_high": 30},
    "Information Technology Services": {"ebitda_low": 10, "ebitda_high": 35, "fcf_low": 5, "fcf_high": 25},
    "default": {"ebitda_low": 5, "ebitda_high": 60, "fcf_low": -10, "fcf_high": 50},
}

# Ticker-specific magnitude checks (Fix 2)
KNOWN_REVENUES = {
    "AMZN": (550000, 750000), # USD M
    "AAPL": (350000, 450000),
    "MSFT": (200000, 300000),
    "GOOGL": (250000, 350000),
    "NVDA": (50000, 180000),
}

def normalize_industry(raw_industry: str) -> str:
    """Map yfinance industry strings to our standard names."""
    if not raw_industry:
        return "default"
    
    MAPPING = {
        "internet retail": "Internet Retail",
        "software - infrastructure": "Software—Infrastructure",
        "software—infrastructure": "Software—Infrastructure",
        "software - application": "Software—Application",
        "semiconductors": "Semiconductors",
        "consumer electronics": "Consumer Electronics",
        "information technology services": "Information Technology Services",
        "specialty retail": "Internet Retail", # Some overlap or misclassification by yf
    }
    return MAPPING.get(raw_industry.lower(), "default")


def validate_financials(data: Dict) -> ValidationReport:
    """
    Universal financial validation.
    Adapts margin expectations based on industry.
    """
    report = ValidationReport()
    
    revenue = data.get("revenue_ttm_M")
    ebitda = data.get("ebitda_reported_M")
    adj_ebitda = data.get("ebitda_adj_M")
    sbc = data.get("sbc_M", 0)
    ev_ebitda = data.get("ev_ebitda")
    growth = data.get("revenue_growth_pct")
    fcf_margin = data.get("fcf_margin_pct")
    market_cap = data.get("market_cap_M")
    raw_industry = data.get("industry", "default")
    
    industry = normalize_industry(raw_industry)
    margins = INDUSTRY_MARGINS.get(industry, INDUSTRY_MARGINS["default"])
    
    # ── Check 1: Revenue is not null ──
    if revenue is None or revenue <= 0:
        report.checks.append(ValidationCheck(
            "Revenue", False, "CRITICAL", "Revenue is NULL or negative — cannot proceed"))
        return report  # Can't validate further without revenue
    else:
        # Magnitude check
        low, high = KNOWN_REVENUES.get(data.get("ticker", ""), (0, 1e12))
        if revenue < low or revenue > high:
            report.checks.append(ValidationCheck(
                "Revenue", False, "WARNING", 
                f"${revenue:,.0f}M outside typical range (${low:,.0f}M - ${high:,.0f}M)"))
        else:
            report.checks.append(ValidationCheck(
                "Revenue", True, "INFO", f"${revenue:,.0f}M"))
    
    # ── Check 2: EBITDA margin in range ──
    if ebitda and revenue:
        margin = (ebitda / revenue) * 100
        low, high = margins["ebitda_low"], margins["ebitda_high"]
        if margin < low - 10 or margin > high + 15:
            report.checks.append(ValidationCheck(
                "EBITDA Margin", False, "CRITICAL",
                f"{margin:.1f}% outside expected range {low}-{high}% for {industry}"))
        elif margin < low or margin > high:
            report.checks.append(ValidationCheck(
                "EBITDA Margin", False, "WARNING",
                f"{margin:.1f}% slightly outside typical {low}-{high}% for {industry}"))
        else:
            report.checks.append(ValidationCheck(
                "EBITDA Margin", True, "INFO", f"{margin:.1f}% (within industry range)"))
    
    # ── Check 3: SBC direction (adj EBITDA < reported) ──
    if adj_ebitda and ebitda:
        if adj_ebitda > ebitda:
            report.checks.append(ValidationCheck(
                "SBC Direction", False, "CRITICAL",
                f"Adj EBITDA (${adj_ebitda:,.0f}M) > Reported (${ebitda:,.0f}M) — SBC added instead of subtracted"))
        else:
            report.checks.append(ValidationCheck(
                "SBC Direction", True, "INFO",
                f"Correctly subtracted: ${ebitda:,.0f}M - ${sbc:,.0f}M = ${adj_ebitda:,.0f}M"))
    
    # ── Check 4: EV/EBITDA bounds ──
    if ev_ebitda:
        if ev_ebitda < 0:
            report.checks.append(ValidationCheck(
                "EV/EBITDA", False, "CRITICAL", f"{ev_ebitda:.1f}x is negative"))
        elif ev_ebitda > 150:
            report.checks.append(ValidationCheck(
                "EV/EBITDA", False, "WARNING", f"{ev_ebitda:.1f}x exceeds typical maximum"))
        else:
            report.checks.append(ValidationCheck(
                "EV/EBITDA", True, "INFO", f"{ev_ebitda:.1f}x"))
    
    # ── Check 5: Growth plausibility ──
    if growth is not None:
        if revenue > 100_000 and growth > 40:
            report.checks.append(ValidationCheck(
                "Growth Rate", False, "WARNING",
                f"{growth:.1f}% growth seems high for a ${revenue/1000:.0f}B company"))
        elif growth > 100:
            report.checks.append(ValidationCheck(
                "Growth Rate", False, "WARNING",
                f"{growth:.1f}% — verify this isn't a base effect"))
        else:
            report.checks.append(ValidationCheck(
                "Growth Rate", True, "INFO", f"{growth:.1f}%"))
    
    # ── Check 6: P/S Ratio sanity ──
    if market_cap and revenue:
        ps = market_cap / revenue
        if ps > 50:
            report.checks.append(ValidationCheck(
                "P/S Ratio", False, "CRITICAL",
                f"P/S of {ps:.1f}x is extreme — possible revenue undercount"))
        elif ps > 25:
            report.checks.append(ValidationCheck(
                "P/S Ratio", False, "WARNING", f"P/S of {ps:.1f}x is elevated"))
        else:
            report.checks.append(ValidationCheck(
                "P/S Ratio", True, "INFO", f"P/S of {ps:.1f}x"))
    
    # ── Check 7: FCF Margin ──
    if fcf_margin is not None:
        low, high = margins["fcf_low"], margins["fcf_high"]
        if fcf_margin < low - 15:
            report.checks.append(ValidationCheck(
                "FCF Margin", False, "WARNING",
                f"{fcf_margin:.1f}% deeply negative — heavy capex period?"))
        elif fcf_margin < 0:
            report.checks.append(ValidationCheck(
                "FCF Margin", False, "WARNING",
                f"{fcf_margin:.1f}% — negative FCF, verify capex cycle"))
        else:
            report.checks.append(ValidationCheck(
                "FCF Margin", True, "INFO", f"{fcf_margin:.1f}%"))
    
    return report
