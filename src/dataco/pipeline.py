import datetime as dt
import json
import sqlite3
import platform
from contextlib import closing
import pandas as pd
from pathlib import Path
from .settings import ROOT
from .ingestion import fingerprint, read_source, normalize, SchemaError
from .quality import audit
from .metrics import python_metrics, sql_metrics, compare, raw_controls


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def validate(cfg):
    before = fingerprint(cfg["input"])
    raw = read_source(cfg["input"], cfg["encoding"])
    d = normalize(raw)
    report, issues, conflicts = audit(raw, d)
    report.update({"source_sha256": before, "source_filename": cfg["input"].name,
                   "source_version": cfg["source_version"], "rule_version": cfg["rule_version"],
                   "loaded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "encoding": cfg["encoding"], "sales_field": cfg["sales_field"]})
    if fingerprint(cfg["input"]) != before:
        raise SchemaError("SOURCE_CHANGED: stop and use an immutable source snapshot")
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    write_json(reports / "data_quality.json", report)
    issues.to_csv(reports / "data_quality_issues.csv", index=False, encoding="utf-8-sig")
    conflicts.to_csv(reports / "order_conflicts.csv", index=False, encoding="utf-8-sig")
    from .documentation import write_dictionary, amount_audit
    write_dictionary(raw, d, cfg, ROOT)
    amount_audit(d, ROOT)
    print(json.dumps({"event": "validated", "sha256": before, "rows": len(d),
                      "issues": len(issues), "blocking": report["blocking_issue_count"]}), flush=True)
    return d, report, conflicts


def execute(command, cfg):
    if cfg["sales_field"] != "Order Item Total":
        raise SchemaError("METRIC_CONTRACT: this revision requires Order Item Total; agree a contract change before changing sales_field")
    if command == "validate":
        _, report, _ = validate(cfg)
        if report["blocking_issue_count"]:
            raise SchemaError("QUALITY_BLOCKED: see data_quality_issues.csv; fix input, do not delete issues silently")
        return
    if command == "build":
        from .mart import make_mart, persist
        d, report, conflicts = validate(cfg)
        tables = make_mart(d, report, conflicts, cfg)
        persist(tables, ROOT)
        with closing(sqlite3.connect(ROOT / "data/db/dataco.sqlite")) as con:
            for script in ["01_kpi_views.sql", "02_commercial_analysis.sql", "03_fulfillment_analysis.sql"]:
                con.executescript((ROOT / "sql" / script).read_text(encoding="utf-8"))
            con.commit()
        write_json(ROOT / "reports/build_manifest.json", {
            "source_sha256": report["source_sha256"], "config_sha256": fingerprint(cfg["_config_path"]),
            "rule_version": cfg["rule_version"], "sales_field": cfg["sales_field"],
            "python_version": platform.python_version(),
            "tables": {name: {"rows": len(frame), "sha256": fingerprint(ROOT / "data/processed" / (name + ".parquet"))} for name, frame in tables.items()},
        })
        print(json.dumps({"event": "built", "tables": {k: len(v) for k,v in tables.items()}}), flush=True)
        return
    if command == "reconcile":
        reconcile(cfg)
        return
    if command == "analyze":
        reconcile(cfg)
        from .analytics import generate
        from .reporting import deliver
        with closing(sqlite3.connect(ROOT / "data/db/dataco.sqlite")) as con:
            datasets = generate(con, cfg, ROOT / "reports")
        kpi = json.loads((ROOT / "reports/kpi_snapshot.json").read_text(encoding="utf-8"))
        deliver(datasets, kpi, cfg, ROOT)
        return
    if command == "run":
        for stage in ("build", "reconcile", "analyze"):
            execute(stage, cfg)
        artifacts = {}
        for folder, pattern in [(ROOT / "reports", "*.csv"), (ROOT / "data/processed", "*.parquet")]:
            for file in sorted(folder.glob(pattern)):
                artifacts[str(file.relative_to(ROOT))] = fingerprint(file)
        write_json(ROOT / "reports/run_manifest.json", {
            "finished_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_sha256": fingerprint(cfg["input"]), "artifacts": artifacts,
            "sales_field": cfg["sales_field"], "gates": {"data": "passed", "analysis": "passed", "powerbi": "rebuild_kit; desktop_validation_pending"},
        })
        return
    raise SchemaError("COMMAND_PENDING: this batch implements validate only")


def reconcile(cfg):
    manifest_path = ROOT / "reports/build_manifest.json"
    if not manifest_path.is_file():
        raise SchemaError("BUILD_REQUIRED: run build before reconcile/analyze")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["source_sha256"] != fingerprint(cfg["input"]):
        raise SchemaError("SOURCE_CHANGED: run build; existing mart belongs to another fingerprint")
    if manifest["config_sha256"] != fingerprint(cfg["_config_path"]) or manifest["sales_field"] != cfg["sales_field"]:
        raise SchemaError("CONFIG_CHANGED: run build and repeat reconciliation")
    tables = {}
    for name, info in manifest["tables"].items():
        file = ROOT / "data/processed" / (name + ".parquet")
        if fingerprint(file) != info["sha256"]:
            raise SchemaError("MART_CHANGED: " + name + "; rebuild before analysis")
        tables[name] = pd.read_parquet(file)
    with closing(sqlite3.connect(ROOT / "data/db/dataco.sqlite")) as con:
        check = compare(python_metrics(tables), sql_metrics(con), cfg)
        fk_ok = not con.execute("PRAGMA foreign_key_check").fetchall()
        # Check grouped commercial totals independently of SQL GROUP BY.
        from .analytics import commercial
        sql_group = commercial(con)
        source = tables["fact_order_items"].merge(tables["fact_orders"][["order_id","market"]], on="order_id", validate="many_to_one")
        py_group = source.groupby("market", dropna=False)[["sales", "reported_profit"]].sum().sort_index()
        market = sql_group[sql_group.dimension.eq("market")].set_index("segment").sort_index()
        group_ok = list(py_group.index) == list(market.index) and bool((py_group - market[["sales","reported_profit"]]).abs().le(cfg["amount_tolerance"]).all().all())
    check.to_csv(ROOT / "reports/reconciliation.csv", index=False, encoding="utf-8-sig")
    py = python_metrics(tables)
    controls = raw_controls(cfg["input"], cfg["encoding"])
    source_check = compare({k:py[k] for k in controls}, controls, cfg)
    source_check.to_csv(ROOT / "reports/source_control_reconciliation.csv", index=False, encoding="utf-8-sig")
    passed = bool(check.passed.all() and fk_ok and group_ok and source_check.passed.all())
    write_json(ROOT / "reports/reconciliation.json", {
        "passed": passed, "metrics_checked": len(check), "foreign_keys_passed": fk_ok,
        "market_aggregation_passed": group_ok, "powerbi_engine_checked": False,
        "independent_raw_controls_passed": bool(source_check.passed.all()),
        "source_sha256": manifest["source_sha256"], "sales_field": cfg["sales_field"]})
    if not passed:
        raise SchemaError("RECONCILIATION_FAILED: inspect reports/reconciliation.csv and grouped totals")
    kpi = python_metrics(tables)
    write_json(ROOT / "reports/kpi_snapshot.json", kpi)
    print(json.dumps({"event": "reconciled", "metrics": len(check), "passed": passed}), flush=True)
    return kpi

