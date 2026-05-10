import os
import json
from datetime import datetime
from pathlib import Path
from project_veritas.core.utils import fmt_number

class ReportGenerator:
    def __init__(self, output_dir="reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_html(self, pipeline_results):
        """Generates a premium HTML investment memo."""
        ticker = pipeline_results["deal_context"]["ticker"]
        verdict = pipeline_results["final_verdict"]
        context = pipeline_results["deal_context"]
        
        # Determine Color Theme
        decision = verdict.get("decision", "HOLD")
        theme_color = "#22c55e" if decision.startswith("APPROVE") else ("#eab308" if decision == "HOLD" else "#ef4444")
        
        # Safe extraction
        fin_data = context.get("financial_data", {})
        val_data = context.get("valuation", {})
        market_data = context.get("market_intel", {})
        forensics_data = context.get("forensics", {})

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Investment Memo: {ticker}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: {theme_color};
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f8fafc;
            --muted: #94a3b8;
            --border: #334155;
        }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border);
            padding-bottom: 20px;
            margin-bottom: 40px;
        }}
        .verdict-badge {{
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 700;
            text-transform: uppercase;
            background-color: var(--primary);
            color: #fff;
        }}
        h1, h2, h3 {{ margin-top: 0; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }}
        .full-width {{
            grid-column: 1 / -1;
        }}
        .card {{
            background: var(--card);
            padding: 24px;
            border-radius: 12px;
            border: 1px solid var(--border);
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }}
        .stat-item {{
            padding: 10px;
            border-bottom: 1px solid var(--border);
        }}
        .stat-label {{ color: var(--muted); font-size: 0.85rem; }}
        .stat-value {{ font-weight: 600; font-size: 1.1rem; }}
        
        .section-title {{
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--primary);
            margin-bottom: 15px;
            font-weight: 700;
        }}
        .bullet-list {{
            margin: 0;
            padding-left: 20px;
        }}
        .bullet-list li {{ margin-bottom: 12px; font-size: 0.95rem; }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid var(--border);
        }}
        th {{ color: var(--muted); font-weight: 400; font-size: 0.85rem; }}
        
        .footer {{
            margin-top: 60px;
            text-align: center;
            color: var(--muted);
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1 style="margin-bottom: 5px;">Project Veritas Memo</h1>
                <p style="color: var(--muted); margin: 0;">{context.get("company_name", ticker)} ({ticker}) | {context.get("industry", "N/A")}</p>
            </div>
            <div class="verdict-badge">{decision}</div>
        </header>

        <div class="grid">
            <div class="card">
                <div class="section-title">Investment Summary</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-label">Current Price</div>
                        <div class="stat-value">{fmt_number(verdict.get("current_price"), "price")}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Fair Value Price</div>
                        <div class="stat-value">{fmt_number(verdict.get("fair_price"), "price")}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Implied Return</div>
                        <div class="stat-value" style="color: {theme_color}">{fmt_number(verdict.get("implied_return_pct"), "pct")}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Conviction Level</div>
                        <div class="stat-value">{verdict.get("conviction", "N/A")}</div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="section-title">Forensic Profile</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-label">Forensic Score</div>
                        <div class="stat-value">{forensics_data.get("forensic_score", "N/A")}/100</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Quality of Earnings</div>
                        <div class="stat-value">{forensics_data.get("quality_of_earnings", "N/A")}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Efficiency Ratio</div>
                        <div class="stat-value">{fmt_number(market_data.get("efficiency_ratio"), "pct")}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">WACC (CoE)</div>
                        <div class="stat-value">{fmt_number(val_data.get("wacc_pct"), "pct")}</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="section-title">What Must Go Right (Bull Case)</div>
                <ul class="bullet-list">
                    {"".join(f"<li>{r}</li>" for r in verdict.get("strategic_outlook", {}).get("what_must_go_right", ["Upside catalysts realization"]))}
                </ul>
            </div>
            <div class="card">
                <div class="section-title">What Must Go Wrong (Bear Case)</div>
                <ul class="bullet-list">
                    {"".join(f"<li>{r}</li>" for r in verdict.get("strategic_outlook", {}).get("what_must_go_wrong", ["Downside risk crystallization"]))}
                </ul>
            </div>
        </div>

        <div class="card" style="margin-bottom: 20px;">
            <div class="section-title">IC Reasoning & Rationale</div>
            <ul class="bullet-list">
                {"".join(f"<li>{r}</li>" for r in verdict.get("reasoning", []))}
            </ul>
        </div>

        <div class="grid">
            <div class="card">
                <div class="section-title">Key Risks & Mitigation</div>
                <ul class="bullet-list">
                    {"".join(f"<li>{r}</li>" for r in verdict.get("risks", []))}
                </ul>
            </div>
            <div class="card">
                <div class="section-title">Precedent Transactions</div>
                <table>
                    <thead>
                        <tr>
                            <th>Target</th>
                            <th>Date</th>
                            <th>Multiple</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(f"<tr><td>{t.get('target', 'N/A')}</td><td>{t.get('date', 'N/A')}</td><td>{t.get('ev_ebitda', 'N/A')}</td></tr>" for t in market_data.get("precedent_transactions", [])[:4])}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card">
            <div class="section-title">Mathematical Rationale</div>
            <p style="font-size: 0.9rem; color: var(--muted); font-family: monospace;">{forensics_data.get("math_agent_rationale", "No math data available.")}</p>
        </div>

        <div class="footer">
            CONFIDENTIAL - PROJECT VERITAS INTERNAL USE ONLY - GENERATED ON {context.get("timestamp", datetime.now().isoformat())}
        </div>
    </div>
</body>
</html>
"""
        filename = f"memo_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        return str(filepath)
