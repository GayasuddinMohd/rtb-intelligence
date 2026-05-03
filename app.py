"""
RTB Campaign Intelligence Dashboard
====================================
A Kayzen-style programmatic advertising analytics dashboard.
Built with Plotly Dash — shows full RTB funnel, anomaly detection,
geo breakdown, format efficiency, and AI-generated campaign briefs.

Run: python dashboard/app.py
Then open: http://localhost:8050
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, callback
import warnings
warnings.filterwarnings("ignore")

# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading data…")
df   = pd.read_csv("data/bid_logs.csv", parse_dates=["timestamp", "date"])
cdf  = pd.read_csv("data/campaigns.csv")
pdf  = pd.read_csv("data/publishers.csv")
df   = df.merge(cdf[["campaign_id","campaign_name","advertiser","goal"]], on="campaign_id")
df   = df.merge(pdf[["publisher_id","iab_category","quality_score","traffic_type"]], on="publisher_id")
print(f"Loaded {len(df):,} bid records")

# ── Color palette ──────────────────────────────────────────────────────────────
COLORS = {
    "bg":       "#0A0E1A",
    "surface":  "#111827",
    "card":     "#1A2235",
    "border":   "#2A3650",
    "accent":   "#3B82F6",
    "green":    "#10B981",
    "amber":    "#F59E0B",
    "red":      "#EF4444",
    "purple":   "#8B5CF6",
    "teal":     "#14B8A6",
    "text":     "#F1F5F9",
    "muted":    "#94A3B8",
}

CHART_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="'DM Mono', 'Courier New', monospace", color=COLORS["text"], size=12),
    margin=dict(l=20, r=20, t=40, b=20),
    xaxis=dict(gridcolor=COLORS["border"], linecolor=COLORS["border"], tickfont=dict(size=11)),
    yaxis=dict(gridcolor=COLORS["border"], linecolor=COLORS["border"], tickfont=dict(size=11)),
)

# ── Helper functions ───────────────────────────────────────────────────────────
def compute_kpis(data):
    bids        = len(data)
    impressions = data["is_won"].sum()
    clicks      = data["is_click"].sum()
    installs    = data["is_install"].sum()
    spend       = data["spend_usd"].sum()
    win_rate    = impressions / bids if bids else 0
    ctr         = clicks / impressions if impressions else 0
    cvr         = installs / clicks if clicks else 0
    cpi         = spend / installs if installs else 0
    ecpm        = (spend / impressions * 1000) if impressions else 0
    return dict(bids=bids, impressions=impressions, clicks=clicks,
                installs=installs, spend=spend, win_rate=win_rate,
                ctr=ctr, cvr=cvr, cpi=cpi, ecpm=ecpm)

def kpi_card(title, value, sub="", color=COLORS["accent"]):
    return html.Div([
        html.P(title, style={"color": COLORS["muted"], "fontSize": "11px",
                              "letterSpacing": "0.1em", "marginBottom": "4px",
                              "textTransform": "uppercase", "fontFamily": "DM Mono, monospace"}),
        html.H3(value, style={"color": color, "fontSize": "26px", "margin": "0",
                               "fontFamily": "DM Mono, monospace", "fontWeight": "700"}),
        html.P(sub, style={"color": COLORS["muted"], "fontSize": "11px",
                            "margin": "4px 0 0 0"}),
    ], style={
        "background": COLORS["card"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "20px",
        "flex": "1",
        "minWidth": "140px",
    })

# ── Build charts ───────────────────────────────────────────────────────────────

def funnel_chart(data):
    kpis = compute_kpis(data)
    stages = ["Bids", "Impressions", "Clicks", "Installs"]
    values = [kpis["bids"], kpis["impressions"], kpis["clicks"], kpis["installs"]]
    colors_f = [COLORS["purple"], COLORS["accent"], COLORS["teal"], COLORS["green"]]

    fig = go.Figure(go.Funnel(
        y=stages, x=values,
        textinfo="value+percent previous",
        marker=dict(color=colors_f),
        connector=dict(line=dict(color=COLORS["border"], width=1)),
        textfont=dict(family="DM Mono, monospace", size=12, color=COLORS["text"]),
    ))
    fig.update_layout(title="Conversion Funnel", **CHART_THEME)
    return fig

def daily_trend(data):
    d = data.groupby("date").agg(
        impressions=("is_won","sum"), clicks=("is_click","sum"),
        installs=("is_install","sum"), spend=("spend_usd","sum")
    ).reset_index()
    d["ctr"] = (d["clicks"] / d["impressions"].replace(0, np.nan)).fillna(0)
    d["ctr_7d"] = d["ctr"].rolling(7, min_periods=1).mean()

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=d["date"], y=d["installs"], name="Installs",
                          marker_color=COLORS["green"], opacity=0.7), secondary_y=False)
    fig.add_trace(go.Scatter(x=d["date"], y=d["ctr_7d"]*100, name="CTR 7d avg %",
                              line=dict(color=COLORS["amber"], width=2),
                              mode="lines"), secondary_y=True)
    fig.update_layout(title="Daily Installs & Rolling CTR", barmode="overlay",
                      legend=dict(orientation="h", y=1.1, x=0, font=dict(size=11)),
                      **CHART_THEME)
    fig.update_yaxes(title_text="Installs", secondary_y=False,
                     gridcolor=COLORS["border"])
    fig.update_yaxes(title_text="CTR %", secondary_y=True, showgrid=False)
    return fig

def geo_heatmap(data):
    g = data[data["is_won"]==1].groupby("country").agg(
        impressions=("is_won","sum"), clicks=("is_click","sum"),
        installs=("is_install","sum"), spend=("spend_usd","sum")
    ).reset_index()
    g["cpi"] = g["spend"] / g["installs"].replace(0, np.nan)
    g = g.dropna(subset=["cpi"])

    fig = px.choropleth(g, locations="country", locationmode="ISO-3",
                        color="cpi", color_continuous_scale="RdYlGn_r",
                        hover_data={"installs": True, "spend": ":.4f", "cpi": ":.2f"},
                        labels={"cpi": "CPI ($)", "installs": "Installs"})
    fig.update_layout(title="CPI by Country (lower = better)",
                      geo=dict(bgcolor="rgba(0,0,0,0)",
                               lakecolor="rgba(0,0,0,0)",
                               landcolor="#1E293B",
                               showframe=False),
                      coloraxis_colorbar=dict(tickfont=dict(color=COLORS["muted"])),
                      **CHART_THEME)
    return fig

def format_efficiency(data):
    f = data.groupby("ad_format").agg(
        bids=("bid_id","count"), impressions=("is_won","sum"),
        clicks=("is_click","sum"), installs=("is_install","sum"),
        spend=("spend_usd","sum")
    ).reset_index()
    f["ctr"] = f["clicks"] / f["impressions"].replace(0, np.nan)
    f["cvr"] = f["installs"] / f["clicks"].replace(0, np.nan)
    f["cpi"] = f["spend"] / f["installs"].replace(0, np.nan)
    f["win_rate"] = f["impressions"] / f["bids"]
    f = f.dropna(subset=["cpi"]).sort_values("cpi")

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Win Rate %", x=f["ad_format"],
                          y=f["win_rate"]*100, marker_color=COLORS["purple"],
                          offsetgroup=0))
    fig.add_trace(go.Bar(name="CTR %", x=f["ad_format"],
                          y=f["ctr"]*100, marker_color=COLORS["accent"],
                          offsetgroup=1))
    fig.add_trace(go.Bar(name="CVR %", x=f["ad_format"],
                          y=f["cvr"]*100, marker_color=COLORS["green"],
                          offsetgroup=2))
    fig.update_layout(title="Format Efficiency Matrix", barmode="group",
                      legend=dict(orientation="h", y=1.12, font=dict(size=11)),
                      **CHART_THEME)
    return fig

def anomaly_chart(data):
    """Shows the CTR anomaly in CMP002 Feb 2025"""
    d = data[data["is_won"]==1].copy()
    d["week"] = d["date"].dt.to_period("W").dt.start_time
    weekly = d.groupby(["campaign_id","week"]).agg(
        impressions=("is_won","sum"), clicks=("is_click","sum")
    ).reset_index()
    weekly["ctr"] = weekly["clicks"] / weekly["impressions"].replace(0, np.nan)

    fig = go.Figure()
    palette = [COLORS["accent"], COLORS["green"], COLORS["purple"], COLORS["teal"],
               COLORS["amber"], "#F97316", "#EC4899", "#6366F1"]
    for i, (cid, grp) in enumerate(weekly.groupby("campaign_id")):
        lw = 3 if cid == "CMP002" else 1.2
        op = 1.0 if cid == "CMP002" else 0.5
        fig.add_trace(go.Scatter(
            x=grp["week"], y=grp["ctr"]*100, name=cid,
            line=dict(color=palette[i % len(palette)], width=lw),
            opacity=op, mode="lines"
        ))
    # Highlight anomaly window
    fig.add_vrect(x0="2025-02-01", x1="2025-03-01",
                  fillcolor=COLORS["red"], opacity=0.08,
                  annotation_text="🚨 CTR Drop (CMP002 Feb)",
                  annotation_position="top left",
                  annotation_font=dict(color=COLORS["red"], size=11))
    fig.update_layout(title="Weekly CTR by Campaign — Anomaly Highlighted",
                      yaxis_title="CTR %",
                      legend=dict(orientation="h", y=-0.2, font=dict(size=10)),
                      **CHART_THEME)
    return fig

def exchange_chart(data):
    ex = data.groupby("exchange").agg(
        bids=("bid_id","count"), wins=("is_won","sum"),
        spend=("spend_usd","sum"), installs=("is_install","sum")
    ).reset_index()
    ex["win_rate"] = ex["wins"] / ex["bids"]
    ex["cpi"]      = ex["spend"] / ex["installs"].replace(0, np.nan)
    ex = ex.sort_values("win_rate", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ex["win_rate"]*100, y=ex["exchange"],
        orientation="h",
        marker=dict(
            color=ex["win_rate"],
            colorscale=[[0, COLORS["red"]], [0.5, COLORS["amber"]], [1, COLORS["green"]]],
            showscale=False
        ),
        text=[f"{v:.1f}%" for v in ex["win_rate"]*100],
        textposition="outside",
        textfont=dict(size=11, color=COLORS["muted"])
    ))
    fig.update_layout(title="Win Rate by Exchange", xaxis_title="Win Rate %",
                      **CHART_THEME)
    return fig

def hourly_heatmap(data):
    days_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    h = data[data["is_won"]==1].groupby(["day_of_week","hour"]).agg(
        installs=("is_install","sum")
    ).reset_index()
    pivot = h.pivot(index="day_of_week", columns="hour", values="installs").fillna(0)
    pivot = pivot.reindex([d for d in days_order if d in pivot.index])

    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns, y=pivot.index,
        colorscale=[[0,"#111827"],[0.3,COLORS["purple"]],
                    [0.7,COLORS["accent"]],[1,COLORS["green"]]],
        text=pivot.values.astype(int),
        texttemplate="%{text}",
        textfont=dict(size=9, color=COLORS["text"]),
        hovertemplate="Day: %{y}<br>Hour: %{x}<br>Installs: %{z}<extra></extra>",
    ))
    fig.update_layout(title="Install Heatmap — Day × Hour",
                      xaxis_title="Hour of Day (UTC)",
                      **CHART_THEME)
    return fig

# ── Dash app ───────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, suppress_callback_exceptions=True,
                meta_tags=[{"name":"viewport","content":"width=device-width,initial-scale=1"}])
app.title = "RTB Intelligence Dashboard"

CAMPAIGN_OPTIONS = [{"label": f"{r['campaign_id']} — {r['campaign_name']}",
                      "value": r["campaign_id"]}
                    for _, r in cdf.iterrows()]

app.layout = html.Div([

    # ── Header ────────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Span("◈", style={"color": COLORS["accent"], "fontSize": "24px",
                                   "marginRight": "10px"}),
            html.Span("RTB INTELLIGENCE", style={
                "fontFamily": "DM Mono, monospace", "fontSize": "18px",
                "fontWeight": "700", "letterSpacing": "0.15em", "color": COLORS["text"]
            }),
            html.Span(" · Campaign Analytics Dashboard", style={
                "fontFamily": "DM Mono, monospace", "fontSize": "13px",
                "color": COLORS["muted"], "marginLeft": "10px"
            }),
        ], style={"display":"flex","alignItems":"center"}),
        html.Div([
            html.Span("● LIVE", style={"color": COLORS["green"], "fontSize": "11px",
                                        "fontFamily": "DM Mono, monospace",
                                        "letterSpacing": "0.1em"}),
            html.Span(" | Q1 2025 | 500K bids", style={"color": COLORS["muted"],
                                                          "fontSize": "11px",
                                                          "fontFamily": "DM Mono, monospace"}),
        ]),
    ], style={
        "background": COLORS["surface"],
        "borderBottom": f"1px solid {COLORS['border']}",
        "padding": "16px 32px",
        "display": "flex",
        "justifyContent": "space-between",
        "alignItems": "center",
    }),

    # ── Controls ──────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Label("CAMPAIGN", style={"color": COLORS["muted"], "fontSize": "10px",
                                           "letterSpacing": "0.1em",
                                           "fontFamily": "DM Mono, monospace",
                                           "display": "block", "marginBottom": "6px"}),
            dcc.Dropdown(
                id="campaign-filter",
                options=[{"label": "All Campaigns", "value": "ALL"}] + CAMPAIGN_OPTIONS,
                value="ALL", clearable=False,
                style={"minWidth": "280px"},
            ),
        ]),
        html.Div([
            html.Label("OS", style={"color": COLORS["muted"], "fontSize": "10px",
                                     "letterSpacing": "0.1em",
                                     "fontFamily": "DM Mono, monospace",
                                     "display": "block", "marginBottom": "6px"}),
            dcc.Dropdown(
                id="os-filter",
                options=[{"label":"All OS","value":"ALL"},
                         {"label":"Android","value":"android"},
                         {"label":"iOS","value":"ios"}],
                value="ALL", clearable=False,
                style={"minWidth": "150px"},
            ),
        ]),
        html.Div([
            html.Label("AD FORMAT", style={"color": COLORS["muted"], "fontSize": "10px",
                                            "letterSpacing": "0.1em",
                                            "fontFamily": "DM Mono, monospace",
                                            "display": "block", "marginBottom": "6px"}),
            dcc.Dropdown(
                id="format-filter",
                options=[{"label": "All Formats", "value": "ALL"}] +
                        [{"label": f, "value": f} for f in df["ad_format"].unique()],
                value="ALL", clearable=False,
                style={"minWidth": "200px"},
            ),
        ]),
    ], style={
        "background": COLORS["surface"],
        "borderBottom": f"1px solid {COLORS['border']}",
        "padding": "16px 32px",
        "display": "flex",
        "gap": "24px",
        "flexWrap": "wrap",
    }),

    # ── KPI Row ───────────────────────────────────────────────────────────────
    html.Div(id="kpi-row", style={
        "display": "flex", "gap": "16px", "padding": "24px 32px",
        "flexWrap": "wrap",
    }),

    # ── Charts Grid ───────────────────────────────────────────────────────────
    html.Div([
        # Row 1: Funnel + Daily Trend
        html.Div([
            html.Div(dcc.Graph(id="funnel-chart", config={"displayModeBar": False}),
                     style={"flex": "1", "minWidth": "300px",
                            "background": COLORS["card"],
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "8px", "padding": "12px"}),
            html.Div(dcc.Graph(id="daily-trend", config={"displayModeBar": False}),
                     style={"flex": "2", "minWidth": "400px",
                            "background": COLORS["card"],
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "8px", "padding": "12px"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

        # Row 2: Anomaly chart
        html.Div(dcc.Graph(id="anomaly-chart", config={"displayModeBar": False}),
                 style={"background": COLORS["card"],
                        "border": f"2px solid {COLORS['red']}",
                        "borderRadius": "8px", "padding": "12px",
                        "marginBottom": "16px"}),

        # Row 3: Geo + Exchange
        html.Div([
            html.Div(dcc.Graph(id="geo-heatmap", config={"displayModeBar": False}),
                     style={"flex": "2", "minWidth": "400px",
                            "background": COLORS["card"],
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "8px", "padding": "12px"}),
            html.Div(dcc.Graph(id="exchange-chart", config={"displayModeBar": False}),
                     style={"flex": "1", "minWidth": "300px",
                            "background": COLORS["card"],
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "8px", "padding": "12px"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

        # Row 4: Format efficiency + Hourly heatmap
        html.Div([
            html.Div(dcc.Graph(id="format-chart", config={"displayModeBar": False}),
                     style={"flex": "1", "minWidth": "400px",
                            "background": COLORS["card"],
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "8px", "padding": "12px"}),
            html.Div(dcc.Graph(id="hourly-heatmap", config={"displayModeBar": False}),
                     style={"flex": "1", "minWidth": "400px",
                            "background": COLORS["card"],
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "8px", "padding": "12px"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

    ], style={"padding": "0 32px 32px"}),

    # ── Footer ────────────────────────────────────────────────────────────────
    html.Div([
        html.Span("RTB Intelligence Dashboard · Built for programmatic advertising analytics · ",
                  style={"color": COLORS["muted"], "fontSize": "11px",
                         "fontFamily": "DM Mono, monospace"}),
        html.A("GitHub", href="#", style={"color": COLORS["accent"], "fontSize": "11px",
                                           "fontFamily": "DM Mono, monospace"}),
    ], style={"textAlign": "center", "padding": "16px",
              "borderTop": f"1px solid {COLORS['border']}",
              "background": COLORS["surface"]}),

], style={"background": COLORS["bg"], "minHeight": "100vh",
          "fontFamily": "DM Mono, Courier New, monospace"})

# ── Callbacks ─────────────────────────────────────────────────────────────────
def filter_data(campaign, os_val, fmt):
    d = df.copy()
    if campaign != "ALL":
        d = d[d["campaign_id"] == campaign]
    if os_val != "ALL":
        d = d[d["os"] == os_val]
    if fmt != "ALL":
        d = d[d["ad_format"] == fmt]
    return d

@app.callback(
    [Output("kpi-row", "children"),
     Output("funnel-chart", "figure"),
     Output("daily-trend", "figure"),
     Output("geo-heatmap", "figure"),
     Output("format-chart", "figure"),
     Output("exchange-chart", "figure"),
     Output("hourly-heatmap", "figure"),
     Output("anomaly-chart", "figure")],
    [Input("campaign-filter", "value"),
     Input("os-filter", "value"),
     Input("format-filter", "value")]
)
def update_all(campaign, os_val, fmt):
    d = filter_data(campaign, os_val, fmt)
    k = compute_kpis(d)

    kpi_cards = [
        kpi_card("Total Bids",      f"{k['bids']:,}",          "auction entries",   COLORS["purple"]),
        kpi_card("Impressions",     f"{k['impressions']:,}",   f"Win {k['win_rate']:.1%}", COLORS["accent"]),
        kpi_card("Clicks",          f"{k['clicks']:,}",        f"CTR {k['ctr']:.2%}",     COLORS["teal"]),
        kpi_card("Installs",        f"{k['installs']:,}",      f"CVR {k['cvr']:.2%}",     COLORS["green"]),
        kpi_card("Total Spend",     f"${k['spend']:.2f}",      "USD",               COLORS["amber"]),
        kpi_card("CPI",             f"${k['cpi']:.3f}" if k["cpi"]>0 else "N/A",
                                    "cost per install",  COLORS["red"]),
        kpi_card("eCPM",            f"${k['ecpm']:.3f}",       "effective CPM",     COLORS["muted"]),
    ]

    return (kpi_cards,
            funnel_chart(d), daily_trend(d), geo_heatmap(d),
            format_efficiency(d), exchange_chart(d),
            hourly_heatmap(d), anomaly_chart(df))  # anomaly always shows full data

if __name__ == "__main__":
    print("\n🚀 Starting RTB Intelligence Dashboard…")
    print("📊 Open your browser: http://localhost:8050\n")
    app.run(debug=True, host="0.0.0.0", port=8050)
