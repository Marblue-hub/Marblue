-- Contract v1.1: sales = Order Item Total, raw precision retained.
DROP VIEW IF EXISTS v_kpi;
CREATE VIEW v_kpi AS
WITH o AS (
 SELECT COUNT(*) AS orders,
 COALESCE(SUM(is_canceled=1),0) AS canceled_orders,
 COUNT(is_over_schedule) AS eligible_orders,
 COALESCE(SUM(is_over_schedule=1),0) AS over_schedule_orders,
 COALESCE(SUM(is_over_schedule=0),0) AS within_schedule_orders,
 COALESCE(SUM(is_order_conflict=1),0) AS conflict_orders,
 AVG(CASE WHEN is_over_schedule=1 THEN positive_over_days END) AS avg_positive_over_days
 FROM fact_orders
), i AS (
 SELECT COUNT(*) AS order_items, SUM(sales) AS sales, SUM(gross_sales) AS gross_sales,
 SUM(reported_profit) AS reported_profit, SUM(discount) AS recorded_discount,
 COALESCE(SUM(reported_profit<0),0) AS negative_profit_items
 FROM fact_order_items
), e AS (
 SELECT COUNT(CASE WHEN o.is_over_schedule IS NOT NULL THEN 1 END) AS eligible_items,
 COALESCE(SUM(CASE WHEN o.is_over_schedule=1 THEN 1 ELSE 0 END),0) AS over_schedule_items,
 SUM(CASE WHEN o.is_canceled=1 THEN i.sales ELSE 0 END) AS canceled_sales_exposure,
 SUM(CASE WHEN o.is_over_schedule=1 THEN i.sales ELSE 0 END) AS over_schedule_sales_exposure
 FROM fact_order_items i JOIN fact_orders o USING(order_id)
)
SELECT o.*, i.*, e.*,
 orders - canceled_orders - eligible_orders AS unknown_timing_orders,
 1.0 * reported_profit / NULLIF(sales,0) AS reported_profit_margin,
 1.0 * sales / NULLIF(orders,0) AS average_order_value,
 1.0 * canceled_orders / NULLIF(orders,0) AS canceled_order_rate,
 1.0 * over_schedule_orders / NULLIF(eligible_orders,0) AS over_schedule_order_rate,
 1.0 * over_schedule_items / NULLIF(eligible_items,0) AS over_schedule_item_rate,
 1.0 * negative_profit_items / NULLIF(order_items,0) AS negative_profit_item_rate
FROM o CROSS JOIN i CROSS JOIN e;

