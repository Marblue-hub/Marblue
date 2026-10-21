"""Separate order and line grains. Consensus is checked before aggregation."""
from pathlib import Path
import sqlite3
from contextlib import closing
import pandas as pd
from .ingestion import SchemaError
from .quality import ORDER_FIELDS


def consensus(values):
    unique = values.drop_duplicates()
    return unique.iloc[0] if len(unique) == 1 else pd.NA


def dimension(d, key, attrs):
    good = d[d[key].notna()]
    grouped = good.groupby(key, sort=True)[attrs]
    counts = grouped.nunique(dropna=False)
    return grouped.first().mask(counts.gt(1)).reset_index()


def make_mart(d, report, conflicts, cfg):
    if report["blocking_issue_count"]:
        raise SchemaError("QUALITY_BLOCKED: see data_quality_issues.csv; repair primary keys/financial values before building")
    grouped = d.groupby("order_id", sort=True)[ORDER_FIELDS]
    counts = grouped.nunique(dropna=False)
    # first() is used only with an explicit consensus check; conflicts become NULL.
    order = grouped.first().mask(counts.gt(1)).reset_index()
    for field in ORDER_FIELDS:
        order[field] = order[field].astype(d[field].dtype)
    sums = d.groupby("order_id", sort=True)[["sales", "gross_sales", "reported_profit", "discount", "quantity"]].sum(min_count=1)
    order = order.merge(sums, on="order_id", validate="one_to_one")
    order["item_count"] = order.order_id.map(d.groupby("order_id").size()).astype("int64")
    order["is_order_conflict"] = order.order_id.isin(conflicts.order_id).astype("int64")
    order["is_over_schedule"] = order.is_over_schedule.astype("Int64").where(order.is_order_conflict.eq(0))
    order["is_canceled"] = order.is_canceled.astype("Int64")
    order["positive_over_days"] = (order.actual_days - order.planned_days).where(order.is_over_schedule.eq(1))
    order["timing_state"] = "not_applicable_unknown"
    order.loc[order.is_canceled.eq(1).fillna(False), "timing_state"] = "not_applicable_canceled"
    order.loc[order.is_over_schedule.eq(0).fillna(False), "timing_state"] = "within_schedule"
    order.loc[order.is_over_schedule.eq(1).fillna(False), "timing_state"] = "over_schedule"
    order.loc[order.is_order_conflict.eq(1), "timing_state"] = "not_applicable_conflict"
    order["order_date"] = pd.to_datetime(order.order_date)
    order["shipping_date"] = pd.to_datetime(order.shipping_date)
    order["date_key"] = order.order_date.dt.strftime("%Y-%m-%d")
    order["order_month"] = order.order_date.dt.strftime("%Y-%m")
    geo_fields = ["market", "region", "country", "state"]
    geo = order[geo_fields].fillna("(unknown)").drop_duplicates().sort_values(geo_fields).reset_index(drop=True)
    geo.insert(0, "geo_key", range(1, len(geo)+1))
    order[geo_fields] = order[geo_fields].fillna("(unknown)")
    order = order.merge(geo, on=geo_fields, validate="many_to_one")
    ship = order[["shipping_mode"]].fillna("(unknown)").drop_duplicates().sort_values("shipping_mode").reset_index(drop=True)
    ship.insert(0, "shipping_mode_key", range(1, len(ship)+1))
    ranges = d.groupby("shipping_mode").planned_days.agg(["min", "max"]).reset_index()
    ship = ship.merge(ranges, on="shipping_mode", how="left").rename(columns={"min": "planned_days_min", "max": "planned_days_max"})
    order["shipping_mode"] = order.shipping_mode.fillna("(unknown)")
    order = order.merge(ship[["shipping_mode", "shipping_mode_key"]], on="shipping_mode", validate="many_to_one")
    items = d[["order_item_id", "order_id", "product_id", "quantity", "sales", "gross_sales",
               "reported_profit", "discount", "discount_rate", "unit_price", "source_row"]].copy()
    product = dimension(d, "product_id", ["category_id", "category", "department_id", "department", "product_name"])
    customer = dimension(d, "customer_id", ["customer_segment"])
    valid_dates = order.order_date.dropna()
    dates = pd.DataFrame({"date": pd.date_range(valid_dates.min().normalize(), valid_dates.max().normalize())}) if len(valid_dates) else pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]")})
    dates["date_key"] = dates.date.dt.strftime("%Y-%m-%d")
    dates["year"] = dates.date.dt.year
    dates["month"] = dates.date.dt.month
    dates["quarter"] = dates.date.dt.quarter
    dates["weekday"] = dates.date.dt.dayofweek
    dates["order_month"] = dates.date.dt.strftime("%Y-%m")
    observed = order.groupby("order_month").date_key.nunique()
    dates["observed_days"] = dates.order_month.map(observed).fillna(0).astype(int)
    dates["days_in_month"] = dates.date.dt.days_in_month
    dates["partial_month"] = dates.observed_days.ne(dates.days_in_month).astype(int)
    dates["business_completeness"] = "unverified"
    dates["is_comparable"] = (dates.partial_month.eq(0) &
        ~dates.order_month.isin(cfg["excluded_comparison_months"])).astype(int)
    dates["comparison_status"] = dates.is_comparable.map({1: "可作观察值比较", 0: "不适用"})
    if cfg.get("comparison_policy_status") in {"pending_user", "confirmed_withheld"}:
        affected = dates.order_month.ge(cfg["comparison_review_from"])
        dates.loc[affected, "is_comparable"] = 0
        dates.loc[affected, "comparison_status"] = (
            "待核验" if cfg["comparison_policy_status"] == "confirmed_withheld" else "待确认")
    tables = {"dim_product": product, "dim_customer": customer, "dim_date": dates,
              "dim_geography": geo, "dim_shipping": ship, "fact_orders": order,
              "fact_order_items": items}
    return tables


def sqlite_type(series):
    if pd.api.types.is_integer_dtype(series.dtype) or pd.api.types.is_bool_dtype(series.dtype):
        return "INTEGER"
    if pd.api.types.is_numeric_dtype(series.dtype):
        return "REAL"
    return "TEXT"


def persist(tables, root):
    target = root / "data/db"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "dataco.sqlite"
    tmp = target / "dataco.building.sqlite"
    if tmp.exists():
        tmp.unlink()
    constraints = {
        "dim_product": ["PRIMARY KEY (product_id)"],
        "dim_customer": ["PRIMARY KEY (customer_id)"],
        "dim_date": ["PRIMARY KEY (date_key)"],
        "dim_geography": ["PRIMARY KEY (geo_key)"],
        "dim_shipping": ["PRIMARY KEY (shipping_mode_key)"],
        "fact_orders": ["PRIMARY KEY (order_id)", "FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id)",
                        "FOREIGN KEY (date_key) REFERENCES dim_date(date_key)", "FOREIGN KEY (geo_key) REFERENCES dim_geography(geo_key)",
                        "FOREIGN KEY (shipping_mode_key) REFERENCES dim_shipping(shipping_mode_key)"],
        "fact_order_items": ["PRIMARY KEY (order_item_id)", "FOREIGN KEY (order_id) REFERENCES fact_orders(order_id)",
                             "FOREIGN KEY (product_id) REFERENCES dim_product(product_id)"],
    }
    schema = []
    with closing(sqlite3.connect(tmp)) as con:
        con.execute("PRAGMA foreign_keys=ON")
        for name, frame in tables.items():
            columns = [f'"{c}" {sqlite_type(frame[c])}' for c in frame]
            statement = f"CREATE TABLE {name} (" + ", ".join(columns + constraints[name]) + ");"
            con.execute(statement)
            schema.append(statement)
            frame.to_sql(name, con, if_exists="append", index=False)
        con.execute("CREATE INDEX ix_order_items_order ON fact_order_items(order_id)")
        con.execute("CREATE INDEX ix_order_month ON fact_orders(order_month)")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise SchemaError("FOREIGN_KEY_FAILURE: audit unidentified dimension keys")
        con.commit()
    tmp.replace(path)
    for folder in (root / "data/processed", root / "powerbi/data"):
        folder.mkdir(parents=True, exist_ok=True)
        for name, frame in tables.items():
            if folder.name == "processed":
                frame.to_parquet(folder / (name + ".parquet"), index=False)
            else:
                frame.to_csv(folder / (name + ".csv"), index=False, encoding="utf-8-sig")
    (root / "sql/00_schema.sql").write_text("-- Generated from tested schema; no data included.\n" + "\n".join(schema), encoding="utf-8")
    return path

