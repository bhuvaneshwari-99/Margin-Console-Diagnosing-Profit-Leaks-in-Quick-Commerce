-- =====================================================================================
-- Margin Console · BigQuery (GoogleSQL) analysis
-- Replace `my-project.margin_console.orders` with your table. Load it first:
--     python scripts/load_to_bigquery.py --project my-project --dataset margin_console
-- Same questions and definitions as sql/quick_comm_postgres.sql; only dialect differs.
-- Cost note: the table is ~100 MB, so every query here is far inside the 1 TB/month free tier.
-- =====================================================================================

-- 0. Sanity checks (all problem counts should be 0)
SELECT COUNT(*)                                                       AS total_rows,
       COUNT(*) - COUNT(DISTINCT order_id)                            AS duplicate_ids,
       COUNTIF(order_value <= 0 OR distance_km <= 0)                  AS non_positive_values,
       COUNTIF(ABS(order_value - delivery_cost - discount_amt - profit) > 0.11) AS profit_mismatch,
       COUNTIF(CAST(profit < 0 AS INT64) <> in_loss)                  AS loss_flag_mismatch
FROM `my-project.margin_console.orders`;

-- 1. Headline loss numbers
SELECT COUNTIF(profit < 0)                                             AS loss_orders,
       ROUND(100 * SAFE_DIVIDE(COUNTIF(profit < 0), COUNT(*)), 2)      AS loss_order_pct,
       ROUND(-SUM(IF(profit < 0, profit, 0)), 2)                       AS total_deficit,
       ROUND(-AVG(IF(profit < 0, profit, NULL)), 2)                    AS avg_loss_per_loss_order
FROM `my-project.margin_console.orders`;

-- 2. Loss by city with a real cumulative (Pareto) share; uniform benchmark is 100/12 = 8.33% each
WITH losses AS (
    SELECT city, -SUM(profit) AS total_loss
    FROM `my-project.margin_console.orders`
    WHERE profit < 0
    GROUP BY city
)
SELECT city,
       ROUND(total_loss, 2)                                             AS total_loss,
       ROUND(100 * total_loss / SUM(total_loss) OVER (), 2)             AS loss_share_pct,
       ROUND(100 * SUM(total_loss) OVER (ORDER BY total_loss DESC)
             / SUM(total_loss) OVER (), 2)                              AS cumulative_share_pct
FROM losses
ORDER BY total_loss DESC;

-- 3. Delivery-cost structure: slope = cov/var. corr = 1 => cost is a formula of distance
SELECT ROUND(COVAR_POP(delivery_cost, distance_km) / VAR_POP(distance_km), 3)                 AS per_km,
       ROUND(AVG(delivery_cost) - COVAR_POP(delivery_cost, distance_km) / VAR_POP(distance_km) * AVG(distance_km), 3)
                                                                                                AS intercept,
       ROUND(CORR(delivery_cost, distance_km), 6)                                             AS correlation
FROM `my-project.margin_console.orders`;

-- 4. Loss rate by basket band x distance band
SELECT CASE WHEN order_value < 50  THEN '1  <50'
            WHEN order_value < 100 THEN '2  50-99'
            WHEN order_value < 150 THEN '3  100-149'
            WHEN order_value < 200 THEN '4  150-199'
            ELSE                        '5  200+' END AS basket_band,
       distance_bucket,
       COUNT(*)                                                  AS orders,
       ROUND(100 * SAFE_DIVIDE(COUNTIF(profit < 0), COUNT(*)), 1) AS loss_order_pct
FROM `my-project.margin_console.orders`
GROUP BY basket_band, distance_bucket
ORDER BY basket_band, distance_bucket;

-- 5. Break-even basket by distance band
SELECT distance_bucket,
       ROUND(AVG(delivery_cost), 2)                                                  AS avg_delivery_cost,
       ROUND(AVG(delivery_cost) / (1 - SUM(discount_amt) / SUM(order_value)), 2)     AS break_even_basket
FROM `my-project.margin_console.orders`
GROUP BY distance_bucket
ORDER BY distance_bucket;

-- 6. Discounted vs not, inside basket bands (a bigger basket must not masquerade as a discount effect)
SELECT CASE WHEN order_value < 150  THEN '1  <150'
            WHEN order_value < 300  THEN '2  150-299'
            WHEN order_value < 600  THEN '3  300-599'
            WHEN order_value < 1000 THEN '4  600-999'
            ELSE                         '5  1000+' END AS basket_band,
       discount_applied,
       COUNT(*)                    AS orders,
       ROUND(AVG(profit), 2)       AS avg_profit,
       ROUND(AVG(discount_amt), 2) AS avg_discount_amt
FROM `my-project.margin_console.orders`
GROUP BY basket_band, discount_applied
ORDER BY basket_band, discount_applied;

-- 7. What-if: minimum order value with a top-up assumption (twin of the Streamlit app). Edit params.
WITH params AS (SELECT 150.0 AS threshold, 0.40 AS topup_rate, 1.00 AS margin),
scored AS (
    SELECT o.city,
           p.margin * o.order_value - o.delivery_cost - o.discount_amt AS base_profit,
           o.order_value < p.threshold                                  AS is_small,
           (p.margin - SAFE_DIVIDE(o.discount_amt, o.order_value)) * p.threshold - o.delivery_cost AS topped_profit,
           p.topup_rate
    FROM `my-project.margin_console.orders` o CROSS JOIN params p
)
SELECT city,
       ROUND(SUM(base_profit), 0) AS profit_today,
       ROUND(SUM(IF(is_small, topup_rate * topped_profit, base_profit)) - SUM(base_profit), 0) AS delta_profit,
       COUNTIF(is_small)          AS small_baskets
FROM scored
GROUP BY city
ORDER BY delta_profit DESC;
