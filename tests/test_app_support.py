"""CSV and allocation checks used by the dashboard and CLI."""

import numpy as np
import pandas as pd
import pytest

from abtrust import Metric, analyze
from abtrust.app_support import (
    arm_labels,
    expected_split_from_percentages,
    load_uploaded_csv,
    parse_harm_margin,
    validate_table,
)
from abtrust.checks import srm_test


def test_clean_uploaded_csv_and_bom():
    data = b'\xef\xbb\xbfuser_id,variant,converted\n1,control,0\n2,treatment,1\n'
    frame = load_uploaded_csv(data)
    assert list(frame.columns) == ["user_id", "variant", "converted"]
    assert arm_labels(frame, "variant") == ["control", "treatment"]


@pytest.mark.parametrize("data,contains", [
    (b"", "empty"),
    (b"hello", "no data"),
    (b"arm,converted\n", "no data"),
    (b"arm,converted\n\xff,1", "Unable to read"),
    (b"arm,outcome,outcome\nA,1,2\nB,2,3", "duplicate header"),
])
def test_bad_uploaded_csv_rejected(data, contains):
    with pytest.raises(ValueError, match=contains):
        load_uploaded_csv(data)


def test_large_csv_rejected_without_parsing():
    with pytest.raises(ValueError, match="limit"):
        load_uploaded_csv(b"abc", max_bytes=2)


def test_missing_or_single_arm_rejected():
    df = pd.DataFrame({"arm": ["control", None], "outcome": [0, 1]})
    with pytest.raises(ValueError, match="missing"):
        arm_labels(df, "arm")
    df.loc[1, "arm"] = "control"
    with pytest.raises(ValueError, match="at least two"):
        arm_labels(df, "arm")


def test_no_numeric_outcomes_rejected():
    with pytest.raises(ValueError, match="numeric"):
        validate_table(pd.DataFrame({"variant": ["a", "b"], "words": ["x", "y"]}))


def test_custom_allocation_percents_are_design_not_observation():
    alloc = expected_split_from_percentages(["control", "treatment"], {"control": 20, "treatment": 80})
    assert alloc == {"control": 0.2, "treatment": 0.8}
    df = pd.DataFrame({"user_id": range(1000), "arm": ["control"] * 200 + ["treatment"] * 800,
                       "outcome": [0] * 1000})
    r = analyze(df, "arm", "control", [Metric("outcome", column="outcome")],
                expected_split=alloc, unit_col="user_id")
    assert not r.srm.flagged
    assert srm_test([200, 800]).flagged


@pytest.mark.parametrize("shares", [
    {"control": 49, "treatment": 50},
    {"control": 0, "treatment": 100},
    {"control": 50, "treatment": float("nan")},
    {"control": float("inf"), "treatment": 0},
    {"control": -1, "treatment": 101},
])
def test_invalid_allocation(shares):
    with pytest.raises(ValueError):
        expected_split_from_percentages(["control", "treatment"], shares)


def test_missing_allocation_arm():
    with pytest.raises(ValueError, match="every arm"):
        expected_split_from_percentages(["control", "treatment"], {"control": 100})


@pytest.mark.parametrize("text", ["abc", "-0.01", "nan", "inf", "-inf"])
def test_invalid_guardrail_harm_margin(text):
    with pytest.raises(ValueError):
        parse_harm_margin(text, "unsubscribed")


def test_guardrail_margin_zero_and_missing_are_different():
    assert parse_harm_margin("", "unsubscribed") is None
    assert parse_harm_margin("0", "unsubscribed") == 0.0
    assert parse_harm_margin(" 0.001 ", "unsubscribed") == pytest.approx(0.001)


def test_srm_rejects_nonsensical_nonfinite_inputs():
    with pytest.raises(ValueError, match="counts"):
        srm_test([np.nan, 12])
    with pytest.raises(ValueError, match="expected_ratios"):
        srm_test([100, 100], [float("inf"), 1])
    with pytest.raises(ValueError, match="threshold"):
        srm_test([100, 100], threshold=float("nan"))
