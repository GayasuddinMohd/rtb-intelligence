"""
RTB Campaign Intelligence Dashboard
====================================
Render-ready version: generates data on startup, exposes `server` for gunicorn.
Run locally:  python app.py
Render start command: gunicorn app:server
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output
import warnings, os, random
warnings.filterwarnings("ignore")

# ── Generate data in-memory (no CSV needed on Render) ─────────────────────────
print("Generating RTB bid log data…")
np.random.seed(42)
random.seed(42)

N_BIDS = 200_000  # reduced for faster cold start on free tier

from datetime import datetime, timedelta

START_DATE = datetime(2025, 1, 1)
END_DATE   = datetime(2025, 3, 31)

CAMPAIGNS = [
    {"campaign_id": f"CMP{i:03d}", "campaign_name": name, "advertiser": adv,
     "goal": goal, "budget_usd": budget, "bid_strategy": strat}
    for i, (name, adv, goal, budget, strat) in enumerate([
        ("Fintech App UA Q1",       "MoneyApp Inc",    "CPI", 50000, "target_cpa"),
        ("Gaming Retargeting",      "GameStudio X",    "CPI", 30000, "max_conversions"),
        ("E-Commerce Brand Lift",   "ShopFast",        "CPM", 20000, "target_cpm"),
        ("Travel App Acquisition",  "WanderBookings",  "CPI", 45000, "target_cpa"),
        ("Streaming Subscriptions", "StreamNow",       "CPI", 60000, "max_conversions"),
        ("Food Delivery UA",        "QuickEats",       "CPI", 35000, "target_cpa"),
        ("Health App Retargeting",  "FitLife Pro",     "CPI", 15000, "max_conversions"),
        ("EdTech Brand Awareness",  "LearnFast",       "CPM", 25000, "target_cpm"),
    ], start=1)
]

AD_FORMATS = ["banner_320x50","interstitial_320x480","native","rewarded_video","banner_300x250"]
OS_TYPES   = ["android","ios"]
COUNTRIES  = ["US","IN","BR","DE","GB","FR","JP","KR","ID","MX","AU","CA","RU","TR","NG"]
EXCHANGES  = ["AppNexus","OpenX","Rubicon","MoPub","AdColony","Unity","IronSource","InMobi"]
PUBLISHERS = [f"PUB{i:04d}" for i in range(1, 101)]

COUNTRY_WEIGHTS = [0.20,0.15,0.08,0.06,0.06,0.05,0.05,0.04,0.04,0.04,0.03,0.03,0.03,0.03,0.11]
FORMAT_WIN_RATE = {"banner_320x50":0.18,"interstitial_320x480":0.28,"native":0.22,"rewarded_video":0.35,"banner_300x250":0.20}
FORMAT_CTR      = {"banner_320x50":0.005,"interstitial_320x480":0.035,"native":0.018,"rewarded_video":0.055,"banner_300x250":0.008}
FORMAT_CVR      = {"banner_320x50":0.04,"interstitial_320x480":0.12,"native":0.09,"rewarded_video":0.18,"banner_300x250":0.05}

date_range_sec = int((END_DATE - START_DATE).total_seconds())
timestamps = sorted([START_DATE + timedelta(seconds=random.randint(0, date_range_sec)) for _ in range(N_BIDS)])

ad_formats   = np.random.choice(AD_FORMATS, N_BIDS, p=[0.30,0.20,0.20,0.15,0.15])
os_arr       = np.random.choice(OS_TYPES, N_BIDS, p=[0.60,0.40])
country_arr  = np.random.choice(COUNTRIES, N_BIDS, p=COUNTRY_WEIGHTS)
exchange_arr = np.random.choice(EXCHANGES, N_BIDS)
pub_arr      = np.random.choice(PUBLISHERS, N_BIDS)
camp_ids     = [c["campaign_id"] for c in CAMPAIGNS]
campaign_arr = np.random.choice(camp_ids, N_BIDS, p=[0.20,0.15,0.15,0.14,0.12,0.10,0.08,0.06])

country_floor = {"US":2.5,"GB":2.0,"DE":1.8,"FR":1.7,"AU":2.0,"CA":1.9,"JP":1.5,"KR":1.2,
                 "BR":0.6,"IN":0.4,"ID":0.3,"MX":0.5,"TR":0.4,"RU":0.5,"NG":0.2}
floors      = np.array([country_floor.get(c,0.5) for c in country_arr])
bid_prices  = np.round(np.random.lognormal(0.3, 0.6, N_BIDS) + floors, 4)
win_rates   = np.array([FORMAT_WIN_RATE[f] for f in ad_formats])
ctrs        = np.array([FORMAT_CTR[f] for f in ad_formats])
cvrs        = np.array([FORMAT_CVR[f] for f in ad_formats])

months_arr  = np.array([t.month for t in timestamps])
anomaly_mask = (campaign_arr == "CMP002") & (months_arr == 2)
ctrs[anomaly_mask] *= 0.30

won       = np.random.random(N_BIDS) < win_rates
clicked   = won & (np.random.random(N_BIDS) < ctrs)
installed = clicked & (np.random.random(N_BIDS) < cvrs)
clearing  = np.where(won, bid_prices * np.random.uniform(0.6,1.0,N_BIDS), 0)
spend     = np.where(won, clearing/1000, 0)

df = pd.DataFrame({
    "bid_id":      [f"BID{i:07d}" for i in range(N_BIDS)],
    "timestamp":   timestamps,
    "campaign_id": campaign_arr,
    "ad_format":   ad_formats,
    "os":          os_arr,
    "country":     country_arr,
    "exchange":    exchange_arr,
    "publisher_id":pub_arr,
    "bid_price_cpm": bid_prices,
    "clearing_price_cpm": np.round(clearing,4),
    "spend_usd":   np.round(spend,6),
    "is_won":      won.astype(int),
    "is_click":    clicked.astype(int),
    "is_install":  installed.astype(int),
    "hour":        [t.hour for t in timestamps],
    "day_of_week": [t.strftime("%A") for t in timestamps],
    "date":        pd.to_datetime([t.date() for t in timestamps]),
    "month":       months_arr,
})

cdf = pd.DataFrame(CAMPAIGNS)
df  = df.merge(cdf[["campaign_id","campaign_name"]], on="campaign_id")
print(f"✅ {N_BIDS:,} bids | {df.is_won.sum():,} wins | {df.is_install.sum():,} installs")

# ── Colors ────────────────────────────────────────────────────────────────────
C = {"bg":"#0A0E1A","surface":"#111827","card":"#1A2235","border":"#2A3650",
     "accent":"#3B82F6","green":"#10B981","amber":"#F59E0B","red":"#EF4444",
     "purple":"#8B5CF6","teal":"#14B8A6","text":"#F1F5F9","muted":"#94A3B8"}

THEME = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             font=dict(family="monospace", color=C["text"], size=11),
             margin=dict(l=20,r=20,t=40,b=20),
             xaxis=dict(gridcolor=C["border"]), yaxis=dict(gridcolor=C["border"]))

# ── Helpers ───────────────────────────────────────────────────────────────────
def kpis(d):
    imp = d.is_won.sum(); clk = d.is_click.sum(); ins = d.is_install.sum()
    spd = d.spend_usd.sum()
    return dict(bids=len(d), impressions=imp, clicks=clk, installs=ins, spend=spd,
                win_rate=imp/len(d) if len(d) else 0,
                ctr=clk/imp if imp else 0, cvr=ins/clk if clk else 0,
                cpi=spd/ins if ins else 0)

def kpi_card(title, val, sub, color):
    return html.Div([
        html.P(title, style={"color":C["muted"],"fontSize":"10px","letterSpacing":"0.1em",
                              "textTransform":"uppercase","margin":"0 0 4px 0"}),
        html.H3(val,  style={"color":color,"fontSize":"24px","margin":"0","fontWeight":"700"}),
        html.P(sub,   style={"color":C["muted"],"fontSize":"10px","margin":"4px 0 0 0"}),
    ], style={"background":C["card"],"border":f"1px solid {C['border']}",
              "borderRadius":"8px","padding":"16px","flex":"1","minWidth":"120px"})

# ── App ───────────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server   # ← Required for gunicorn / Render

CAMP_OPTIONS = [{"label":"All Campaigns","value":"ALL"}] + \
               [{"label":f"{r.campaign_id} — {r.campaign_name}","value":r.campaign_id}
                for _,r in cdf.iterrows()]

app.layout = html.Div([

    # Header
    html.Div([
        html.Div([
            html.Span("◈ RTB INTELLIGENCE", style={"fontWeight":"700","fontSize":"18px",
                      "letterSpacing":"0.12em","color":C["text"]}),
            html.Span(" · Campaign Analytics Dashboard",
                      style={"color":C["muted"],"fontSize":"13px","marginLeft":"10px"}),
        ]),
        html.Span("● Q1 2025 · 200K bid events",
                  style={"color":C["green"],"fontSize":"11px","letterSpacing":"0.08em"}),
    ], style={"background":C["surface"],"borderBottom":f"1px solid {C['border']}",
              "padding":"14px 28px","display":"flex","justifyContent":"space-between","alignItems":"center"}),

    # Filters
    html.Div([
        html.Div([
            html.Label("CAMPAIGN", style={"color":C["muted"],"fontSize":"10px",
                        "letterSpacing":"0.1em","display":"block","marginBottom":"5px"}),
            dcc.Dropdown(id="camp", options=CAMP_OPTIONS, value="ALL", clearable=False,
                         style={"minWidth":"260px"}),
        ]),
        html.Div([
            html.Label("OS", style={"color":C["muted"],"fontSize":"10px",
                        "letterSpacing":"0.1em","display":"block","marginBottom":"5px"}),
            dcc.Dropdown(id="os", options=[{"label":"All","value":"ALL"},
                         {"label":"Android","value":"android"},{"label":"iOS","value":"ios"}],
                         value="ALL", clearable=False, style={"minWidth":"140px"}),
        ]),
        html.Div([
            html.Label("FORMAT", style={"color":C["muted"],"fontSize":"10px",
                        "letterSpacing":"0.1em","display":"block","marginBottom":"5px"}),
            dcc.Dropdown(id="fmt",
                         options=[{"label":"All Formats","value":"ALL"}]+
                                 [{"label":f,"value":f} for f in df.ad_format.unique()],
                         value="ALL", clearable=False, style={"minWidth":"200px"}),
        ]),
    ], style={"background":C["surface"],"borderBottom":f"1px solid {C['border']}",
              "padding":"14px 28px","display":"flex","gap":"20px","flexWrap":"wrap"}),

    # KPI row
    html.Div(id="kpi-row", style={"display":"flex","gap":"12px","padding":"20px 28px","flexWrap":"wrap"}),

    # Charts
    html.Div([
        # Row 1: Funnel + Daily trend
        html.Div([
            html.Div(dcc.Graph(id="funnel", config={"displayModeBar":False}),
                     style={"flex":"1","background":C["card"],"border":f"1px solid {C['border']}",
                            "borderRadius":"8px","padding":"10px","minWidth":"280px"}),
            html.Div(dcc.Graph(id="trend",  config={"displayModeBar":False}),
                     style={"flex":"2","background":C["card"],"border":f"1px solid {C['border']}",
                            "borderRadius":"8px","padding":"10px","minWidth":"380px"}),
        ], style={"display":"flex","gap":"14px","marginBottom":"14px"}),

        # Row 2: Anomaly
        html.Div(dcc.Graph(id="anomaly", config={"displayModeBar":False}),
                 style={"background":C["card"],"border":f"2px solid {C['red']}",
                        "borderRadius":"8px","padding":"10px","marginBottom":"14px"}),

        # Row 3: Geo + Exchange
        html.Div([
            html.Div(dcc.Graph(id="geo",      config={"displayModeBar":False}),
                     style={"flex":"2","background":C["card"],"border":f"1px solid {C['border']}",
                            "borderRadius":"8px","padding":"10px","minWidth":"380px"}),
            html.Div(dcc.Graph(id="exchange", config={"displayModeBar":False}),
                     style={"flex":"1","background":C["card"],"border":f"1px solid {C['border']}",
                            "borderRadius":"8px","padding":"10px","minWidth":"260px"}),
        ], style={"display":"flex","gap":"14px","marginBottom":"14px"}),

        # Row 4: Format + Heatmap
        html.Div([
            html.Div(dcc.Graph(id="formats",  config={"displayModeBar":False}),
                     style={"flex":"1","background":C["card"],"border":f"1px solid {C['border']}",
                            "borderRadius":"8px","padding":"10px","minWidth":"360px"}),
            html.Div(dcc.Graph(id="heatmap",  config={"displayModeBar":False}),
                     style={"flex":"1","background":C["card"],"border":f"1px solid {C['border']}",
                            "borderRadius":"8px","padding":"10px","minWidth":"360px"}),
        ], style={"display":"flex","gap":"14px","marginBottom":"14px"}),

    ], style={"padding":"0 28px 28px"}),

    html.Div("RTB Intelligence Dashboard · Built for Kayzen Product Analyst portfolio",
             style={"textAlign":"center","padding":"12px","color":C["muted"],"fontSize":"11px",
                    "borderTop":f"1px solid {C['border']}","background":C["surface"]}),

], style={"background":C["bg"],"minHeight":"100vh","fontFamily":"monospace"})

# ── Callbacks ─────────────────────────────────────────────────────────────────
def filt(camp, os_val, fmt_val):
    d = df.copy()
    if camp    != "ALL": d = d[d.campaign_id == camp]
    if os_val  != "ALL": d = d[d.os == os_val]
    if fmt_val != "ALL": d = d[d.ad_format == fmt_val]
    return d

@app.callback(
    [Output("kpi-row","children"), Output("funnel","figure"), Output("trend","figure"),
     Output("anomaly","figure"),   Output("geo","figure"),    Output("exchange","figure"),
     Output("formats","figure"),   Output("heatmap","figure")],
    [Input("camp","value"), Input("os","value"), Input("fmt","value")]
)
def update(camp, os_val, fmt_val):
    d = filt(camp, os_val, fmt_val)
    k = kpis(d)

    cards = [
        kpi_card("Bids",        f"{k['bids']:,}",           "total auctions",    C["purple"]),
        kpi_card("Impressions", f"{k['impressions']:,}",    f"WR {k['win_rate']:.1%}", C["accent"]),
        kpi_card("Clicks",      f"{k['clicks']:,}",         f"CTR {k['ctr']:.2%}",    C["teal"]),
        kpi_card("Installs",    f"{k['installs']:,}",       f"CVR {k['cvr']:.2%}",    C["green"]),
        kpi_card("Spend",       f"${k['spend']:.2f}",       "USD total",         C["amber"]),
        kpi_card("CPI",         f"${k['cpi']:.3f}" if k["installs"] else "N/A",
                                "cost per install",  C["red"]),
    ]

    # Funnel
    fig_f = go.Figure(go.Funnel(
        y=["Bids","Impressions","Clicks","Installs"],
        x=[k["bids"],k["impressions"],k["clicks"],k["installs"]],
        textinfo="value+percent previous",
        marker=dict(color=[C["purple"],C["accent"],C["teal"],C["green"]]),
        textfont=dict(size=11, color=C["text"])
    ))
    fig_f.update_layout(title="Conversion Funnel", **THEME)

    # Daily trend
    daily = d.groupby("date").agg(installs=("is_install","sum"),
                                   impressions=("is_won","sum"),
                                   clicks=("is_click","sum")).reset_index()
    daily["ctr"] = daily["clicks"] / daily["impressions"].replace(0,np.nan)
    daily["ctr_7d"] = daily["ctr"].rolling(7, min_periods=1).mean()
    fig_t = make_subplots(specs=[[{"secondary_y":True}]])
    fig_t.add_trace(go.Bar(x=daily["date"], y=daily["installs"], name="Installs",
                            marker_color=C["green"], opacity=0.7), secondary_y=False)
    fig_t.add_trace(go.Scatter(x=daily["date"], y=daily["ctr_7d"]*100, name="CTR 7d%",
                                line=dict(color=C["amber"],width=2)), secondary_y=True)
    fig_t.update_layout(title="Daily Installs & Rolling CTR", **THEME,
                         legend=dict(orientation="h",y=1.12,font=dict(size=10)))
    fig_t.update_yaxes(gridcolor=C["border"])

    # Anomaly
    won_df = df[df["is_won"]==1].copy()
    won_df["week"] = won_df["date"].dt.to_period("W").dt.start_time
    wk = won_df.groupby(["campaign_id","week"]).agg(
        imp=("is_won","sum"), clk=("is_click","sum")).reset_index()
    wk["ctr"] = wk["clk"] / wk["imp"].replace(0,np.nan)
    fig_a = go.Figure()
    palette = [C["accent"],C["green"],C["purple"],C["teal"],C["amber"],"#F97316","#EC4899","#6366F1"]
    for i,(cid,grp) in enumerate(wk.groupby("campaign_id")):
        fig_a.add_trace(go.Scatter(x=grp["week"], y=grp["ctr"]*100, name=cid,
            line=dict(color=palette[i%8], width=3 if cid=="CMP002" else 1.2),
            opacity=1.0 if cid=="CMP002" else 0.45, mode="lines"))
    fig_a.add_vrect(x0="2025-02-01", x1="2025-03-01", fillcolor=C["red"], opacity=0.08,
                    annotation_text="🚨 CTR Anomaly — CMP002 Feb",
                    annotation_font=dict(color=C["red"],size=11))
    fig_a.update_layout(title="Weekly CTR — Anomaly Detection (CMP002 highlighted)",
                         yaxis_title="CTR %", **THEME,
                         legend=dict(orientation="h",y=-0.18,font=dict(size=9)))

    # Geo
    geo = d[d["is_won"]==1].groupby("country").agg(
        impressions=("is_won","sum"), installs=("is_install","sum"),
        spend=("spend_usd","sum")).reset_index()
    geo["cpi"] = geo["spend"] / geo["installs"].replace(0,np.nan)
    geo = geo.dropna(subset=["cpi"])
    fig_g = px.choropleth(geo, locations="country", locationmode="ISO-3", color="cpi",
                           color_continuous_scale="RdYlGn_r",
                           hover_data={"installs":True,"cpi":":.3f"},
                           labels={"cpi":"CPI ($)"})
    fig_g.update_layout(title="CPI by Country", geo=dict(bgcolor="rgba(0,0,0,0)",
                         landcolor="#1E293B",showframe=False), **THEME)

    # Exchange
    ex = d.groupby("exchange").agg(bids=("bid_id","count"), wins=("is_won","sum")).reset_index()
    ex["win_rate"] = ex["wins"]/ex["bids"]
    ex = ex.sort_values("win_rate")
    fig_e = go.Figure(go.Bar(x=ex["win_rate"]*100, y=ex["exchange"], orientation="h",
                              marker=dict(color=ex["win_rate"],
                              colorscale=[[0,C["red"]],[0.5,C["amber"]],[1,C["green"]]]),
                              text=[f"{v:.1f}%" for v in ex["win_rate"]*100],
                              textposition="outside"))
    fig_e.update_layout(title="Win Rate by Exchange", xaxis_title="Win Rate %", **THEME)

    # Formats
    fmt = d.groupby("ad_format").agg(impressions=("is_won","sum"), clicks=("is_click","sum"),
                                      installs=("is_install","sum"), bids=("bid_id","count")).reset_index()
    fmt["win_rate"] = fmt["impressions"]/fmt["bids"]
    fmt["ctr"]      = fmt["clicks"]/fmt["impressions"].replace(0,np.nan)
    fmt["cvr"]      = fmt["installs"]/fmt["clicks"].replace(0,np.nan)
    fig_fmt = go.Figure()
    fig_fmt.add_trace(go.Bar(name="Win Rate %", x=fmt["ad_format"], y=fmt["win_rate"]*100,
                              marker_color=C["purple"], offsetgroup=0))
    fig_fmt.add_trace(go.Bar(name="CTR %",      x=fmt["ad_format"], y=fmt["ctr"]*100,
                              marker_color=C["accent"], offsetgroup=1))
    fig_fmt.add_trace(go.Bar(name="CVR %",      x=fmt["ad_format"], y=fmt["cvr"]*100,
                              marker_color=C["green"], offsetgroup=2))
    fig_fmt.update_layout(title="Format Efficiency Matrix", barmode="group", **THEME,
                           legend=dict(orientation="h",y=1.12,font=dict(size=10)))

    # Heatmap
    days_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    hm = d[d["is_won"]==1].groupby(["day_of_week","hour"]).agg(
        installs=("is_install","sum")).reset_index()
    piv = hm.pivot(index="day_of_week", columns="hour", values="installs").fillna(0)
    piv = piv.reindex([x for x in days_order if x in piv.index])
    fig_h = go.Figure(go.Heatmap(z=piv.values, x=piv.columns, y=piv.index,
        colorscale=[[0,"#111827"],[0.3,C["purple"]],[0.7,C["accent"]],[1,C["green"]]],
        text=piv.values.astype(int), texttemplate="%{text}", textfont=dict(size=8)))
    fig_h.update_layout(title="Install Heatmap — Day × Hour", xaxis_title="Hour (UTC)", **THEME)

    return cards, fig_f, fig_t, fig_a, fig_g, fig_e, fig_fmt, fig_h

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)
