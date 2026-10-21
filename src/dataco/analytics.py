"""P0 descriptive outputs; comparisons are observed-record arithmetic, not causal."""
import numpy as np
import pandas as pd


def monthly_trends(monthly, cfg):
    d = monthly.sort_values("order_month").copy()
    d["business_completeness"] = "unverified"
    d["comparison_note"] = "observed_records_only; calendar_coverage_does_not_prove_business_completeness"
    d.loc[d.order_month.isin(cfg["excluded_comparison_months"]), "is_comparable"] = 0
    d["comparison_status"] = d.is_comparable.map({1: "可作观察值比较", 0: "不适用"})
    if cfg.get("comparison_policy_status") in {"pending_user", "confirmed_withheld"}:
        affected = d.order_month.ge(cfg["comparison_review_from"])
        confirmed = cfg["comparison_policy_status"] == "confirmed_withheld"
        d.loc[affected, "is_comparable"] = 0
        d.loc[affected, "comparison_status"] = "待核验" if confirmed else "待确认"
        d.loc[affected, "comparison_note"] = (
            "user_confirmed_review_required; record_structure_change; no_comparison_computed"
            if confirmed else "pending_user_decision_on_record_structure_change; no_comparison_computed")
    d.loc[d.order_month.isin(cfg["excluded_comparison_months"]), "comparison_note"] = "comparison_excluded_by_user; business_completeness_unverified"
    d["sales_mom_change"] = np.nan
    d["sales_yoy_change"] = np.nan
    indexed = d.set_index("order_month")
    for idx, row in d.iterrows():
        if pd.isna(row.order_month) or not row.is_comparable:
            continue
        period = pd.Period(row.order_month, freq="M")
        for offset, field in [(1, "sales_mom_change"), (12, "sales_yoy_change")]:
            key = str(period - offset)
            if key in indexed.index:
                prev = indexed.loc[key]
                if prev.is_comparable and prev.sales:
                    d.at[idx, field] = row.sales / prev.sales - 1
    d["structural_warning"] = ""
    d.loc[d.order_month.ge("2017-10"), "structural_warning"] = "item_per_order_and_category_mix_changed; avoid_unqualified_business_decline_claims"
    return d


def loss_pareto(loss):
    d = loss[loss.loss_amount.gt(0)].sort_values(["loss_amount", "category"], ascending=[False, True]).reset_index(drop=True)
    total = d.loss_amount.sum()
    d["loss_share"] = d.loss_amount / total if total else np.nan
    d["cumulative_loss_share"] = d.loss_share.cumsum()
    return d


def commercial(con):
    groups = {"market": "market", "category": "category", "department": "department",
              "customer_segment": "customer_segment", "product": "product_id"}
    results = []
    for label, col in groups.items():
        sql = f"""SELECT '{label}' AS dimension, COALESCE(CAST({col} AS TEXT),'(unknown)') AS segment,
            COUNT(*) AS order_items, COUNT(DISTINCT order_id) AS orders,
            SUM(sales) AS sales, SUM(gross_sales) AS gross_sales,
            SUM(reported_profit) AS reported_profit,
            SUM(CASE WHEN reported_profit<0 THEN -reported_profit ELSE 0 END) AS negative_profit_amount,
            SUM(reported_profit<0) AS negative_items
            FROM v_commercial_lines GROUP BY {col}"""
        frame = pd.read_sql_query(sql, con)
        frame["reported_profit_margin"] = frame.reported_profit / frame.sales.replace(0, np.nan)
        frame["sales_contribution"] = frame.sales / frame.sales.sum() if frame.sales.sum() else np.nan
        results.append(frame)
    return pd.concat(results, ignore_index=True)


def fulfillment(con, cfg):
    groups = {
        "shipping_mode": ["shipping_mode"], "market": ["market"], "region": ["region"],
        "shipping_mode_region": ["shipping_mode", "region"],
        "shipping_mode_planned_days": ["shipping_mode", "planned_days"],
        "market_planned_days": ["market", "planned_days"],
    }
    frames = []
    delayed_total = con.execute("SELECT COUNT(*) FROM fact_orders WHERE is_over_schedule=1").fetchone()[0]
    for label, cols in groups.items():
        segment = " || ' / ' || ".join(f"COALESCE(CAST({c} AS TEXT),'(unknown)')" for c in cols)
        query = f"""SELECT '{label}' AS dimension, {segment} AS segment,
            COUNT(*) AS orders, COUNT(is_over_schedule) AS eligible_orders,
            COALESCE(SUM(is_over_schedule=1),0) AS over_schedule_orders,
            COALESCE(SUM(is_canceled=1),0) AS canceled_orders,
            SUM(sales) AS sales,
            SUM(CASE WHEN is_over_schedule=1 THEN sales ELSE 0 END) AS over_schedule_sales_exposure,
            AVG(CASE WHEN is_over_schedule=1 THEN positive_over_days END) AS avg_positive_over_days
            FROM fact_orders GROUP BY {', '.join(cols)}"""
        frame = pd.read_sql_query(query, con)
        frame["over_schedule_rate"] = frame.over_schedule_orders / frame.eligible_orders.replace(0, np.nan)
        frame["over_schedule_contribution"] = frame.over_schedule_orders / delayed_total if delayed_total else np.nan
        frame["small_sample"] = frame.eligible_orders.lt(cfg["small_sample_threshold"]).astype(int)
        frame["severity_rank"] = frame.over_schedule_rate.rank(method="min", ascending=False).astype("Int64")
        frame["volume_rank"] = frame.over_schedule_orders.rank(method="min", ascending=False).astype("Int64")
        frame["interpretation"] = np.where(frame.segment.str.contains("First Class", regex=False),
                                           "requires_source_definition_review", "descriptive_association_only")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def generate(con, cfg, output):
    output.mkdir(parents=True, exist_ok=True)
    datasets = {
        "commercial_summary": commercial(con),
        "monthly_trends": monthly_trends(pd.read_sql_query("SELECT * FROM v_monthly_commercial", con), cfg),
        "loss_pareto": loss_pareto(pd.read_sql_query("SELECT * FROM v_loss_categories", con)),
        "fulfillment_segments": fulfillment(con, cfg),
        "first_class_audit": pd.read_sql_query("SELECT * FROM v_first_class_audit", con),
        "cancellation_status_audit": pd.read_sql_query(
            "SELECT delivery_status,order_status,COUNT(*) AS orders,SUM(sales) AS sales FROM fact_orders GROUP BY delivery_status,order_status", con),
    }
    for name, frame in datasets.items():
        frame.to_csv(output / (name + ".csv"), index=False, encoding="utf-8-sig")
    return datasets

