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
