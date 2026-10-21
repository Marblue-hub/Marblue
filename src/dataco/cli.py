import argparse
import datetime as dt
import json
import sys
from .settings import ROOT, load_config


def parser():
    p = argparse.ArgumentParser(description="DataCo P0 pipeline; no raw data is modified.")
    p.add_argument("--config")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("validate", "build", "analyze", "reconcile", "run"):
        cmd = sub.add_parser(name)
        if name in ("validate", "build", "run"):
            cmd.add_argument("--input")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    cfg = load_config(args.config)
    if getattr(args, "input", None):
        from pathlib import Path
        p = Path(args.input)
        cfg["input"] = p.resolve() if p.is_absolute() else (ROOT / p).resolve()
    print(json.dumps({"event": "start", "command": args.command,
                      "utc": dt.datetime.now(dt.timezone.utc).isoformat()}), flush=True)
    try:
        from .pipeline import execute
        execute(args.command, cfg)
    except Exception as exc:
        # Paths, parser error messages, and cell contents may contain PII.
        from .ingestion import SchemaError
        message = str(exc) if isinstance(exc, SchemaError) else type(exc).__name__ + ": inspect local inputs/config and reports; raw values omitted"
        print(json.dumps({"event": "failure", "message": message}), file=sys.stderr)
        return 1
    print(json.dumps({"event": "complete", "command": args.command,
                      "utc": dt.datetime.now(dt.timezone.utc).isoformat()}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

