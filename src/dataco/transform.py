"""Shared three-state timing contract used before Python, SQL and BI."""
import pandas as pd


def derive_timing(d, valid_delivery):
    known = d.delivery_status.isin(valid_delivery)
    d["is_canceled"] = d.delivery_status.eq("Shipping canceled").astype("Int64").where(known)
    valid = (d.actual_days.ge(0) & d.planned_days.ge(0) &
             d.actual_days.mod(1).eq(0) & d.planned_days.mod(1).eq(0)).fillna(False)
    eligible = d.is_canceled.eq(0).fillna(False) & valid
    d["is_over_schedule"] = d.actual_days.gt(d.planned_days).astype("Int64").where(eligible)
    d["positive_over_days"] = (d.actual_days - d.planned_days).where(d.is_over_schedule.eq(1))
    d["timing_state"] = pd.Series("not_applicable_unknown", index=d.index, dtype="string")
    d.loc[d.is_canceled.eq(1).fillna(False), "timing_state"] = "not_applicable_canceled"
    d.loc[d.is_over_schedule.eq(0).fillna(False), "timing_state"] = "within_schedule"
    d.loc[d.is_over_schedule.eq(1).fillna(False), "timing_state"] = "over_schedule"
    return d
