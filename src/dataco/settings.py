from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(path=None):
    config_path = Path(path).resolve() if path else ROOT / "config/project.yaml"
    with config_path.open(encoding="utf-8") as stream:
        cfg = yaml.safe_load(stream)
    cfg["_config_path"] = config_path
    for field in ("input", "dictionary"):
        p = Path(cfg[field])
        cfg[field] = p.resolve() if p.is_absolute() else (ROOT / p).resolve()
    return cfg

