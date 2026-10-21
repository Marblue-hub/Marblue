import pandas as pd
import pytest
from dataco.ingestion import normalize, SchemaError
from dataco.mart import make_mart
from dataco.quality import audit
from dataco.settings import load_config


def build(raw_rows, changes):
    raw = pd.DataFrame([raw_rows(c) for c in changes])
    d = normalize(raw)
    report, _, conflicts = audit(raw, d)
    return make_mart(d, report, conflicts, load_config())


def test_order_and_item_grains(raw_rows):
    tables = build(raw_rows, [{}, {"Order Item Id": "11", "Order Item Total": "45", "Sales": "50", "Order Profit Per Order": "4.5"}])
    assert len(tables["fact_orders"]) == 1
    assert len(tables["fact_order_items"]) == 2
    assert tables["fact_orders"].sales.iloc[0] == 135
    assert tables["fact_orders"].reported_profit.iloc[0] == 13.5


def test_order_conflict_is_quarantined_from_timing(raw_rows):
    tables = build(raw_rows, [{}, {"Order Item Id": "11", "Shipping Mode": "Same Day"}])
    order = tables["fact_orders"].iloc[0]
    assert order.is_order_conflict == 1
    assert order.shipping_mode == "(unknown)"
    assert pd.isna(order.is_over_schedule)
    assert len(tables["fact_order_items"]) == 2


def test_duplicate_item_key_stops_build(raw_rows):
    with pytest.raises(SchemaError, match="QUALITY_BLOCKED"):
        build(raw_rows, [{}, {}])


def test_january_policy_does_not_fabricate_missing_dates(raw_rows):
    tables = build(raw_rows, [{"order date (DateOrders)": f"1/{day}/2018 10:00",
                             "Order Id": str(day), "Order Item Id": str(day)} for day in range(1,32)])
    dates = tables["dim_date"]
    assert dates.partial_month.eq(0).all()
    assert dates.is_comparable.eq(0).all()
    assert dates.business_completeness.eq("unverified").all()


def test_confirmed_structure_policy_is_exported_to_date_dimension(raw_rows):
    cfg = load_config()
    cfg.update(comparison_policy_status="confirmed_withheld", comparison_review_from="2017-10")
    changes = [{"order date (DateOrders)": f"{month}/{day}/2017 10:00",
                "Order Id": str(month * 100 + day),
                "Order Item Id": str(month * 100 + day)}
               for month, count in [(9, 30), (10, 31)] for day in range(1, count + 1)]
    raw = pd.DataFrame([raw_rows(c) for c in changes])
    d = normalize(raw)
    q, _, conflicts = audit(raw, d)
    dates = make_mart(d, q, conflicts, cfg)["dim_date"]
    assert dates.partial_month.eq(0).all()
    assert dates.loc[dates.order_month.eq("2017-09"), "is_comparable"].eq(1).all()
    assert dates.loc[dates.order_month.eq("2017-10"), "is_comparable"].eq(0).all()
    assert dates.loc[dates.order_month.eq("2017-10"), "comparison_status"].eq("待核验").all()

