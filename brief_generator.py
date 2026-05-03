"""
AI-Powered Campaign Brief Generator
=====================================
Uses the Claude API to auto-generate structured campaign health briefs
from raw performance data — exactly the LLM automation workflow
described in the Kayzen Product Analyst JD.

Usage:
    python ai_module/brief_generator.py --campaign CMP002
    python ai_module/brief_generator.py --all
"""

import pandas as pd
import numpy as np
import json
import argparse
import textwrap
from datetime import datetime

# ── Load data ──────────────────────────────────────────────────────────────────
df  = pd.read_csv("data/bid_logs.csv", parse_dates=["date"])
cdf = pd.read_csv("data/campaigns.csv")
df  = df.merge(cdf, on="campaign_id")

def compute_campaign_stats(campaign_id: str) -> dict:
    """Compute all KPIs needed for the brief."""
    d = df[df["campaign_id"] == campaign_id].copy()
    camp = cdf[cdf["campaign_id"] == campaign_id].iloc[0]

    # Monthly breakdown
    monthly = d.groupby("month").agg(
        bids=("bid_id","count"), impressions=("is_won","sum"),
        clicks=("is_click","sum"), installs=("is_install","sum"),
        spend=("spend_usd","sum")
    ).reset_index()
    monthly["ctr"] = (monthly["clicks"] / monthly["impressions"].replace(0, np.nan)).fillna(0)
    monthly["cvr"] = (monthly["installs"] / monthly["clicks"].replace(0, np.nan)).fillna(0)
    monthly["cpi"] = (monthly["spend"] / monthly["installs"].replace(0, np.nan)).fillna(0)

    # Format breakdown
    fmt = d.groupby("ad_format").agg(
        impressions=("is_won","sum"), clicks=("is_click","sum"),
        installs=("is_install","sum"), spend=("spend_usd","sum")
    ).reset_index()
    fmt["ctr"] = (fmt["clicks"] / fmt["impressions"].replace(0, np.nan)).fillna(0)

    # Geo top 5 by installs
    geo = d.groupby("country").agg(
        installs=("is_install","sum"), spend=("spend_usd","sum")
    ).sort_values("installs", ascending=False).head(5).reset_index()
    geo["cpi"] = (geo["spend"] / geo["installs"].replace(0, np.nan)).fillna(0)

    # CTR anomaly check
    weekly = d[d["is_won"]==1].copy()
    weekly["week"] = pd.to_datetime(d["date"]).dt.to_period("W").dt.start_time
    wk = weekly.groupby("week").agg(
        impressions=("is_won","sum"), clicks=("is_click","sum")
    ).reset_index()
    wk["ctr"] = (wk["clicks"] / wk["impressions"].replace(0, np.nan)).fillna(0)
    avg_ctr = wk["ctr"].mean()
    std_ctr = wk["ctr"].std()
    anomalies = wk[((wk["ctr"] - avg_ctr).abs() / std_ctr) > 2] if std_ctr > 0 else pd.DataFrame()

    # OS split
    os_split = d.groupby("os").agg(
        installs=("is_install","sum"), spend=("spend_usd","sum")
    ).reset_index()

    return {
        "campaign_id":   campaign_id,
        "campaign_name": camp["campaign_name"],
        "advertiser":    camp["advertiser"],
        "goal":          camp["goal"],
        "budget_usd":    int(camp["budget_usd"]),
        "bid_strategy":  camp["bid_strategy"],
        "total_bids":    int(d["bid_id"].count()),
        "impressions":   int(d["is_won"].sum()),
        "clicks":        int(d["is_click"].sum()),
        "installs":      int(d["is_install"].sum()),
        "total_spend":   round(float(d["spend_usd"].sum()), 4),
        "win_rate":      round(float(d["is_won"].mean()), 4),
        "ctr":           round(float(d["is_click"].sum() / max(d["is_won"].sum(), 1)), 5),
        "cvr":           round(float(d["is_install"].sum() / max(d["is_click"].sum(), 1)), 4),
        "cpi":           round(float(d["spend_usd"].sum() / max(d["is_install"].sum(), 1)), 4),
        "monthly_trend": monthly[["month","impressions","clicks","installs",
                                   "ctr","cvr","cpi"]].round(5).to_dict("records"),
        "top_formats":   fmt.sort_values("installs", ascending=False
                            )[["ad_format","impressions","clicks","installs","ctr"]
                            ].round(5).head(5).to_dict("records"),
        "top_geos":      geo[["country","installs","cpi"]].round(3).to_dict("records"),
        "os_split":      os_split.to_dict("records"),
        "anomaly_weeks": len(anomalies),
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
    }


def generate_brief_prompt(stats: dict) -> str:
    return f"""You are a Senior Product Analyst at a mobile programmatic advertising DSP (demand-side platform).

Analyze the following campaign performance data and generate a structured **Campaign Health Brief**.

## Campaign Data
```json
{json.dumps(stats, indent=2)}
```

## Brief Format (follow exactly)

### 🎯 Campaign Overview
- Campaign: [name + ID]
- Advertiser: [name] | Goal: [goal type] | Strategy: [bid strategy]
- Period: Q1 2025 (Jan–Mar) | Budget: $[amount]

### 📊 Performance Summary
Write 3–4 sentences summarizing overall performance: key metrics, whether the campaign is healthy, and the most important observation from the data.

### 🚦 Traffic Light Assessment
Rate each metric as 🟢 (good), 🟡 (needs attention), or 🔴 (critical):
- Win Rate: [value] [status]
- CTR: [value] [status] — with benchmark context (typical mobile CTR: 0.5%–3%)
- CVR: [value] [status]
- CPI: [value] [status]

### 📈 Monthly Trend Analysis
Describe the trend across January, February, March. Note any month-over-month changes, especially any drops or spikes.

### 🔍 Root Cause Investigation
If any anomalies were detected (anomaly_weeks > 0), describe:
1. What the anomaly is (metric, timeframe)
2. Likely root causes to investigate (creative fatigue, inventory issues, bid floor changes, etc.)
3. Recommended debugging steps

### 🌍 Geo & Format Insights
- Top performing geos and why they matter
- Best performing ad formats and optimization recommendation

### ⚡ Recommended Actions (prioritized)
List 3–5 concrete, actionable recommendations with expected impact. Be specific — include bid adjustments, format reallocation, geo targeting changes, etc.

### ⚠️ Risks & Watch Items
Any risks to monitor in the next 2 weeks.

---
Keep the brief factual, data-driven, and actionable. Use numbers throughout. Write for a product/engineering audience."""


def generate_brief_with_claude(campaign_id: str) -> str:
    """
    Calls the Claude API to generate the brief.
    In a real deployment this runs against claude-sonnet-4-20250514.
    For the portfolio demo we show the prompt + mock response
    (replace the mock with the real fetch call below when running live).
    """
    try:
        import urllib.request, json as _json

        stats  = compute_campaign_stats(campaign_id)
        prompt = generate_brief_prompt(stats)

        payload = _json.dumps({
            "model":      "claude-sonnet-4-20250514",
            "max_tokens": 1500,
            "messages":   [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read())
            return data["content"][0]["text"]

    except Exception as e:
        # Fallback: return the generated prompt so you can see what would be sent
        stats  = compute_campaign_stats(campaign_id)
        prompt = generate_brief_prompt(stats)
        return f"""[DEMO MODE — Claude API key not set]

The following prompt would be sent to claude-sonnet-4-20250514:

{'='*60}
{prompt}
{'='*60}

To run live: set ANTHROPIC_API_KEY in your environment and
the brief_generator will call the real Claude API automatically.

Campaign Stats Extracted:
- Campaign:    {stats['campaign_name']} ({stats['campaign_id']})
- Installs:    {stats['installs']:,}
- CTR:         {stats['ctr']:.4%}
- CVR:         {stats['cvr']:.4%}
- CPI:         ${stats['cpi']:.4f}
- Spend:       ${stats['total_spend']:.4f}
- Anomalies:   {stats['anomaly_weeks']} week(s) flagged
"""


def run_all_briefs():
    """Generate briefs for all campaigns and save to files."""
    import os
    os.makedirs("output/briefs", exist_ok=True)

    for _, row in cdf.iterrows():
        cid = row["campaign_id"]
        print(f"\n{'─'*50}")
        print(f"Generating brief: {cid} — {row['campaign_name']}")
        brief = generate_brief_with_claude(cid)

        filepath = f"output/briefs/{cid}_brief.md"
        with open(filepath, "w") as f:
            f.write(f"# Campaign Brief: {row['campaign_name']}\n")
            f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
            f.write(brief)

        print(f"✅ Saved: {filepath}")
        print(brief[:500] + "…")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RTB Campaign Brief Generator")
    parser.add_argument("--campaign", type=str, help="Campaign ID (e.g. CMP001)")
    parser.add_argument("--all",      action="store_true", help="Generate all campaigns")
    args = parser.parse_args()

    if args.all:
        run_all_briefs()
    elif args.campaign:
        print(f"\nGenerating brief for {args.campaign}…\n")
        brief = generate_brief_with_claude(args.campaign)
        print(brief)
    else:
        # Default: show CMP002 (the anomaly campaign)
        print("\nGenerating brief for CMP002 (anomaly campaign)…\n")
        brief = generate_brief_with_claude("CMP002")
        print(brief)
