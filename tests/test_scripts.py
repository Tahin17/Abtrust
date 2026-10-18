"""The case-study scripts must keep working as the library evolves."""

import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hillstrom_analysis_runs_on_schema_stand_in():
    mod = _load("hillstrom")
    md, readout = mod.analyze_hillstrom(mod.synthetic_hillstrom(n=12_000, seed=1))
    assert "## Direct comparison: men's versus women's email" in md
    assert "## Exploratory: visit lift by customer subgroup" in md
    assert set(readout.table.arm) == {"Mens E-Mail", "Womens E-Mail"}
    assert set(readout.table.method) == {"lin_hc2", "delta_ratio"}
    assert not readout.srm.flagged


def test_hillstrom_rejects_wrong_schema():
    import pandas as pd

    mod = _load("hillstrom")
    with pytest.raises(ValueError, match="schema"):
        mod.analyze_hillstrom(pd.DataFrame({"segment": ["No E-Mail"], "visit": [1]}))


def test_simulated_case_json_uses_the_same_naive_population_as_report(tmp_path, monkeypatch):
    import json

    from abtrust.simulate import ecommerce_experiment

    mod = _load("case_study")
    logged, full, truth = ecommerce_experiment(n_users=60_000, seed=2026)
    monkeypatch.setattr(mod, "ecommerce_experiment", lambda **kw: (logged, full, truth))
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "OUT", tmp_path / "reports")
    monkeypatch.setattr(mod, "FIG", tmp_path / "reports/figures")
    monkeypatch.setattr(mod.plots, "forest_figure", lambda *a, **kw: None)
    monkeypatch.setattr(mod.plots, "trajectory_figure", lambda *a, **kw: None)
    mod.main()
    result = json.loads((tmp_path / "reports/case_study.json").read_text(encoding="utf-8"))
    assert result["naive"]["orders_per_session"] == pytest.approx(mod.per_session_naive(logged))
    assert "unique randomization units could not be verified" not in (
        tmp_path / "reports/case_study_readout.md").read_text(encoding="utf-8")
