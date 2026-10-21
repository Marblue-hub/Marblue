DROP VIEW IF EXISTS v_commercial_lines;
CREATE VIEW v_commercial_lines AS
SELECT i.*, p.category, p.department, p.product_name,
 o.market, o.customer_segment, o.order_month, o.is_over_schedule, o.is_canceled
FROM fact_order_items i
JOIN fact_orders o USING(order_id)
LEFT JOIN dim_product p USING(product_id);

DROP VIEW IF EXISTS v_monthly_commercial;
CREATE VIEW v_monthly_commercial AS
WITH item AS (
 SELECT order_month, SUM(sales) AS sales, SUM(gross_sales) AS gross_sales,
 SUM(reported_profit) AS reported_profit, COUNT(*) AS order_items,
 SUM(CASE WHEN reported_profit<0 THEN -reported_profit ELSE 0 END) AS negative_profit_amount
 FROM v_commercial_lines GROUP BY order_month
), ord AS (
 SELECT order_month, COUNT(*) AS orders, COUNT(DISTINCT date_key) AS observed_days
 FROM fact_orders GROUP BY order_month
), dates AS (
 SELECT order_month, MAX(days_in_month) AS days_in_month,
 MAX(partial_month) AS partial_month, MIN(is_comparable) AS is_comparable
 FROM dim_date GROUP BY order_month
)
SELECT item.*, ord.orders, ord.observed_days, dates.days_in_month, dates.partial_month, dates.is_comparable
FROM item JOIN ord USING(order_month) LEFT JOIN dates USING(order_month);

DROP VIEW IF EXISTS v_loss_categories;
CREATE VIEW v_loss_categories AS
SELECT COALESCE(category,'(unknown)') AS category,
 SUM(CASE WHEN reported_profit<0 THEN -reported_profit ELSE 0 END) AS loss_amount,
 SUM(reported_profit<0) AS negative_items
FROM v_commercial_lines GROUP BY category;

