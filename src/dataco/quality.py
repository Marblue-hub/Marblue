"""Traceable issues; never dump source rows or identity fields."""
import re
import numpy as np
import pandas as pd
from .ingestion import FIELDS, VALID_DELIVERY

ORDER_FIELDS = [
    "shipping_mode", "market", "region", "country", "state", "order_date",
    "shipping_date", "customer_id", "customer_segment", "delivery_status",
    "order_status", "actual_days", "planned_days", "is_canceled", "is_over_schedule",
]
ISSUE_COLUMNS = ["source_row", "order_id", "order_item_id", "field", "raw_value", "rule", "severity", "action"]


def safe_value(value):
    text = str(value)
    if "@" in text or re.search(r"https?://|password|token|secret", text, re.I):
        return "[REDACTED]"
    return text[:160]


def audit(raw, d):
    issues = []
    inverse = {v: k for k, v in FIELDS.items()}

    def add(mask, field, rule, severity="warning", action="retain_and_audit"):
        mask = pd.Series(mask, index=d.index).fillna(False)
        source = inverse.get(field)
        for i in d.index[mask]:
            value = raw.at[i, source] if source in raw else d.at[i, field] if field in d else ""
            issues.append({
                "source_row": int(d.at[i, "source_row"]),
                "order_id": d.at[i, "order_id"], "order_item_id": d.at[i, "order_item_id"],
                "field": source or field, "raw_value": safe_value(value), "rule": rule,
                "severity": severity, "action": action,
            })

    for key in ("order_id", "order_item_id"):
        add(d[key].isna(), key, "INVALID_PRIMARY_KEY", "error", "stop_build")
    add(d.order_item_id.notna() & d.order_item_id.duplicated(keep=False),
        "order_item_id", "DUPLICATE_ITEM_KEY", "error", "stop_build")
    for field in ("order_date", "shipping_date"):
        add(d[field].isna(), field, "INVALID_DATE")
    for field in ("actual_days", "planned_days"):
        add(d[field].isna() | d[field].lt(0) | d[field].mod(1).ne(0),
            field, "INVALID_DURATION", action="timing_not_applicable")
    for field in ("sales", "gross_sales", "reported_profit"):
        add(d[field].isna(), field, "MISSING_FINANCIAL_VALUE", "error", "stop_build")
    for field in ("sales", "gross_sales"):
        add(d[field].lt(0), field, "NEGATIVE_SALES")
    add(d.discount_rate.isna() | ~d.discount_rate.between(0, 1), "discount_rate", "INVALID_DISCOUNT_RATE")
    add(d.discount.isna() | d.discount.lt(0) | d.discount.gt(d.gross_sales + 0.011),
        "discount", "INVALID_DISCOUNT_AMOUNT")
    add(d.quantity.isna() | d.quantity.le(0) | d.quantity.mod(1).ne(0), "quantity", "INVALID_QUANTITY")
    add(d.shipping_date.lt(d.order_date), "shipping_date", "SHIPPING_BEFORE_ORDER")
    add(~d.delivery_status.isin(VALID_DELIVERY), "delivery_status", "UNKNOWN_DELIVERY_STATUS",
        action="timing_not_applicable")
    status_conflict = d.is_canceled.ne(d.order_status.eq("CANCELED").astype("Int64"))
    add(status_conflict, "order_status", "CANCEL_STATUS_DIFFERENCE",
        action="use_delivery_status_cancel_rule")
    eligible = d.is_over_schedule.notna()
    add(eligible & d.source_late_risk.ne(d.is_over_schedule), "source_late_risk", "SOURCE_RISK_MISMATCH")
    expected_late = d.delivery_status.eq("Late delivery").astype("Int64")
    add(eligible & expected_late.ne(d.is_over_schedule), "delivery_status", "SOURCE_STATUS_MISMATCH")
    for field, a, b in [
        ("sales", d.sales, d.gross_sales - d.discount),
        ("sales_per_customer", d.sales_per_customer, d.sales),
        ("benefit_per_order", d.benefit_per_order, d.reported_profit),
        ("gross_sales", d.gross_sales, d.unit_price * d.quantity),
    ]:
        add(a.notna() & b.notna() & (a-b).abs().gt(0.011), field, "AMOUNT_IDENTITY_MISMATCH")
    # The published profit ratio is rounded, so use its rounding error bound.
    add(d.source_profit_ratio.notna() &
        (d.reported_profit - d.sales*d.source_profit_ratio).abs().gt(d.sales.abs()*0.005 + 0.011),
        "source_profit_ratio", "PROFIT_RATIO_IDENTITY_MISMATCH")
    conflicts = []
    grouped = d[d.order_id.notna()].groupby("order_id", sort=True)
    for field in ORDER_FIELDS:
        counts = grouped[field].nunique(dropna=False)
        ids = counts[counts.gt(1)].index
        if len(ids):
            add(d.order_id.isin(ids), field, "ORDER_ATTRIBUTE_CONFLICT", action="exclude_order_from_operating_kpi")
            conflicts.extend({"order_id": int(oid), "field": field, "distinct_values": int(counts.loc[oid])} for oid in ids)
    for key, attrs in [
        ("product_id", ["category_id", "category", "department_id", "department", "product_name"]),
        ("customer_id", ["customer_segment"]),
    ]:
        for field in attrs:
            counts = d[d[key].notna()].groupby(key)[field].nunique(dropna=False)
            add(d[key].isin(counts[counts.gt(1)].index), field, "DIMENSION_ATTRIBUTE_CONFLICT",
                action="dimension_value_unknown")
    conflict_frame = pd.DataFrame(conflicts, columns=["order_id", "field", "distinct_values"])
    out = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    report = {
        "rows": int(len(d)), "columns": len(raw.columns),
        "distinct_orders": int(d.order_id.nunique()), "distinct_items": int(d.order_item_id.nunique()),
        "conflict_orders": int(conflict_frame.order_id.nunique()),
        "issue_count": len(out), "affected_rows": int(out.source_row.nunique()),
        "blocking_issue_count": int(out.severity.eq("error").sum()),
        "issue_counts_by_rule": {k: int(v) for k, v in out.rule.value_counts().items()},
        "missing_rates": {c: float(raw[c].astype("string").str.strip().eq("").mean()) for c in raw},
        "optional_missing_columns": [c for c in FIELDS if c not in raw],
        "pii_policy": "source values limited to affected allowed model fields; full rows never exported",
    }
    return report, out, conflict_frame

