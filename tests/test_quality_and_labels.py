import pandas as pd
import pytest
from dataco.ingestion import SchemaError, read_source, normalize
from dataco.quality import audit


def frame(raw_rows, changes):
    return pd.DataFrame([raw_rows(x) for x in changes])


def test_schema_error_names_missing_field(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Order Id\n1\n", encoding="utf-8")
    with pytest.raises(SchemaError, match="Order Item Id"):
        read_source(p)


@pytest.mark.parametrize("changes,expected", [
    ({}, 1),
    ({"Days for shipping (real)": "3", "Late_delivery_risk": "0"}, 0),
    ({"Delivery Status": "Shipping canceled"}, None),
    ({"Days for shipping (real)": ""}, None),
    ({"Days for shipment (scheduled)": "-1"}, None),
    ({"Days for shipping (real)": "nan"}, None),
    ({"Days for shipping (real)": "inf"}, None),
    ({"Delivery Status": "UNKNOWN"}, None),
])
def test_three_state_labels(raw_rows, changes, expected):
    d = normalize(frame(raw_rows, [changes]))
    value = d["is_over_schedule"].iloc[0]
    assert pd.isna(value) if expected is None else value == expected


def test_conflicting_order_is_identified(raw_rows):
    raw = frame(raw_rows, [{}, {"Order Item Id": "11", "Shipping Mode": "Same Day"}])
    d = normalize(raw)
    report, issues, conflicts = audit(raw, d)
    assert report["conflict_orders"] == 1
    assert "ORDER_ATTRIBUTE_CONFLICT" in set(issues.rule)
    assert conflicts.order_id.nunique() == 1


def test_invalid_key_and_missing_day_are_not_deleted(raw_rows):
    raw = frame(raw_rows, [{"Order Item Id": "", "Days for shipping (real)": ""}])
    d = normalize(raw)
    report, issues, _ = audit(raw, d)
    assert len(d) == 1
    assert report["blocking_issue_count"] > 0
    assert "INVALID_DURATION" in set(issues.rule)


def test_duplicate_and_optional_missing_fields(raw_rows):
    raw = frame(raw_rows, [{}, {}]).drop(columns=["Product Name"])
    report, issues, _ = audit(raw, normalize(raw))
    assert report["blocking_issue_count"] > 0
    assert "DUPLICATE_ITEM_KEY" in set(issues.rule)
    assert "Product Name" in report["optional_missing_columns"]


def test_consistent_source_status_is_not_a_false_positive(raw_rows):
    raw = frame(raw_rows, [{}, {"Order Id": "2", "Order Item Id": "11",
                              "Delivery Status": "Shipping on time",
                              "Days for shipping (real)": "3", "Late_delivery_risk": "0"}])
    _, issues, _ = audit(raw, normalize(raw))
    assert "SOURCE_STATUS_MISMATCH" not in set(issues.rule)

