"""Read source without mutation. Only explicitly allowed fields enter the mart."""
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd

REQUIRED = [
    "Order Id", "Order Item Id", "order date (DateOrders)", "Shipping Mode",
    "Delivery Status", "Days for shipping (real)", "Days for shipment (scheduled)",
    "Sales", "Order Item Total", "Order Profit Per Order",
]
FIELDS = {
    "Order Id": "order_id", "Order Item Id": "order_item_id",
    "Order Customer Id": "customer_id", "Product Card Id": "product_id",
    "Category Id": "category_id", "Category Name": "category",
    "Department Id": "department_id", "Department Name": "department",
    "Product Name": "product_name", "Customer Segment": "customer_segment",
    "Market": "market", "Order Region": "region", "Order Country": "country",
    "Order State": "state", "Shipping Mode": "shipping_mode",
    "Delivery Status": "delivery_status", "Order Status": "order_status",
    "order date (DateOrders)": "order_date",
    "shipping date (DateOrders)": "shipping_date",
    "Days for shipping (real)": "actual_days",
    "Days for shipment (scheduled)": "planned_days",
    "Sales": "gross_sales", "Order Item Total": "sales",
    "Order Profit Per Order": "reported_profit", "Order Item Discount": "discount",
    "Order Item Discount Rate": "discount_rate", "Order Item Quantity": "quantity",
    "Order Item Product Price": "unit_price", "Late_delivery_risk": "source_late_risk",
    "Benefit per order": "benefit_per_order", "Sales per customer": "sales_per_customer",
    "Order Item Profit Ratio": "source_profit_ratio",
}
KEYS = ["order_id", "order_item_id", "customer_id", "product_id", "category_id", "department_id"]
NUMBERS = ["actual_days", "planned_days", "gross_sales", "sales", "reported_profit",
           "discount", "discount_rate", "quantity", "unit_price", "source_late_risk",
           "benefit_per_order", "sales_per_customer", "source_profit_ratio"]
VALID_DELIVERY = {"Advance shipping", "Late delivery", "Shipping on time", "Shipping canceled"}


class SchemaError(ValueError):
    pass


def fingerprint(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_source(path, encoding="latin-1"):
    raw = pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
    raw.columns = raw.columns.str.strip()
    if raw.columns.duplicated().any():
        raise SchemaError("SCHEMA_DUPLICATE_COLUMN: repair duplicate header names")
    missing = [c for c in REQUIRED if c not in raw]
    if missing:
        raise SchemaError("SCHEMA_MISSING: fields=" + ", ".join(missing) + "; supply the source CSV")
    return raw


def normalize(raw):
    d = pd.DataFrame(index=raw.index)
    d["source_row"] = np.arange(len(raw)) + 2
    for source, target in FIELDS.items():
        values = raw[source].astype("string").str.strip() if source in raw else pd.Series(pd.NA, index=raw.index, dtype="string")
        d[target] = values.mask(values == "")
    for k in KEYS:
        v = pd.to_numeric(d[k], errors="coerce")
        d[k] = v.where(np.isfinite(v) & v.ge(0) & v.mod(1).eq(0)).astype("Int64")
    for k in NUMBERS:
        v = pd.to_numeric(d[k], errors="coerce").astype("Float64")
        d[k] = v.where(np.isfinite(v))
    for k in ("order_date", "shipping_date"):
        d[k] = pd.to_datetime(d[k], format="%m/%d/%Y %H:%M", errors="coerce")
    from .transform import derive_timing
    return derive_timing(d, VALID_DELIVERY)

