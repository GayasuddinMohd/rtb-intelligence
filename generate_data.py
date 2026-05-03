"""
RTB Bid Log Data Generator
Simulates a realistic programmatic advertising dataset for a mobile DSP.
Covers: bid requests, wins, impressions, clicks, installs (the full funnel).
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import json

np.random.seed(42)
random.seed(42)

# ── Configuration ─────────────────────────────────────────────────────────────
N_BIDS = 500_000
START_DATE = datetime(2025, 1, 1)
END_DATE   = datetime(2025, 3, 31)

# ── Reference tables ──────────────────────────────────────────────────────────
CAMPAIGNS = [
    {"campaign_id": f"CMP{i:03d}", "campaign_name": name, "advertiser": adv,
     "goal": goal, "budget_usd": budget, "bid_strategy": strat}
    for i, (name, adv, goal, budget, strat) in enumerate([
        ("Fintech App UA Q1",       "MoneyApp Inc",      "CPI",   50000, "target_cpa"),
        ("Gaming Retargeting",      "GameStudio X",      "CPI",   30000, "max_conversions"),
        ("E-Commerce Brand Lift",   "ShopFast",          "CPM",   20000, "target_cpm"),
        ("Travel App Acquisition",  "WanderBookings",    "CPI",   45000, "target_cpa"),
        ("Streaming Subscriptions", "StreamNow",         "CPI",   60000, "max_conversions"),
        ("Food Delivery UA",        "QuickEats",         "CPI",   35000, "target_cpa"),
        ("Health App Retargeting",  "FitLife Pro",       "CPI",   15000, "max_conversions"),
        ("EdTech Brand Awareness",  "LearnFast",         "CPM",   25000, "target_cpm"),
    ], start=1)
]

AD_FORMATS = ["banner_320x50", "interstitial_320x480", "native", "rewarded_video", "banner_300x250"]
OS_TYPES    = ["android", "ios"]
COUNTRIES   = ["US","IN","BR","DE","GB","FR","JP","KR","ID","MX","AU","CA","RU","TR","NG"]
EXCHANGES   = ["AppNexus", "OpenX", "Rubicon", "MoPub", "AdColony", "Unity", "IronSource", "InMobi"]
PUBLISHERS  = [f"PUB{i:04d}" for i in range(1, 201)]
DEVICES     = ["smartphone", "tablet"]

COUNTRY_WEIGHTS = [0.20,0.15,0.08,0.06,0.06,0.05,0.05,0.04,0.04,0.04,0.03,0.03,0.03,0.03,0.11]

# ── Bid-level funnel probabilities (by format) ────────────────────────────────
FORMAT_WIN_RATE = {
    "banner_320x50":      0.18,
    "interstitial_320x480": 0.28,
    "native":             0.22,
    "rewarded_video":     0.35,
    "banner_300x250":     0.20,
}
FORMAT_CTR = {
    "banner_320x50":      0.005,
    "interstitial_320x480": 0.035,
    "native":             0.018,
    "rewarded_video":     0.055,
    "banner_300x250":     0.008,
}
FORMAT_CVR = {   # click-to-install
    "banner_320x50":      0.04,
    "interstitial_320x480": 0.12,
    "native":             0.09,
    "rewarded_video":     0.18,
    "banner_300x250":     0.05,
}

# ── Generate bid logs ─────────────────────────────────────────────────────────
print(f"Generating {N_BIDS:,} bid records …")

date_range_seconds = int((END_DATE - START_DATE).total_seconds())
timestamps = [START_DATE + timedelta(seconds=random.randint(0, date_range_seconds))
              for _ in range(N_BIDS)]
timestamps.sort()

campaign_ids  = [c["campaign_id"] for c in CAMPAIGNS]
campaign_wts  = [0.20, 0.15, 0.15, 0.14, 0.12, 0.10, 0.08, 0.06]

ad_formats    = np.random.choice(AD_FORMATS, N_BIDS,
                                  p=[0.30, 0.20, 0.20, 0.15, 0.15])
os_arr        = np.random.choice(OS_TYPES, N_BIDS, p=[0.60, 0.40])
country_arr   = np.random.choice(COUNTRIES, N_BIDS, p=COUNTRY_WEIGHTS)
exchange_arr  = np.random.choice(EXCHANGES, N_BIDS)
publisher_arr = np.random.choice(PUBLISHERS, N_BIDS)
device_arr    = np.random.choice(DEVICES, N_BIDS, p=[0.80, 0.20])
campaign_arr  = np.random.choice(campaign_ids, N_BIDS, p=campaign_wts)

# Bid prices: log-normal, floor varies by country
country_floor = {"US":2.5,"GB":2.0,"DE":1.8,"FR":1.7,"AU":2.0,"CA":1.9,
                 "JP":1.5,"KR":1.2,"BR":0.6,"IN":0.4,"ID":0.3,"MX":0.5,
                 "TR":0.4,"RU":0.5,"NG":0.2}
floors = np.array([country_floor.get(c, 0.5) for c in country_arr])
bid_prices = np.round(np.random.lognormal(mean=0.3, sigma=0.6, size=N_BIDS) + floors, 4)

# Win / impression / click / install flags
win_rates  = np.array([FORMAT_WIN_RATE[f] for f in ad_formats])
ctrs       = np.array([FORMAT_CTR[f] for f in ad_formats])
cvrs       = np.array([FORMAT_CVR[f] for f in ad_formats])

# Inject a performance anomaly: CMP002 has a CTR drop in Feb
anomaly_mask = (campaign_arr == "CMP002") & \
               (np.array([t.month for t in timestamps]) == 2)
ctrs_adj = ctrs.copy()
ctrs_adj[anomaly_mask] *= 0.30   # 70% CTR drop — the "bug" analysts must find

won        = np.random.random(N_BIDS) < win_rates
clicked    = won & (np.random.random(N_BIDS) < ctrs_adj)
installed  = clicked & (np.random.random(N_BIDS) < cvrs)

# CPM for won impressions
clearing_price = np.where(won, bid_prices * np.random.uniform(0.6, 1.0, N_BIDS), 0)
clearing_price = np.round(clearing_price, 4)

# Spend
spend = np.where(won, clearing_price / 1000, 0)  # CPM → per impression cost

df = pd.DataFrame({
    "bid_id":         [f"BID{i:08d}" for i in range(N_BIDS)],
    "timestamp":      timestamps,
    "campaign_id":    campaign_arr,
    "ad_format":      ad_formats,
    "os":             os_arr,
    "country":        country_arr,
    "exchange":       exchange_arr,
    "publisher_id":   publisher_arr,
    "device_type":    device_arr,
    "bid_price_cpm":  bid_prices,
    "clearing_price_cpm": clearing_price,
    "spend_usd":      np.round(spend, 6),
    "is_won":         won.astype(int),
    "is_impression":  won.astype(int),
    "is_click":       clicked.astype(int),
    "is_install":     installed.astype(int),
    "hour":           [t.hour for t in timestamps],
    "day_of_week":    [t.strftime("%A") for t in timestamps],
    "date":           [t.date() for t in timestamps],
    "month":          [t.month for t in timestamps],
})

# ── Campaign metadata table ────────────────────────────────────────────────────
campaigns_df = pd.DataFrame(CAMPAIGNS)

# ── Publisher quality scores ───────────────────────────────────────────────────
pub_quality = pd.DataFrame({
    "publisher_id": PUBLISHERS,
    "quality_score": np.round(np.random.beta(5, 2, len(PUBLISHERS)) * 10, 2),
    "iab_category":  np.random.choice(["Gaming","Finance","News","Entertainment",
                                        "Sports","Health","Travel","Education"], len(PUBLISHERS)),
    "traffic_type":  np.random.choice(["organic","incentivized","mixed"], len(PUBLISHERS),
                                       p=[0.6, 0.2, 0.2]),
})

# ── Save ───────────────────────────────────────────────────────────────────────
df.to_csv("/home/claude/rtb-intelligence/data/bid_logs.csv", index=False)
campaigns_df.to_csv("/home/claude/rtb-intelligence/data/campaigns.csv", index=False)
pub_quality.to_csv("/home/claude/rtb-intelligence/data/publishers.csv", index=False)

print(f"✅ bid_logs.csv       → {len(df):,} rows")
print(f"✅ campaigns.csv      → {len(campaigns_df)} rows")
print(f"✅ publishers.csv     → {len(pub_quality)} rows")
print(f"\nFunnel summary:")
print(f"  Bids:        {N_BIDS:>10,}")
print(f"  Wins:        {df.is_won.sum():>10,}  ({df.is_won.mean():.1%})")
print(f"  Clicks:      {df.is_click.sum():>10,}  ({df.is_click.sum()/df.is_won.sum():.1%} of wins)")
print(f"  Installs:    {df.is_install.sum():>10,}  ({df.is_install.sum()/df.is_click.sum():.1%} of clicks)")
print(f"  Total spend: ${df.spend_usd.sum():>10,.2f}")
