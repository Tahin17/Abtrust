"""Smoke tests for the Monte Carlo suite: right shape, and the headline claims hold
even at a small number of simulations (full-size results live in reports/)."""

import numpy as np
import pandas as pd
import pytest

from abtrust.report import load_validation_results, md_table, write_validation_report
from abtrust.sequential import sequential_test
from abtrust.validation import STUDIES, StudyResult, run_all, study_peeking


def test_bounded_study_uses_each_schedules_own_error_budget(monkeypatch):
    """A one-look design must use look 1's budget, not look 100's budget."""
    c = np.zeros(10_000)
    t = np.r_[np.ones(350), np.zeros(9650)]

    class FixedOutcomes:
        def __init__(self):
            self.calls = 0

        def random(self, n):
            outcome = c if self.calls % 2 == 0 else t
            self.calls += 1
            assert n == outcome.size
            return 1.0 - outcome

    monkeypatch.setattr("abtrust.validation.np.random.default_rng", lambda seed: FixedOutcomes())
    table = study_peeking(n_sims=1)
    rates = table[(table.scenario == "A/A (no effect)") & table.method.str.startswith("Hoeffding")
                  & table.rejection_rate.notna()].set_index("looks")
    for k, row in rates.iterrows():
        result = sequential_test(c, t, looks=int(k), mode="bounded")
        assert row.rejection_rate == float(result.stop_index is not None)
    assert rates.loc[1, "rejection_rate"] == 1.0


def test_validation_report_displays_replications_per_power_cell(tmp_path):
    table = pd.DataFrame({
        "design": ["conversion", "revenue"], "method": ["welch", "welch"],
        "n_per_arm": [1000, 2000], "planned_power": [0.8, 0.8],
        "empirical_power": [0.79, 0.81], "mcse": [0.01, 0.02], "n_sims": [2000, 500],
    })
    result = StudyResult("power_calibration", "Power calibration — précision", table, "Example", 1.0)
    report = write_validation_report({"power_calibration": result}, tmp_path, figures=False).read_text(encoding="utf-8")
    assert "Power calibration — précision" in report
    assert "| mcse | n_sims |" in report
    assert "| 1.0% | 2,000 |" in report
    assert "| 2.0% | 500 |" in report
    assert "<sub>2,000 simulated experiments per cell" not in report


@pytest.mark.slow
def test_run_all_quick_and_report(tmp_path):
    res = run_all(scale=0.04, verbose=False)
    assert set(res) == set(STUDIES)

    peek = res["peeking"].table
    aa = peek[(peek.scenario == "A/A (no effect)") & (peek.looks == 100) & peek.rejection_rate.notna()]
    naive = aa[aa.method.str.startswith("naive")].rejection_rate.iloc[0]
    msprt = aa[aa.method.str.startswith("mSPRT")].rejection_rate.iloc[0]
    assert naive > 0.15 > 0.06 > msprt

    cup = res["cuped"].table
    assert cup[(cup.rho == 0.9) & (cup.method == "cuped")].se_ratio.iloc[0] < 0.6

    path = write_validation_report(res, tmp_path, figures=False)
    text = path.read_text()
    assert "# Validation report" in text and "Peeking" in text
    again = load_validation_results(tmp_path)
    assert set(again) == set(res)


def test_md_table_formats():
    import pandas as pd

    md = md_table(pd.DataFrame({"a": [1, 2000], "b": [0.5, 0.25], "c": ["x", "y"]}), {"b": ".0%"})
    assert "| 2,000 | 25% | y |" in md
    assert md.splitlines()[1] == "|---:|---:|---|"
