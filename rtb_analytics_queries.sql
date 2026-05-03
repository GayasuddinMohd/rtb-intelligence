-- ============================================================
-- RTB Campaign Intelligence — SQL Query Library
-- Author: Portfolio Project | Platform: Kayzen-style DSP
-- Dialect: Standard SQL (compatible with BigQuery / Redshift)
-- ============================================================
-- These queries are designed for a bid_logs fact table joined
-- with campaigns and publishers dimension tables.
-- ============================================================


-- ────────────────────────────────────────────────────────────
-- Q1: Campaign Funnel Summary (Core KPI Report)
--     Joins campaign metadata; computes full funnel metrics
-- ────────────────────────────────────────────────────────────
WITH funnel AS (
    SELECT
        b.campaign_id,
        c.campaign_name,
        c.advertiser,
        c.goal,
        COUNT(*)                                    AS total_bids,
        SUM(b.is_won)                               AS impressions,
        SUM(b.is_click)                             AS clicks,
        SUM(b.is_install)                           AS installs,
        ROUND(SUM(b.spend_usd), 2)                  AS total_spend_usd,
        ROUND(SUM(b.is_won) * 1.0 / COUNT(*), 4)   AS win_rate,
        ROUND(SUM(b.is_click) * 1.0
              / NULLIF(SUM(b.is_won), 0), 4)        AS ctr,
        ROUND(SUM(b.is_install) * 1.0
              / NULLIF(SUM(b.is_click), 0), 4)      AS cvr,
        ROUND(SUM(b.spend_usd)
              / NULLIF(SUM(b.is_install), 0), 2)    AS cpi_usd,
        ROUND(SUM(b.spend_usd)
              / NULLIF(SUM(b.is_click), 0) * 1000, 2) AS ecpm_usd
    FROM bid_logs b
    JOIN campaigns c USING (campaign_id)
    GROUP BY 1, 2, 3, 4
)
SELECT
    *,
    RANK() OVER (ORDER BY cpi_usd ASC)    AS cpi_rank,
    RANK() OVER (ORDER BY installs DESC)  AS volume_rank
FROM funnel
ORDER BY installs DESC;


-- ────────────────────────────────────────────────────────────
-- Q2: Daily Performance Trend with 7-Day Rolling Averages
--     Window functions for smoothed KPI tracking
-- ────────────────────────────────────────────────────────────
WITH daily AS (
    SELECT
        date,
        campaign_id,
        SUM(is_won)     AS impressions,
        SUM(is_click)   AS clicks,
        SUM(is_install) AS installs,
        SUM(spend_usd)  AS spend
    FROM bid_logs
    GROUP BY 1, 2
)
SELECT
    date,
    campaign_id,
    impressions,
    clicks,
    installs,
    ROUND(spend, 2) AS spend_usd,
    ROUND(clicks * 1.0 / NULLIF(impressions, 0), 4) AS daily_ctr,
    ROUND(
        AVG(clicks * 1.0 / NULLIF(impressions, 0))
        OVER (PARTITION BY campaign_id
              ORDER BY date
              ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 4
    ) AS ctr_7d_rolling_avg,
    ROUND(
        AVG(installs)
        OVER (PARTITION BY campaign_id
              ORDER BY date
              ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2
    ) AS installs_7d_rolling_avg,
    SUM(spend)
        OVER (PARTITION BY campaign_id ORDER BY date) AS cumulative_spend
FROM daily
ORDER BY campaign_id, date;


-- ────────────────────────────────────────────────────────────
-- Q3: Anomaly Detection — CTR Z-Score by Campaign × Week
--     Flags statistically unusual CTR weeks (|z| > 2)
-- ────────────────────────────────────────────────────────────
WITH weekly_ctr AS (
    SELECT
        campaign_id,
        DATE_TRUNC('week', date)                    AS week_start,
        SUM(is_click) * 1.0 / NULLIF(SUM(is_won), 0) AS ctr
    FROM bid_logs
    GROUP BY 1, 2
),
stats AS (
    SELECT
        campaign_id,
        AVG(ctr)    AS mean_ctr,
        STDDEV(ctr) AS stddev_ctr
    FROM weekly_ctr
    GROUP BY 1
),
scored AS (
    SELECT
        w.campaign_id,
        w.week_start,
        ROUND(w.ctr, 5)                                       AS weekly_ctr,
        ROUND(s.mean_ctr, 5)                                  AS campaign_avg_ctr,
        ROUND((w.ctr - s.mean_ctr) / NULLIF(s.stddev_ctr, 0), 2) AS z_score
    FROM weekly_ctr w
    JOIN stats s USING (campaign_id)
)
SELECT
    *,
    CASE
        WHEN ABS(z_score) > 2 THEN '🚨 ANOMALY'
        WHEN ABS(z_score) > 1 THEN '⚠️  WARNING'
        ELSE '✅ NORMAL'
    END AS status
FROM scored
WHERE ABS(z_score) > 1
ORDER BY ABS(z_score) DESC;


-- ────────────────────────────────────────────────────────────
-- Q4: Publisher Quality Analysis
--     Identifies top/bottom publishers by CPI efficiency
--     Uses CTEs + window functions for percentile ranking
-- ────────────────────────────────────────────────────────────
WITH pub_perf AS (
    SELECT
        b.publisher_id,
        p.iab_category,
        p.quality_score,
        p.traffic_type,
        COUNT(*)              AS total_bids,
        SUM(b.is_won)         AS impressions,
        SUM(b.is_click)       AS clicks,
        SUM(b.is_install)     AS installs,
        SUM(b.spend_usd)      AS spend
    FROM bid_logs b
    JOIN publishers p USING (publisher_id)
    GROUP BY 1, 2, 3, 4
    HAVING SUM(b.is_won) >= 50   -- minimum traffic threshold
),
ranked AS (
    SELECT
        *,
        ROUND(clicks * 1.0 / NULLIF(impressions, 0), 4)  AS ctr,
        ROUND(installs * 1.0 / NULLIF(clicks, 0), 4)     AS cvr,
        ROUND(spend / NULLIF(installs, 0), 2)             AS cpi,
        NTILE(10) OVER (ORDER BY spend / NULLIF(installs, 0) ASC) AS cpi_decile
    FROM pub_perf
    WHERE installs > 0
)
SELECT
    publisher_id,
    iab_category,
    traffic_type,
    quality_score,
    impressions,
    clicks,
    installs,
    ROUND(spend, 2) AS spend_usd,
    ctr,
    cvr,
    cpi,
    cpi_decile,
    CASE
        WHEN cpi_decile <= 2 THEN 'TOP PERFORMER'
        WHEN cpi_decile >= 9 THEN 'UNDERPERFORMER'
        ELSE 'MID TIER'
    END AS publisher_tier
FROM ranked
ORDER BY cpi ASC;


-- ────────────────────────────────────────────────────────────
-- Q5: Geo × OS Performance Breakdown
--     Identifies best country-OS combos by CPI for budget
--     reallocation recommendations
-- ────────────────────────────────────────────────────────────
WITH geo_perf AS (
    SELECT
        country,
        os,
        COUNT(*)            AS bids,
        SUM(is_won)         AS impressions,
        SUM(is_click)       AS clicks,
        SUM(is_install)     AS installs,
        SUM(spend_usd)      AS spend,
        AVG(bid_price_cpm)  AS avg_bid_cpm,
        AVG(clearing_price_cpm) AS avg_clearing_cpm
    FROM bid_logs
    GROUP BY 1, 2
)
SELECT
    country,
    os,
    impressions,
    clicks,
    installs,
    ROUND(spend, 2)                                        AS spend_usd,
    ROUND(clicks * 1.0 / NULLIF(impressions, 0), 4)       AS ctr,
    ROUND(installs * 1.0 / NULLIF(clicks, 0), 4)          AS cvr,
    ROUND(spend / NULLIF(installs, 0), 2)                  AS cpi_usd,
    ROUND(avg_bid_cpm, 3)                                  AS avg_bid_cpm,
    ROUND(avg_clearing_cpm, 3)                             AS avg_win_cpm,
    ROUND(avg_bid_cpm - avg_clearing_cpm, 3)               AS bid_surplus_cpm,
    RANK() OVER (ORDER BY spend / NULLIF(installs, 0) ASC) AS cpi_rank
FROM geo_perf
WHERE installs >= 2
ORDER BY cpi_usd ASC;


-- ────────────────────────────────────────────────────────────
-- Q6: Hour-of-Day Heatmap — When Do Users Convert?
--     Finds optimal bidding windows for dayparting
-- ────────────────────────────────────────────────────────────
SELECT
    hour,
    day_of_week,
    SUM(is_won)                                              AS impressions,
    SUM(is_click)                                            AS clicks,
    SUM(is_install)                                          AS installs,
    ROUND(SUM(is_click) * 1.0 / NULLIF(SUM(is_won), 0), 4) AS ctr,
    ROUND(SUM(is_install) * 1.0 / NULLIF(SUM(is_click), 0), 4) AS cvr,
    ROUND(
        SUM(is_install) * 1.0 /
        NULLIF(SUM(is_install), 0) * 100, 2
    ) AS install_share_pct
FROM bid_logs
GROUP BY 1, 2
ORDER BY installs DESC;


-- ────────────────────────────────────────────────────────────
-- Q7: Ad Format Efficiency Matrix
--     Ranks formats by funnel efficiency and CPM competitiveness
-- ────────────────────────────────────────────────────────────
WITH format_stats AS (
    SELECT
        ad_format,
        COUNT(*)                AS bids,
        SUM(is_won)             AS impressions,
        SUM(is_click)           AS clicks,
        SUM(is_install)         AS installs,
        SUM(spend_usd)          AS spend,
        AVG(bid_price_cpm)      AS avg_bid,
        AVG(clearing_price_cpm) AS avg_clear
    FROM bid_logs
    GROUP BY 1
)
SELECT
    ad_format,
    bids,
    impressions,
    ROUND(impressions * 1.0 / bids, 4)           AS win_rate,
    ROUND(clicks * 1.0 / NULLIF(impressions,0),4) AS ctr,
    ROUND(installs * 1.0 / NULLIF(clicks,0),4)    AS cvr,
    ROUND(installs * 1.0 / NULLIF(impressions,0),5) AS impression_to_install,
    ROUND(spend / NULLIF(installs,0), 2)           AS cpi_usd,
    ROUND(avg_bid, 3)                              AS avg_bid_cpm,
    ROUND(avg_clear, 3)                            AS avg_clearing_cpm,
    RANK() OVER (ORDER BY spend / NULLIF(installs,0) ASC) AS cpi_rank
FROM format_stats
ORDER BY cpi_usd ASC;


-- ────────────────────────────────────────────────────────────
-- Q8: Budget Pacing Analysis
--     Checks if campaigns are on track vs their daily budget
-- ────────────────────────────────────────────────────────────
WITH campaign_daily AS (
    SELECT
        campaign_id,
        date,
        SUM(spend_usd) AS daily_spend
    FROM bid_logs
    GROUP BY 1, 2
),
campaign_budget AS (
    SELECT campaign_id, budget_usd,
           budget_usd / 90.0 AS daily_budget_target  -- 90-day quarter
    FROM campaigns
),
pacing AS (
    SELECT
        d.campaign_id,
        d.date,
        d.daily_spend,
        b.daily_budget_target,
        ROUND(d.daily_spend / NULLIF(b.daily_budget_target, 0), 3) AS pace_ratio,
        AVG(d.daily_spend) OVER (
            PARTITION BY d.campaign_id
            ORDER BY d.date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS spend_7d_avg
    FROM campaign_daily d
    JOIN campaign_budget b USING (campaign_id)
)
SELECT
    campaign_id,
    date,
    ROUND(daily_spend, 4)         AS daily_spend_usd,
    ROUND(daily_budget_target, 4) AS target_usd,
    ROUND(pace_ratio, 3)          AS pace_ratio,
    ROUND(spend_7d_avg, 4)        AS spend_7d_avg,
    CASE
        WHEN pace_ratio < 0.7  THEN 'UNDERPACING'
        WHEN pace_ratio > 1.3  THEN 'OVERPACING'
        ELSE 'ON TRACK'
    END AS pacing_status
FROM pacing
ORDER BY date DESC, pace_ratio DESC;


-- ────────────────────────────────────────────────────────────
-- Q9: Exchange Competitiveness Report
--     Win rates and clearing efficiency by exchange
-- ────────────────────────────────────────────────────────────
SELECT
    exchange,
    COUNT(*)                                               AS auctions_entered,
    SUM(is_won)                                            AS auctions_won,
    ROUND(SUM(is_won) * 1.0 / COUNT(*), 4)                AS win_rate,
    ROUND(AVG(bid_price_cpm), 3)                           AS avg_bid_cpm,
    ROUND(AVG(CASE WHEN is_won=1 THEN clearing_price_cpm END), 3) AS avg_win_cpm,
    ROUND(AVG(bid_price_cpm) - AVG(CASE WHEN is_won=1
          THEN clearing_price_cpm END), 3)                 AS avg_bid_surplus,
    SUM(is_install)                                        AS total_installs,
    ROUND(SUM(spend_usd) / NULLIF(SUM(is_install), 0), 2) AS cpi_usd
FROM bid_logs
GROUP BY 1
ORDER BY win_rate DESC;


-- ────────────────────────────────────────────────────────────
-- Q10: Root-Cause Debug — CTR Drop Investigation
--      (The anomaly injected in CMP002, Feb 2025)
--      Isolates the dimension causing the drop
-- ────────────────────────────────────────────────────────────
WITH monthly_ctr AS (
    SELECT
        campaign_id,
        month,
        ad_format,
        os,
        country,
        SUM(is_won)   AS impressions,
        SUM(is_click) AS clicks,
        ROUND(SUM(is_click) * 1.0 / NULLIF(SUM(is_won), 0), 5) AS ctr
    FROM bid_logs
    WHERE campaign_id = 'CMP002'
    GROUP BY 1, 2, 3, 4, 5
),
pivoted AS (
    SELECT
        ad_format,
        os,
        country,
        MAX(CASE WHEN month = 1 THEN ctr END) AS jan_ctr,
        MAX(CASE WHEN month = 2 THEN ctr END) AS feb_ctr,
        MAX(CASE WHEN month = 3 THEN ctr END) AS mar_ctr
    FROM monthly_ctr
    GROUP BY 1, 2, 3
)
SELECT
    *,
    ROUND((feb_ctr - jan_ctr) / NULLIF(jan_ctr, 0) * 100, 1) AS jan_to_feb_change_pct,
    CASE
        WHEN (feb_ctr - jan_ctr) / NULLIF(jan_ctr, 0) < -0.5 THEN '🚨 ROOT CAUSE CANDIDATE'
        ELSE ''
    END AS flag
FROM pivoted
WHERE jan_ctr IS NOT NULL AND feb_ctr IS NOT NULL
ORDER BY jan_to_feb_change_pct ASC;
