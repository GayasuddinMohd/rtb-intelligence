## 🔴 LIVE DEMO: https://rtb-intelligence.onrender.com


# ◈ RTB Campaign Intelligence Dashboard

> A production-grade programmatic advertising analytics system built for a mobile DSP (demand-side platform). Analyzes 500K+ bid-level events across the full RTB funnel — from auction entry to install — with AI-powered campaign briefs, statistical anomaly detection, and actionable optimization insights.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![Plotly Dash](https://img.shields.io/badge/Plotly_Dash-Interactive_Dashboard-orange?style=flat-square)
![SQL](https://img.shields.io/badge/SQL-10_Production_Queries-green?style=flat-square)
![Claude API](https://img.shields.io/badge/Claude_API-AI_Brief_Generator-purple?style=flat-square)

---

## 🎯 Project Overview

This project simulates the analytical work of a **Product Analyst at a mobile DSP** — the exact role Kayzen describes. It covers all three pillars of the JD:

| JD Requirement | This Project |
|---|---|
| Deep SQL on large event datasets | 10 production-grade queries: CTEs, window functions, Z-scores, pivot tables |
| Product debugging & root cause | Injected CTR anomaly in CMP002; full multi-dimensional investigation |
| LLM automation (Claude/GPT) | `brief_generator.py` auto-generates structured campaign health briefs |
| BI dashboards | Interactive Dash dashboard with 7 chart types + real-time filters |
| RTB/AdTech domain expertise | Full DSP simulation: bid requests, win rates, CPM, CPI funnel |
| Funnel & user behavior analysis | Bid → Win → Click → Install with CTR/CVR/CPI breakdowns |

---

## 🗂️ Project Structure

```
rtb-intelligence/
├── data/
│   ├── generate_data.py       # Simulates 500K RTB bid log events
│   ├── bid_logs.csv           # Generated: 500,000 bid-level events
│   ├── campaigns.csv          # 8 campaign configurations
│   └── publishers.csv         # 200 publishers with quality scores
│
├── sql/
│   └── rtb_analytics_queries.sql   # 10 production-grade SQL queries
│
├── dashboard/
│   └── app.py                 # Plotly Dash interactive dashboard
│
├── ai_module/
│   └── brief_generator.py     # Claude API campaign brief generator
│
├── notebooks/
│   └── rtb_analysis.ipynb     # Deep-dive analytical narrative
│
└── README.md
```

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/yourusername/rtb-intelligence.git
cd rtb-intelligence
pip install -r requirements.txt
```

### 2. Generate the dataset

```bash
python data/generate_data.py
```

Output: `500,000 bid events` across 8 campaigns, 200 publishers, 15 countries, Q1 2025.

### 3. Run the dashboard

```bash
python dashboard/app.py
# Open: http://localhost:8050
```

### 4. Generate an AI campaign brief

```bash
# Single campaign (the anomaly campaign)
python ai_module/brief_generator.py --campaign CMP002

# All campaigns
python ai_module/brief_generator.py --all
```

With your `ANTHROPIC_API_KEY` set, this calls `claude-sonnet-4-20250514` to generate a structured markdown brief including performance assessment, anomaly investigation, and prioritized recommendations.

### 5. Run the Jupyter notebook

```bash
jupyter notebook notebooks/rtb_analysis.ipynb
```

---

## 📊 Dashboard Features

The Dash dashboard includes:

- **KPI Row** — Bids, Impressions, Clicks, Installs, Spend, CPI, eCPM (live-filtered)
- **Conversion Funnel** — Full bid-to-install funnel with drop-off rates
- **Daily Trend** — Bar + 7-day rolling CTR with dual-axis
- **Anomaly Chart** — Weekly CTR across all campaigns with February anomaly highlighted in red
- **Geo Heatmap** — CPI by country (choropleth)
- **Format Efficiency** — Win rate / CTR / CVR by ad format
- **Exchange Win Rate** — Competitive analysis across SSPs
- **Install Heatmap** — Day × hour conversion rate matrix

Filters: Campaign, OS (Android/iOS), Ad Format — all charts update in sync.

---

## 🔍 SQL Query Library

`sql/rtb_analytics_queries.sql` contains 10 production-ready queries:

| # | Query | Techniques Used |
|---|-------|-----------------|
| Q1 | Campaign Funnel Summary | CTE, JOIN, aggregations, RANK() |
| Q2 | Daily Trend + 7-Day Rolling Avg | Window functions, ROWS BETWEEN |
| Q3 | CTR Anomaly Detection (Z-Score) | CTE chain, STDDEV, Z-score math |
| Q4 | Publisher Quality Analysis | CTE, NTILE(), HAVING |
| Q5 | Geo × OS Performance Breakdown | Multi-dim aggregation, RANK() |
| Q6 | Hour-of-Day Heatmap | GROUP BY multi-dim |
| Q7 | Ad Format Efficiency Matrix | CTE, RANK() |
| Q8 | Budget Pacing Analysis | Window SUM, CASE, rolling AVG |
| Q9 | Exchange Competitiveness Report | Conditional aggregation |
| Q10 | Root-Cause Debug — CTR Drop | Pivot via MAX(CASE WHEN), CTE chain |

---

## 🤖 AI Brief Generator

The `brief_generator.py` module demonstrates LLM-powered automation:

1. **Extracts** all relevant KPIs and trend data from the dataset
2. **Constructs** a structured prompt with campaign context, monthly trends, anomaly flags, geo and format breakdowns
3. **Calls** `claude-sonnet-4-20250514` via the Anthropic API
4. **Returns** a markdown brief with traffic-light assessment, root-cause analysis, and prioritized recommendations

This is exactly the "automate recurring analyses and data briefs" workflow described in the Kayzen JD.

---

## 🔍 The Anomaly: CMP002 February CTR Drop

A 70% CTR drop was deliberately injected into Campaign CMP002 (Gaming Retargeting) during February 2025. The analytical workflow to detect and investigate it:

1. **Detection**: Z-score > 2 flagged in weekly CTR monitoring (Q3 in SQL library)
2. **Isolation**: Pivoted CTR by month × format × geo to find the affected dimensions
3. **Finding**: Drop is **uniform across all formats and countries** — ruling out creative fatigue or geo-specific bid floor issues
4. **Hypothesis**: Audience list corruption or click tracking pixel failure in February
5. **Resolution path**: Cross-reference ad server click logs with MMP (AppsFlyer/Adjust) data for discrepancy

This mirrors the "go deep into complex customer-facing issues, identify root causes in data" requirement.

---

## 📈 Key Analytical Findings

| Finding | Data Point | Action |
|---------|-----------|--------|
| Rewarded video is the most efficient format | Lowest CPI, highest CVR (18%) | Shift budget from banners |
| IN + Android is top geo-OS combo by CPI | CPI ~40% below US | Increase bid caps |
| Publisher quality score negatively correlates with CPI | r ≈ -0.3 | Blocklist score < 4 |
| Peak install window: 18:00–22:00 UTC | +35% conversion rate vs off-peak | Enable dayparting |
| CMP002 CTR recovered in March | Feb anomaly confirmed as transient | Audit tracking stack |

---

## 🛠️ Tech Stack

- **Python 3.10+** — core analysis
- **Pandas / NumPy** — data manipulation
- **Plotly / Dash** — interactive dashboard
- **SQLite / DuckDB compatible SQL** — query library
- **Claude API (claude-sonnet-4-20250514)** — AI brief generation
- **Jupyter** — analytical narrative

---

## 📦 Requirements

```
pandas>=2.0
numpy>=1.24
plotly>=5.15
dash>=2.14
faker>=18.0
jupyter>=1.0
```

---

## 📄 License

MIT — free to use, adapt, and build upon.

---

*Built as a portfolio project demonstrating programmatic advertising analytics, RTB funnel analysis, SQL proficiency, and LLM-powered automation.*
