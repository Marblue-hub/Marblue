import math
import csv
from decimal import Decimal
import pandas as pd


def divide(n, d):
    return float(n / d) if d and pd.notna(d) and pd.notna(n) else None


def scalar(value):
    return None if pd.isna(value) else float(value)


def python_metrics(tables):
    o, i = tables["fact_orders"], tables["fact_order_items"]
    n = len(o)
    canceled = int(o.is_canceled.eq(1).sum())
    eligible = int(o.is_over_schedule.notna().sum())
    delayed = int(o.is_over_schedule.eq(1).sum())
    within = int(o.is_over_schedule.eq(0).sum())
    joined = i.merge(o[["order_id", "is_canceled", "is_over_schedule"]], on="order_id", validate="many_to_one")
    values = {
        "orders": n, "canceled_orders": canceled, "eligible_orders": eligible,
        "over_schedule_orders": delayed, "within_schedule_orders": within,
        "conflict_orders": int(o.is_order_conflict.sum()),
        "avg_positive_over_days": scalar(o.loc[o.is_over_schedule.eq(1), "positive_over_days"].mean()),
        "order_items": len(i), "sales": scalar(i.sales.sum(min_count=1)),
        "gross_sales": scalar(i.gross_sales.sum(min_count=1)),
        "reported_profit": scalar(i.reported_profit.sum(min_count=1)),
        "recorded_discount": scalar(i.discount.sum(min_count=1)),
        "negative_profit_items": int(i.reported_profit.lt(0).sum()),
        "eligible_items": int(joined.is_over_schedule.notna().sum()),
        "over_schedule_items": int(joined.is_over_schedule.eq(1).sum()),
        "canceled_sales_exposure": scalar(joined.loc[joined.is_canceled.eq(1), "sales"].sum()),
        "over_schedule_sales_exposure": scalar(joined.loc[joined.is_over_schedule.eq(1), "sales"].sum()),
        "unknown_timing_orders": n - canceled - eligible,
    }
    values.update({
        "reported_profit_margin": divide(values["reported_profit"], values["sales"]),
        "average_order_value": divide(values["sales"], n),
        "canceled_order_rate": divide(canceled, n),
        "over_schedule_order_rate": divide(delayed, eligible),
        "over_schedule_item_rate": divide(values["over_schedule_items"], values["eligible_items"]),
        "negative_profit_item_rate": divide(values["negative_profit_items"], len(i)),
    })
    return values


def sql_metrics(con):
    cursor = con.execute("SELECT * FROM v_kpi")
    return dict(zip([col[0] for col in cursor.description], cursor.fetchone()))


def compare(py, sql, cfg):
    rows = []
    if set(py) != set(sql):
        raise ValueError("Metric key sets differ")
    for key, value in py.items():
        other = sql[key]
        tolerance = cfg["ratio_tolerance"] if "rate" in key or "margin" in key or "days" in key else cfg["amount_tolerance"] if key in {
            "sales", "gross_sales", "reported_profit", "recorded_discount", "average_order_value",
            "canceled_sales_exposure", "over_schedule_sales_exposure"} else 0
        delta = None if value is None or other is None else float(other-value)
        passed = (value is None and other is None) or (delta is not None and math.isfinite(delta) and abs(delta) <= tolerance)
        rows.append({"metric": key, "python": value, "sql": other,
                     "difference": delta, "tolerance": tolerance, "passed": bool(passed)})
    return pd.DataFrame(rows)


def raw_controls(path, encoding):
    """Independent stdlib parsing and decimal addition, without normalized inputs."""
    fields = {"sales": "Order Item Total", "gross_sales": "Sales",
              "reported_profit": "Order Profit Per Order", "recorded_discount": "Order Item Discount"}
    sums = {key: Decimal(0) for key in fields}
    orders, items = set(), set()
    rows = 0
    with open(path, encoding=encoding, newline="") as stream:
        for row in csv.DictReader(stream):
            rows += 1
            orders.add(row["Order Id"])
            items.add(row["Order Item Id"])
            for key, field in fields.items():
                text = row.get(field, "").strip()
                if text:
                    sums[key] += Decimal(text)
    return {**{key:float(value) for key,value in sums.items()}, "orders":len(orders), "order_items":rows}

