import pandas as pd
import pytest
from dataco.analytics import monthly_trends, loss_pareto
from dataco.settings import load_config


def test_single_month_and_january_are_not_compared():
    cfg = load_config()
    d = pd.DataFrame({"order_month": ["2018-01"], "sales": [1.0], "reported_profit": [0.1],
                      "orders": [1], "observed_days": [31], "days_in_month": [31],
                      "partial_month": [0], "is_comparable": [0]})
    result = monthly_trends(d, cfg)
    assert result.sales_mom_change.isna().all()
    assert result.sales_yoy_change.isna().all()
    assert result.is_comparable.eq(0).all()


def test_pareto_uses_negative_item_profit_magnitude():
    d = pd.DataFrame({"category": ["A", "B", "C"], "loss_amount": [10.0, 30.0, 0.0],
                      "negative_items": [1, 2, 0]})
    p = loss_pareto(d)
    assert p.category.tolist() == ["B", "A"]
    assert p.cumulative_loss_share.iloc[-1] == 1.0


def test_pending_structure_review_never_computes_comparison():
    cfg = load_config()
    cfg.update(comparison_policy_status="pending_user", comparison_review_from="2017-10")
    d = pd.DataFrame({"order_month":["2017-09","2017-10"],"sales":[100.,50.],
                      "reported_profit":[10.,5.],"orders":[1,1],
                      "observed_days":[30,31],"days_in_month":[30,31],
                      "partial_month":[0,0],"is_comparable":[1,1]})
    result = monthly_trends(d,cfg)
    assert result.loc[result.order_month.eq("2017-10"),"sales_mom_change"].isna().all()


def test_confirmed_review_policy_keeps_amounts_and_marks_comparisons():
    cfg = load_config()
    cfg.update(comparison_policy_status="confirmed_withheld", comparison_review_from="2017-10")
    months = ["2017-08", "2017-09", "2017-10", "2017-11", "2017-12", "2018-01"]
    amounts = [100., 120., 60., 50., 40., 30.]
    d = pd.DataFrame({"order_month": months, "sales": amounts,
                      "reported_profit": [v / 10 for v in amounts], "orders": [1] * 6,
                      "observed_days": [31, 30, 31, 30, 31, 31],
                      "days_in_month": [31, 30, 31, 30, 31, 31],
                      "partial_month": [0] * 6, "is_comparable": [1] * 6})
    result = monthly_trends(d, cfg)
    affected = result.order_month.ge("2017-10")
    assert result.sales.tolist() == amounts
    assert result.loc[affected, ["sales_mom_change", "sales_yoy_change"]].isna().all().all()
    assert result.loc[affected, "comparison_status"].eq("待核验").all()
    assert result.loc[affected, "is_comparable"].eq(0).all()
    assert result.loc[result.order_month.eq("2017-09"), "sales_mom_change"].iloc[0] == pytest.approx(.2)

