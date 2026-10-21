-- Load 01_kpi_views.sql first. All rates are fractions, not percentage points.
SELECT * FROM v_kpi;
SELECT 'order_primary_key' AS check_name, COUNT(*)-COUNT(DISTINCT order_id) AS violations FROM fact_orders;
SELECT 'item_primary_key' AS check_name, COUNT(*)-COUNT(DISTINCT order_item_id) AS violations FROM fact_order_items;
SELECT 'orphan_items' AS check_name, COUNT(*) AS violations
FROM fact_order_items i LEFT JOIN fact_orders o USING(order_id) WHERE o.order_id IS NULL;
SELECT 'partition' AS check_name, orders-canceled_orders-eligible_orders-unknown_timing_orders AS violations FROM v_kpi;
PRAGMA foreign_key_check;

