"""Guardrail safety, randomization-unit checks and truly bounded sequential tests."""
import numpy as np
import pandas as pd
import pytest

from abtrust import Metric, analyze, sequential_test, tau_from_design


def _data(n=4000, seed=7):
    rng = np.random.default_rng(seed)
    arms = np.tile(["control", "treatment"], n // 2)
    return pd.DataFrame({
        "user_id": np.arange(n), "arm": arms,
        "conversion": rng.binomial(1, np.where(arms == "treatment", 0.45, 0.30)),
        "complaint": rng.binomial(1, 0.10, n).astype(float),
    })


def test_no_guardrails_never_auto_ships():
    df = _data()
    r = analyze(df, "arm", "control", [Metric("conversion", column="conversion", role="primary")], unit_col="user_id")
    assert r.decision().startswith("REVIEW REQUIRED")
    assert "no guardrails" in r.decision()


def test_nonsignificant_guardrail_without_margin_does_not_prove_safety():
    df = _data()
    r = analyze(df, "arm", "control", [Metric("conversion", column="conversion", role="primary"),
                                       Metric("complaint", column="complaint", role="guardrail", higher_is_better=False)],
                unit_col="user_id")
    assert "margins missing" in r.decision()
    assert "Guardrail safety screening" in r.to_markdown()


def test_declared_guardrail_margin_enables_screen_not_authorization():
    df = _data()
    r = analyze(df, "arm", "control", [Metric("conversion", column="conversion", role="primary"),
                                       Metric("complaint", column="complaint", role="guardrail", higher_is_better=False, max_harm=0.2)],
                unit_col="user_id")
    assert r.decision().startswith("SHIP CANDIDATE (review required)")
    assert r.table.loc[r.table.role == "guardrail", "safety_pass"].all()
    r2 = analyze(df, "arm", "control", [Metric("conversion", column="conversion", role="primary"),
                                        Metric("complaint", column="complaint", role="guardrail", higher_is_better=False, max_harm=0.0)],
                 unit_col="user_id")
    assert not r2.decision().startswith("SHIP")


def test_data_quality_blocks_decision():
    df = _data()
    df.loc[df.arm == "treatment", "complaint"] = np.nan
    ms = [Metric("conversion", column="conversion", role="primary"), Metric("complaint", column="complaint")]
    with pytest.raises(ValueError, match="fewer than 2"):
        analyze(df, "arm", "control", ms, unit_col="user_id")
    df = _data()
    df.loc[df.index[:80], "complaint"] = np.nan
    r = analyze(df, "arm", "control", ms, unit_col="user_id")
    assert r.data_quality_blockers
    assert r.decision().startswith("DO NOT DECIDE")


def test_duplicate_ids_and_metrics_rejected():
    df = _data()
    df.loc[0, "user_id"] = 1
    with pytest.raises(ValueError, match="unique"):
        analyze(df, "arm", "control", [Metric("conversion", column="conversion")], unit_col="user_id")
    with pytest.raises(ValueError, match="metric names"):
        analyze(_data(), "arm", "control", [Metric("same", column="conversion"), Metric("same", column="complaint")])


def test_bounded_mode_stated_guarantee_and_coverage():
    rng = np.random.default_rng(21)
    for _ in range(25):
        c = rng.binomial(1, 0.3, 600)
        t = rng.binomial(1, 0.3, 600)
        r = sequential_test(c, t, looks=20, mode="bounded")
        assert r.is_anytime_valid
        assert r.final.ci_low <= 0 <= r.final.ci_high
        assert np.all(np.diff([lk.p_value for lk in r.looks]) <= 0)
        assert r.tau is None
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        sequential_test([1, 2, 0], [0, 1, 0], looks=1, mode="bounded")


def test_known_gaussian_mode_requires_valid_design_and_prespecified_tau():
    rng = np.random.default_rng(3)
    c, t = rng.normal(size=800), rng.normal(size=800)
    with pytest.raises(ValueError, match="known_sd AND"):
        sequential_test(c, t, mode="gaussian_known_sd")
    with pytest.raises(ValueError, match="equal arm sizes"):
        sequential_test(c[:-1], t, mode="gaussian_known_sd", known_sd=1.0, tau=0.1)
    res = sequential_test(c, t, looks=10, mode="gaussian_known_sd", known_sd=1.0,
                          tau=tau_from_design(1.0, 800))
    assert res.is_anytime_valid and res.mode == "gaussian_known_sd"
    assert not sequential_test(c, t, looks=10).is_anytime_valid


def test_nonfinite_and_nonnumeric_metric_values_are_rejected():
    df = _data()
    df.loc[0, "complaint"] = float("inf")
    with pytest.raises(ValueError, match="infinity"):
        analyze(df, "arm", "control", [Metric("complaint", column="complaint")])
    df = _data()
    df["complaint"] = df.complaint.map(lambda x: f"value={x}")
    with pytest.raises(ValueError, match="numeric"):
        analyze(df, "arm", "control", [Metric("complaint", column="complaint")])
