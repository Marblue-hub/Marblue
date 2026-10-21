DROP VIEW IF EXISTS v_first_class_audit;
CREATE VIEW v_first_class_audit AS
SELECT shipping_mode, planned_days, actual_days, delivery_status, order_status,
 COUNT(*) AS orders, COUNT(is_over_schedule) AS eligible_orders,
 COALESCE(SUM(is_over_schedule=1),0) AS over_schedule_orders,
 SUM(sales) AS sales,
 SUM(CASE WHEN ABS((julianday(shipping_date)-julianday(order_date))-actual_days)<0.00001 THEN 1 ELSE 0 END) AS shipping_elapsed_matches_actual_days,
 'requires_source_definition_review' AS interpretation
FROM fact_orders WHERE shipping_mode='First Class'
GROUP BY shipping_mode, planned_days, actual_days, delivery_status, order_status;

