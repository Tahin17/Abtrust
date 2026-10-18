"""Regression cases for invalid settings that must never silently change an analysis."""

import numpy as np
import pandas as pd
import pytest

import abtrust as ab
from abtrust.cli import main
from abtrust.sequential import always_valid_halfwidth, mixture_log_lr


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), 0, -1])
def test_planning_rejects_invalid_spreads_and_allocation(bad):
    for kwargs in ({"sd": bad}, {"sd": 1, "ratio": bad}, {"sd": 1, "sd_treatment": bad}):
        with pytest.raises(ValueError):
            ab.sample_size_mean(0.1, **kwargs)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_effects_and_sequential_scales_rejected(bad):
    for call in (
        lambda: ab.sample_size_mean(bad, 1),
        lambda: ab.power_mean(100, bad, 1),
        lambda: ab.tau_from_design(bad, 100),
        lambda: ab.sequential_test(np.arange(20), np.arange(20), looks=2, tau=bad),
        lambda: mixture_log_lr(0.1, 0.1, bad),
        lambda: always_valid_halfwidth(0.1, bad),
    ):
        with pytest.raises(ValueError):
            call()


@pytest.mark.parametrize("looks", [[], [0.5, np.nan], [np.inf], True, [0.5, 0.5]])
def test_invalid_monitoring_schedules_rejected(looks):
    with pytest.raises(ValueError, match="looks"):
        ab.sequential_test(np.zeros(100), np.zeros(100), looks=looks, mode="bounded")


def test_zero_effect_and_small_plans_have_defined_behavior():
    with pytest.raises(ValueError, match="non-zero"):
        ab.sample_size_proportion(0.1, 0)
    assert ab.power_mean(100, 0, 1) == pytest.approx(0.05)
    plan = ab.sample_size_mean(1000, 1, ratio=0.1)
    assert min(plan.n_control, plan.n_treatment) >= 2


@pytest.mark.parametrize("options", [
    ["--primary", "typo"], ["--guardrail", "typo"], ["--lower-is-better", "typo"],
    ["--primary", "converted", "--guardrail", "converted"],
    ["--guardrail-max-harm", "converted=0.01"],
    ["--guardrail", "converted", "--guardrail-max-harm", "converted=0.01",
     "--guardrail-max-harm", "converted=0.02"],
])
def test_cli_rejects_undeclared_or_conflicting_roles(tmp_path, capsys, options):
    path = tmp_path / "data.csv"
    pd.DataFrame({"arm": ["A", "A", "B", "B"], "converted": [0, 1, 0, 1]}).to_csv(path, index=False)
    with pytest.raises(SystemExit) as error:
        main(["analyze", str(path), "--arm", "arm", "--control", "A", "--metric", "converted", *options])
    assert error.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_lin_rejects_nonidentifiable_and_saturated_designs():
    treatment = np.r_[np.zeros(5), np.ones(5)]
    with pytest.raises(ValueError, match="not identifiable"):
        ab.lin_adjustment(np.arange(10), treatment, treatment)
    with pytest.raises(ValueError, match="degrees of freedom|unit leverage"):
        ab.lin_adjustment(np.arange(4), [0, 0, 1, 1], [0, 1, 0, 1])


def test_lin_redundancy_and_covariate_units_preserve_effect_and_se():
    rng = np.random.default_rng(108)
    x = rng.normal(size=500)
    treatment = np.tile([0, 1], 250)
    y = 3 + treatment * 0.3 + x + rng.normal(size=500)
    reference = ab.lin_adjustment(y, treatment, x)
    redundant = ab.lin_adjustment(y, treatment, np.column_stack([x * 1e12, x, np.ones(500)]))
    assert redundant.effect == pytest.approx(reference.effect, abs=1e-10)
    assert redundant.se == pytest.approx(reference.se, rel=1e-10)
    assert redundant.extras["df"] == reference.extras["df"]
