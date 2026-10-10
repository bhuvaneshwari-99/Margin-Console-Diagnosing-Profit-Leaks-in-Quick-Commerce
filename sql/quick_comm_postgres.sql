-- =====================================================================================
-- Margin Console · PostgreSQL analysis
-- Table is built from data/orders_clean.csv (produced by scripts/prepare_data.py).
-- Run top to bottom in pgAdmin / DBeaver / psql. Every query below is read-only.
-- Notes on the delivery-cost / discount / profit columns are in section 0.
-- =====================================================================================

-- ------------------------------------------------------------------ 0. SCHEMA & LOAD
CREATE TABLE IF NOT EXISTS quick_comm (
    order_id                BIGINT PRIMARY KEY,
    company                 VARCHAR(50),
    city                    VARCHAR(50),
    customer_age            INT,
    age_bucket              VARCHAR(20),
    order_value             NUMERIC(10,2),
    delivery_time_min       INT,
    delivery_time_bucket    VARCHAR(20),
    distance_km             NUMERIC(5,2),
    distance_bucket         VARCHAR(20),
    items_count             INT,
    product_category        VARCHAR(50),
    payment_method          VARCHAR(50),
    customer_rating         NUMERIC(2,1),
    discount_applied        SMALLINT CHECK (discount_applied IN (0,1)),
    delivery_partner_rating NUMERIC(2,1),
    delivery_cost           NUMERIC(8,2),   -- MODELLED (not in the Kaggle source): ~ 29 + 8 * distance_km
    discount_amt            NUMERIC(10,2),  -- MODELLED (not in the Kaggle source)
    profit                  NUMERIC(10,2),  -- order_value - delivery_cost - discount_amt
    in_loss                 SMALLINT,
    loss_driver             VARCHAR(30)     -- legacy label; see section 4 for why it is not used
);
-- psql:  \copy quick_comm FROM 'data/orders_clean.csv' CSV HEADER
-- (pgAdmin: right-click table > Import/Export, header on, delimiter ',')

-- Sanity checks: each should return 0 problems
SELECT COUNT(*)                                                       AS total_rows,
       COUNT(*) - COUNT(DISTINCT order_id)                            AS duplicate_ids,
       COUNT(*) FILTER (WHERE order_value <= 0 OR distance_km <= 0)   AS non_positive_values,
       COUNT(*) FILTER (WHERE ABS(order_value - delivery_cost - discount_amt - profit) > 0.11)
                                                                      AS profit_mismatch,
       COUNT(*) FILTER (WHERE (profit < 0)::int <> in_loss)           AS loss_flag_mismatch
FROM quick_comm;

-- ------------------------------------------------------------------ 1. REVENUE (GMV)
-- Total order value. Note: this is GMV (basket value), not company revenue.
SELECT SUM(order_value) AS total_gmv FROM quick_comm;

SELECT company,
       SUM(order_value)             AS total_gmv,
       ROUND(AVG(order_value), 2)   AS avg_order_value
FROM quick_comm
GROUP BY company
ORDER BY total_gmv DESC;

-- Top 5 city x category pairs by GMV
SELECT city, product_category, SUM(order_value) AS gmv
FROM quick_comm
GROUP BY city, product_category
ORDER BY gmv DESC
LIMIT 5;

-- Top cities overall
SELECT city, SUM(order_value) AS gmv
FROM quick_comm
GROUP BY city
ORDER BY gmv DESC;

-- Categories by GMV
SELECT product_category, SUM(order_value) AS gmv
FROM quick_comm
GROUP BY product_category
ORDER BY gmv DESC;

-- ------------------------------------------------------------------ 2. CUSTOMERS
-- Average basket and discount usage by age group (buckets come from the table, so they
-- match the notebook exactly)
SELECT age_bucket,
       ROUND(AVG(order_value), 2)                           AS avg_order_value,
       ROUND(100.0 * AVG(discount_applied), 2)              AS discount_usage_pct
FROM quick_comm
GROUP BY age_bucket
ORDER BY avg_order_value DESC;

SELECT payment_method, COUNT(*) AS orders
FROM quick_comm
GROUP BY payment_method
ORDER BY orders DESC;

-- Discounted vs not: basket, revenue, orders. (Observational - discounted baskets are bigger,
-- which is NOT the same as discounts causing bigger baskets.)
SELECT discount_applied,
       ROUND(AVG(order_value), 2) AS avg_order_value,
       SUM(order_value)           AS gmv,
       COUNT(*)                   AS orders
FROM quick_comm
GROUP BY discount_applied;

-- Delivery time vs satisfaction
SELECT delivery_time_bucket, ROUND(AVG(customer_rating), 3) AS avg_rating, COUNT(*) AS orders
FROM quick_comm
GROUP BY delivery_time_bucket
ORDER BY delivery_time_bucket;

-- Distance vs basket size
SELECT distance_bucket, ROUND(AVG(order_value), 2) AS avg_order_value
FROM quick_comm
GROUP BY distance_bucket
ORDER BY distance_bucket;

SELECT city, ROUND(AVG(customer_rating), 3) AS avg_rating
FROM quick_comm
GROUP BY city
ORDER BY avg_rating DESC;

SELECT delivery_partner_rating, ROUND(AVG(customer_rating), 3) AS avg_customer_rating
FROM quick_comm
GROUP BY delivery_partner_rating
ORDER BY delivery_partner_rating DESC;

-- Do bigger baskets get better ratings?  (original query had LOW / HIGH / HIGH - fixed)
SELECT CASE WHEN order_value < 300 THEN '1 LOW  (<300)'
            WHEN order_value < 600 THEN '2 MEDIUM (300-599)'
            ELSE                        '3 HIGH (600+)' END AS order_bucket,
       ROUND(AVG(customer_rating), 3) AS avg_rating,
       COUNT(*)                       AS orders
FROM quick_comm
GROUP BY 1
ORDER BY 1;

-- ------------------------------------------------------------------ 3. PROFITABILITY
-- 3.1 Share of loss-making orders  (same definition as the notebook: profit < 0)
SELECT COUNT(*) FILTER (WHERE profit < 0)                                   AS loss_orders,
       ROUND(100.0 * COUNT(*) FILTER (WHERE profit < 0) / COUNT(*), 2)      AS loss_order_pct,
       ROUND(-SUM(profit) FILTER (WHERE profit < 0), 2)                     AS total_deficit,
       ROUND(-AVG(profit) FILTER (WHERE profit < 0), 2)                     AS avg_loss_per_loss_order
FROM quick_comm;

-- 3.2 Loss by category.  Compare each share with the uniform benchmark 100/7 = 14.29%:
--     categories are almost perfectly balanced, so small gaps here are noise, not a finding.
WITH losses AS (
    SELECT product_category, -SUM(profit) AS total_loss
    FROM quick_comm WHERE profit < 0 GROUP BY product_category
)
SELECT product_category,
       ROUND(total_loss, 2) AS total_loss,
       ROUND(100.0 * total_loss / SUM(total_loss) OVER (), 2)                        AS loss_share_pct,
       ROUND(100.0 * total_loss / SUM(total_loss) OVER () - 100.0 / COUNT(*) OVER (), 2) AS vs_uniform_pts
FROM losses
ORDER BY total_loss DESC;

-- 3.3 Loss by city, with a real cumulative (Pareto) share.
--     Uniform benchmark for 12 cities is 8.33% each; a true 80/20 pattern would put ~80% of
--     losses in the top 2-3 cities. Check the cumulative column before claiming one.
WITH losses AS (
    SELECT city, -SUM(profit) AS total_loss
    FROM quick_comm WHERE profit < 0 GROUP BY city
)
SELECT city,
       ROUND(total_loss, 2)                                                            AS total_loss,
       ROUND(100.0 * total_loss / SUM(total_loss) OVER (), 2)                          AS loss_share_pct,
       ROUND(100.0 * SUM(total_loss) OVER (ORDER BY total_loss DESC)
             / SUM(total_loss) OVER (), 2)                                             AS cumulative_share_pct,
       RANK() OVER (ORDER BY total_loss DESC)                                          AS city_rank
FROM losses
ORDER BY total_loss DESC;

-- 3.4 Profit per order by city (the "geography" view)
SELECT city,
       ROUND(AVG(profit), 2)                                   AS avg_profit,
       ROUND(AVG(order_value), 2)                              AS avg_basket,
       ROUND(AVG(delivery_cost), 2)                            AS avg_delivery_cost,
       ROUND(100.0 * AVG((profit < 0)::int), 2)                AS loss_order_pct
FROM quick_comm
GROUP BY city
ORDER BY avg_profit;

-- 3.5 Distance vs profit
SELECT distance_bucket,
       ROUND(AVG(profit), 2)                    AS avg_profit,
       ROUND(AVG(delivery_cost), 2)             AS avg_delivery_cost,
       ROUND(100.0 * AVG((profit < 0)::int), 2) AS loss_order_pct
FROM quick_comm
GROUP BY distance_bucket
ORDER BY distance_bucket;

-- 3.6 Discount vs profit (observational; compare like-for-like baskets in 3.7)
SELECT discount_applied,
       COUNT(*)                          AS orders,
       ROUND(AVG(order_value), 2)        AS avg_order_value,
       ROUND(AVG(discount_amt), 2)       AS avg_discount_amt,
       ROUND(AVG(profit), 2)             AS avg_profit
FROM quick_comm
GROUP BY discount_applied;

-- 3.7 Same comparison inside basket-size bands, so a bigger basket cannot masquerade as a discount effect
SELECT CASE WHEN order_value < 150 THEN '1  <150'
            WHEN order_value < 300 THEN '2  150-299'
            WHEN order_value < 600 THEN '3  300-599'
            WHEN order_value < 1000 THEN '4  600-999'
            ELSE                        '5  1000+' END AS basket_band,
       discount_applied,
       COUNT(*)                     AS orders,
       ROUND(AVG(profit), 2)        AS avg_profit,
       ROUND(AVG(discount_amt), 2)  AS avg_discount_amt
FROM quick_comm
GROUP BY 1, 2
ORDER BY 1, 2;

-- ------------------------------------------------------------------ 4. WHY ORDERS LOSE MONEY
-- 4.1 How delivery cost is built.  slope/intercept + corr: corr = 1 means cost is a pure function
--     of distance (i.e. a formula, not a measurement).
SELECT ROUND(regr_intercept(delivery_cost, distance_km)::numeric, 3) AS intercept,
       ROUND(regr_slope(delivery_cost, distance_km)::numeric, 3)     AS per_km,
       ROUND(corr(delivery_cost, distance_km)::numeric, 6)           AS correlation
FROM quick_comm;

-- 4.2 Loss rate by basket band x distance band.  A loss happens when basket < cost + discount,
--     and cost rises with distance, so the loss frontier tilts: farther trips need bigger baskets.
SELECT CASE WHEN order_value < 50  THEN '1  <50'
            WHEN order_value < 100 THEN '2  50-99'
            WHEN order_value < 150 THEN '3  100-149'
            WHEN order_value < 200 THEN '4  150-199'
            ELSE                        '5  200+' END AS basket_band,
       distance_bucket,
       COUNT(*)                                   AS orders,
       ROUND(100.0 * AVG((profit < 0)::int), 1)   AS loss_order_pct
FROM quick_comm
GROUP BY 1, 2
ORDER BY 1, 2;

-- 4.3 The old `loss_driver` label is circular: it tests order_value < 300 FIRST, and no order
--     above ~cost can lose money, so 100% of losses land in 'Low Value Order' by construction.
--     Evidence: the largest loss-making basket is far below 300, so any driver order gives the same answer.
SELECT loss_driver, COUNT(*) AS loss_orders, MAX(order_value) AS max_basket_among_losses
FROM quick_comm WHERE profit < 0
GROUP BY loss_driver;

-- 4.4 Break-even basket by distance band (what a minimum order value / distance-tiered fee must clear)
SELECT distance_bucket,
       ROUND(AVG(delivery_cost), 2)                                            AS avg_delivery_cost,
       ROUND(AVG(delivery_cost) / (1 - SUM(discount_amt) / SUM(order_value)), 2) AS break_even_basket
FROM quick_comm
GROUP BY distance_bucket
ORDER BY distance_bucket;

-- ------------------------------------------------------------------ 5. WHAT-IF (SQL twin of the app)
-- Minimum order value with a top-up assumption. Edit the three parameters.
-- Expected profit per small basket:  topup * profit_after_topup   (the rest abandon => 0)
-- Results should match the Streamlit app with the same settings (tests/test_sql.py proves it).
WITH params AS (SELECT 150.0 AS threshold, 0.40 AS topup_rate, 1.00 AS margin),
scored AS (
    SELECT q.*,
           p.margin * order_value - delivery_cost - discount_amt AS base_profit,
           order_value < p.threshold                              AS is_small,
           (p.margin - CASE WHEN order_value > 0 THEN discount_amt / order_value ELSE 0 END) * p.threshold
               - delivery_cost                                    AS topped_profit
    FROM quick_comm q CROSS JOIN params p
)
SELECT ROUND(SUM(base_profit), 2)                                                     AS profit_today,
       ROUND(SUM(CASE WHEN is_small THEN p.topup_rate * topped_profit ELSE base_profit END), 2)
                                                                                      AS profit_with_policy,
       ROUND(SUM(CASE WHEN is_small THEN p.topup_rate * topped_profit ELSE base_profit END)
             - SUM(base_profit), 2)                                                   AS delta_profit,
       ROUND(SUM(CASE WHEN is_small THEN 1 - p.topup_rate ELSE 0 END), 0)             AS orders_lost,
       COUNT(*) FILTER (WHERE is_small)                                               AS small_baskets
FROM scored CROSS JOIN params p;

-- Same what-if by city (swap `city` for `company` to get platforms)
WITH params AS (SELECT 150.0 AS threshold, 0.40 AS topup_rate, 1.00 AS margin),
scored AS (
    SELECT q.city,
           p.margin * order_value - delivery_cost - discount_amt AS base_profit,
           order_value < p.threshold                              AS is_small,
           (p.margin - CASE WHEN order_value > 0 THEN discount_amt / order_value ELSE 0 END) * p.threshold
               - delivery_cost                                    AS topped_profit
    FROM quick_comm q CROSS JOIN params p
)
SELECT city,
       ROUND(SUM(base_profit), 0) AS profit_today,
       ROUND(SUM(CASE WHEN is_small THEN p.topup_rate * topped_profit ELSE base_profit END) - SUM(base_profit), 0)
                                  AS delta_profit
FROM scored CROSS JOIN params p
GROUP BY city
ORDER BY delta_profit DESC;
