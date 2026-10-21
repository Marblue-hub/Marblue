"""Verify the actual persisted outputs, optionally repeat the full pipeline."""
import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
import pandas as pd
from dataco.ingestion import fingerprint
from dataco.settings import ROOT, load_config


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.images = [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "a":
            self.links.append(a.get("href", ""))
        if tag == "img":
            self.images += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rerun", action="store_true")
    args = parser.parse_args()
    manifest_path = ROOT / "reports/run_manifest.json"
    before = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.rerun:
        subprocess.run([sys.executable, "-m", "dataco.cli", "run"], cwd=ROOT, check=True)
    after = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = [p for p,h in before["artifacts"].items() if after["artifacts"].get(p) != h]
    unexpected = sorted(set(after["artifacts"]) - set(before["artifacts"]))
    forbidden = {"Customer Email","Customer Fname","Customer Lname","Customer Password",
                 "Customer Street","Customer Zipcode","Order Zipcode","Latitude","Longitude",
                 "email","password","street","latitude","longitude"}
    pii_columns = {}
    for path in (ROOT / "powerbi/data").glob("*.csv"):
        names = pd.read_csv(path, nrows=0).columns
        found = sorted(forbidden.intersection(names))
        if found:
            pii_columns[path.name] = found
    page = (ROOT / "reports/analysis_report.html").read_text(encoding="utf-8")
    html_parser = ReportParser()
    html_parser.feed(page)
    missing_links = [p for p in html_parser.links if not p.startswith(("http","https","#")) and not (ROOT / "reports" / p).is_file()]
    report_ok = all(x in html_parser.ids for x in ("overview","sla","products","customers")) and html_parser.images == 4 and not missing_links and "__OVERVIEW__" not in page
    xml = ET.parse(ROOT / "reports/tests.xml")
    suites = list(xml.getroot().iter("testsuite"))
    tests = sum(int(s.attrib.get("tests",0)) for s in suites)
    failures = sum(int(s.attrib.get("failures",0))+int(s.attrib.get("errors",0)) for s in suites)
    rec = json.loads((ROOT / "reports/reconciliation.json").read_text(encoding="utf-8"))
    cfg = load_config()
    raw_unchanged = fingerprint(cfg["input"]) == before["source_sha256"] == after["source_sha256"]
    pending = cfg.get("comparison_policy_status") == "pending_user"
    restricted = cfg.get("comparison_policy_status") in {"pending_user", "confirmed_withheld"}
    monthly = pd.read_csv(ROOT / "reports/monthly_trends.csv")
    affected = monthly.order_month.ge(cfg["comparison_review_from"])
    comparison_ok = not restricted or bool(monthly.loc[affected, ["sales_mom_change","sales_yoy_change"]].isna().all().all())
    labels_ok = cfg.get("comparison_policy_status") != "confirmed_withheld" or bool(monthly.loc[affected, "comparison_status"].eq("待核验").all())
    result = {
        "passed": bool(not pii_columns and report_ok and failures==0 and tests>0 and rec["passed"] and raw_unchanged and comparison_ok and labels_ok and (not args.rerun or not changed and not unexpected)),
        "tests": tests, "test_failures_or_errors": failures,
        "repeat_run_performed": args.rerun, "changed_analytical_artifacts":changed,
        "unexpected_analytical_artifacts":unexpected, "source_unchanged":raw_unchanged,
        "forbidden_export_columns":pii_columns, "html_structure_and_links_passed":report_ok,
        "restricted_comparisons_withheld":comparison_ok,
        "comparison_review_labels_passed":labels_ok,
        "comparison_policy_status":cfg.get("comparison_policy_status"),
        "comparison_policy_pending_user":pending, "powerbi_engine_checked":False,
    }
    (ROOT / "reports/verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

