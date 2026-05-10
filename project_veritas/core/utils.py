from __future__ import annotations

from typing import Any, Dict, Optional


def fmt_number(value: Any, num_type: str) -> str:
    """Format numbers consistently for prompts and reports."""
    if value is None:
        return "N/A"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if num_type == "pct":
        return f"{value:+.1f}%" if value != 0 else "0.0%"
    if num_type == "multiple":
        return f"{value:.1f}x"
    if num_type == "price":
        return f"${value:,.2f}"
    if num_type == "money":
        # Assumes input is in Millions (USD M or Rs Cr)
        if abs(value) >= 1_000:
            return f"${value / 1_000:,.1f}B"
        return f"${value:,.1f}M"
    if num_type == "ratio":
        return f"{value:.2f}"
    return str(value)


def compute_entry_strategy(current_price: Optional[float], implied_fair_value: Optional[float], verdict: str) -> Dict[str, Any]:
    """Create an internally consistent entry plan around fair value."""
    if not current_price or not implied_fair_value:
        return {
            "status": "VALUATION DATA UNAVAILABLE",
            "action": "N/A - valuation computation error",
            "fair_value": implied_fair_value,
            "current_price": current_price,
        }

    verdict = verdict.upper()
    if current_price < implied_fair_value:
        discount_pct = (implied_fair_value - current_price) / implied_fair_value * 100
        
        # Refactor Entry Strategy (Problem 2)
        if "CAUTION" in verdict or "HOLD" in verdict:
            status = "BELOW FAIR VALUE - PATIENT ACCUMULATION"
            action = f"ACCUMULATE below ${implied_fair_value:,.2f} (current discount: {discount_pct:.0f}%)"
        else:
            status = "BELOW FAIR VALUE - ATTRACTIVE ENTRY"
            action = f"BUY at current levels ({discount_pct:.0f}% below fair value)"

        return {
            "status": status,
            "fair_value": implied_fair_value,
            "current_price": current_price,
            "discount": f"{discount_pct:.1f}%",
            "max_entry": implied_fair_value,
            "accumulate_below": current_price * 0.95,
            "action": action,
        }

    premium_pct = (current_price - implied_fair_value) / implied_fair_value * 100
    return {
        "status": "ABOVE FAIR VALUE - WAIT FOR PULLBACK",
        "fair_value": implied_fair_value,
        "current_price": current_price,
        "premium": f"{premium_pct:.1f}%",
        "recommended_entry": implied_fair_value * 0.90,
        "aggressive_entry": implied_fair_value * 1.05,
        "walk_away_above": implied_fair_value * 1.25,
        "action": f"WAIT - currently {premium_pct:.0f}% above fair value",
    }


def sector_display(financial_data: Dict[str, Any]) -> str:
    sector = financial_data.get("sector") or "Unknown Sector"
    industry = financial_data.get("industry") or "Unknown Industry"
    return f"{sector} | {industry}"
