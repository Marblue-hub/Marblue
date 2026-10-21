import runpy
from pathlib import Path


def test_original_multi_line_dax_measures_are_kept_whole():
    root = Path(__file__).resolve().parents[1]
    author = runpy.run_path(str(root / "scripts/build_powerbi_project.py"))
    measures = author["load_measures"]()
    assert not any(name.startswith("VAR ") for name in measures)
    for name in ("Orders", "Average Positive Over Days", "Over Schedule Order Sales Exposure"):
        assert measures[name].startswith("VAR SelectedOrderIds")
        assert "RETURN " in measures[name]
        assert "CALCULATE(" in measures[name]
        assert "TREATAS(SelectedOrderIds, fact_orders[order_id])" in measures[name]
