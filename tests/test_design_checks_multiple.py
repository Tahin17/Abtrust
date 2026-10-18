import numpy as np
import pytest

from abtrust import (
    benjamini_hochberg,
    holm,
    mde_mean,
    power_mean,
    sample_size_mean,
    sample_size_proportion,
    srm_test,
)
from abtrust.multiple import adjust

# ------------------------------------------------------------------ design


def test_proportion_sample_size_textbook_value():
    # 10% -> 11%: (1.96 + 0.8416)^2 * (0.09 + 0.0979) / 0.01^2 = 14,749
    plan = sample_size_proportion(0.10, 0.01)
    assert plan.n_control == 14_749
    assert plan.total == 2 * 14_749
    assert sample_size_proportion(0.10, 0.10, relative=True).n_control == plan.n_control


def test_mean_sample_size_power_and_mde_are_consistent():
    plan = sample_size_mean(mde=0.5, sd=4.0)
    assert power_mean(plan.n_control, 0.5, 4.0) == pytest.approx(0.80, abs=0.002)
    assert mde_mean(plan.n_control, 4.0) == pytest.approx(0.5, rel=0.002)


def test_variance_reduction_shrinks_sample_size():
    raw = sample_size_mean(0.1, 1.0)
    adj = sample_size_mean(0.1, 1.0, variance_reduction=0.36)
    assert adj.n_control == pytest.approx(raw.n_control * 0.64, rel=0.002)


def test_unequal_allocation():
    plan = sample_size_mean(0.1, 1.0, ratio=2.0)
    assert plan.n_treatment == pytest.approx(2 * plan.n_control, abs=1)
    assert power_mean(plan.n_control, 0.1, 1.0, ratio=2.0) == pytest.approx(0.8, abs=0.003)


def test_days_and_errors():
    plan = sample_size_proportion(0.05, 0.01)
    assert plan.days(plan.total) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        plan.days(0)
    with pytest.raises(ValueError):
        sample_size_proportion(1.2, 0.01)
    with pytest.raises(ValueError):
        sample_size_mean(0.0, 1.0)
    with pytest.raises(ValueError):
        sample_size_mean(0.1, 1.0, variance_reduction=1.0)


# ------------------------------------------------------------------ SRM


def test_srm_balanced_not_flagged():
    res = srm_test([50_120, 49_880])
    assert not res.flagged
    assert res.p_value > 0.4


def test_srm_detects_imbalance():
    res = srm_test([50_000, 48_500])
    assert res.flagged
    assert "SRM DETECTED" in res.summary()


def test_srm_respects_designed_split():
    assert not srm_test([90_100, 9_900], [90, 10]).flagged
    assert srm_test([90_100, 9_900]).flagged
    res = srm_test([200, 300, 500], [0.2, 0.3, 0.5])
    assert res.expected_ratios == pytest.approx((0.2, 0.3, 0.5))
    assert res.p_value == pytest.approx(1.0)


def test_srm_input_validation():
    with pytest.raises(ValueError):
        srm_test([100])
    with pytest.raises(ValueError):
        srm_test([10, -1])
    with pytest.raises(ValueError):
        srm_test([10, 10], [1, 0])


# ------------------------------------------------------------------ multiple testing


def test_holm_known_values():
    np.testing.assert_allclose(holm([0.01, 0.04, 0.03, 0.2]), [0.04, 0.09, 0.09, 0.2])


def test_bh_known_values():
    np.testing.assert_allclose(benjamini_hochberg([0.01, 0.04, 0.03, 0.2]), [0.04, 0.16 / 3, 0.16 / 3, 0.2])


def test_adjusted_pvalues_are_bounded_and_ordered():
    rng = np.random.default_rng(0)
    p = rng.random(50) ** 3
    for method in ("holm", "bh"):
        adj = adjust(p, method)
        assert np.all(adj >= p - 1e-15) and np.all(adj <= 1)
        order = np.argsort(p)
        assert np.all(np.diff(adj[order]) >= -1e-15)
    assert np.all(holm(p) >= benjamini_hochberg(p) - 1e-15)
    np.testing.assert_array_equal(adjust(p, "none"), p)
    with pytest.raises(ValueError):
        adjust(p, "bonferroni-ish")
