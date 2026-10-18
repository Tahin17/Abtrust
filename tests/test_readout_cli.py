import io
from contextlib import redirect_stdout

import numpy as np
import pandas as pd
import pytest

from abtrust import Metric, analyze
from abtrust.cli import main
from abtrust.simulate import ecommerce_experiment


def _toy(n=6000, seed=0, lift=0.0, drop_treatment=0):
    rng = np.random.default_rng(seed)
    arm = np.where(rng.random(n) < 0.5, "B", "A")
    pre = rng.gamma(2, 5, n)
    rev = np.maximum(0, pre * 0.8 + rng.normal(0, 5, n) + (arm == "B") * lift)
    sessions = 1 + rng.poisson(3, n)
    clicks = rng.binomial(sessions, 0.2)
    df = pd.DataFrame(
        {
            "arm": arm,
            "pre": pre,
            "revenue": rev,
            "converted": (rev > 8).astype(int),
            "sessions": sessions,
            "clicks": clicks,
        }
    )
    if drop_treatment:
        idx = df.index[df.arm == "B"][:drop_treatment]
        df = df.drop(idx)
    return df


METRICS = [
    Metric("converted", column="converted", role="primary"),
    Metric("revenue", column="revenue", covariate="pre"),
    Metric("ctr", numerator="clicks", denominator="sessions", role="guardrail"),
]


def test_analyze_table_and_markdown():
    ro = analyze(_toy(lift=2.0), "arm", "A", METRICS)
    t = ro.table
    assert list(t.metric) == ["converted", "revenue", "ctr"]
    assert set(t.method) == {"welch", "cuped", "delta_ratio"}
    assert (t.p_adjusted >= t.p_value - 1e-12).all()
    rev = t.set_index("metric").loc["revenue"]
    assert rev.variance_reduction > 0.3
    md = ro.to_markdown()
    assert "## 1. Sample ratio mismatch" in md and "**PASS**" in md
    assert "CUPED with `pre`" in md
    assert ro.decision().startswith(("REVIEW REQUIRED", "MIXED", "INCONCLUSIVE"))


def test_srm_invalidates_every_verdict():
    ro = analyze(_toy(drop_treatment=300), "arm", "A", METRICS)
    assert ro.srm.flagged
    assert set(ro.table.verdict) == {"invalid (SRM)"}
    assert ro.decision().startswith("DO NOT DECIDE")
    assert "**FAIL**" in ro.to_markdown()


def test_guardrail_regression_blocks_ship():
    df = _toy(seed=3)
    df.loc[df.arm == "B", "clicks"] = (df.loc[df.arm == "B", "clicks"] * 0.7).round()
    ro = analyze(df, "arm", "A", METRICS)
    assert "ctr" in ro.decision() and ro.decision().startswith("DO NOT SHIP")


def test_lower_is_better_and_multi_arm():
    rng = np.random.default_rng(5)
    n = 9000
    arm = rng.choice(["ctrl", "v1", "v2"], n)
    latency = rng.normal(300, 30, n) - (arm == "v2") * 15
    ro = analyze(
        pd.DataFrame({"g": arm, "latency": latency}),
        "g",
        "ctrl",
        [Metric("latency", column="latency", higher_is_better=False, role="primary")],
    )
    t = ro.table.set_index("arm")
    assert t.loc["v2", "verdict"] == "significant improvement"
    assert len(t) == 2


def test_missing_values_are_dropped_with_a_note():
    df = _toy()
    df.loc[df.index[:10], "revenue"] = np.nan
    ro = analyze(df, "arm", "A", [Metric("revenue", column="revenue")])
    assert any("dropped 10" in note for note in ro.notes)


def test_metric_and_input_validation():
    with pytest.raises(ValueError):
        Metric("x")
    with pytest.raises(ValueError):
        Metric("x", column="a", numerator="b", denominator="c")
    with pytest.raises(ValueError):
        Metric("x", numerator="a", denominator="b", covariate="c")
    with pytest.raises(ValueError):
        Metric("x", column="a", role="vip")
    df = _toy()
    with pytest.raises(KeyError):
        analyze(df, "arm", "A", [Metric("nope", column="nope")])
    with pytest.raises(ValueError):
        analyze(df, "arm", "Z", METRICS)
    with pytest.raises(ValueError):
        analyze(df, "arm", "A", METRICS, expected_split={"A": 1})


def test_ecommerce_generator_plants_the_srm_bug():
    logged, full, truth = ecommerce_experiment(n_users=40_000, seed=1)
    assert len(logged) < len(full)
    lost = full.variant.value_counts()["treatment"] - logged.variant.value_counts()["treatment"]
    assert lost > 0
    assert logged.variant.value_counts()["control"] == full.variant.value_counts()["control"]
    assert truth["all_users"].orders_per_session_rel == pytest.approx(0.04)
    assert 0 < truth["all_users"].conversion_rel < 0.04


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def test_cli_plan():
    code, out = _run(["plan", "--baseline", "0.1", "--mde", "0.01", "--daily", "10000"])
    assert code == 0 and "14,749 control" in out and "days" in out
    code, out = _run(["plan", "--sd", "1", "--mde", "0.1", "--rho", "0.6"])
    assert code == 0


def test_cli_analyze(tmp_path):
    data = tmp_path / "exp.csv"
    _toy(lift=1.0).to_csv(data, index=False)
    out = tmp_path / "readout.md"
    code, printed = _run(
        [
            "analyze",
            str(data),
            "--arm",
            "arm",
            "--control",
            "A",
            "--metric",
            "converted",
            "--metric",
            "revenue:pre",
            "--ratio",
            "clicks/sessions",
            "--primary",
            "converted",
            "--split",
            "50,50",
            "--out",
            str(out),
            "--title",
            "Experiment — café",
        ]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "Experiment — café" in text
    assert "clicks/sessions" in text and "cuped" in text
    assert printed.strip()
