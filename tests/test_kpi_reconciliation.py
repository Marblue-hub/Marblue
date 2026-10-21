import sqlite3
import pandas as pd
import pytest
from dataco.ingestion import normalize
from dataco.quality import audit
from dataco.mart import make_mart, persist
from dataco.metrics import python_metrics, sql_metrics, compare
from dataco.settings import load_config, ROOT


def get_tables(raw_rows, changes):
    raw = pd.DataFrame([raw_rows(c) for c in changes])
    d = normalize(raw)
    q, _, c = audit(raw, d)
    return make_mart(d, q, c, load_config())


def test_sql_python_cancellation_unknown_and_zero_sales(raw_rows, tmp_path):
    tables = get_tables(raw_rows, [
        {},
        {"Order Item Id": "11", "Order Item Total": "45"},
        {"Order Id": "2", "Order Item Id": "12", "Delivery Status": "Shipping canceled"},
        {"Order Id": "3", "Order Item Id": "13", "Days for shipping (real)": ""},
        {"Order Id": "4", "Order Item Id": "14", "Days for shipping (real)": "3", "Late_delivery_risk": "0"},
    ])
    (tmp_path / "sql").mkdir()
    db = persist(tables, tmp_path)
    with sqlite3.connect(db) as con:
        con.executescript((ROOT / "sql/01_kpi_views.sql").read_text())
        py, sql = python_metrics(tables), sql_metrics(con)
        assert compare(py, sql, load_config()).passed.all()
        assert sql["orders"] == 4
        assert sql["order_items"] == 5
        assert sql["eligible_orders"] == 2
        assert sql["over_schedule_orders"] == 1
        assert sql["unknown_timing_orders"] == 1
        assert sql["over_schedule_order_rate"] == 0.5
        assert sql["sales"] == 405

    zero = get_tables(raw_rows, [{"Sales": "0", "Order Item Total": "0"}])
    assert python_metrics(zero)["reported_profit_margin"] is None


def test_empty_denominators_and_differences_are_visible(raw_rows):
    tables = get_tables(raw_rows, [{"Delivery Status": "Shipping canceled"}])
    values = python_metrics(tables)
    assert values["over_schedule_order_rate"] is None
    other = dict(values, orders=99)
    result = compare(values, other, load_config())
    assert not result.passed.all()

