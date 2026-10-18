import numpy as np
import pytest
from scipy import stats

from abtrust import sequential_test, tau_for_horizon
from abtrust.sequential import _optimal_ratio, always_valid_halfwidth, mixture_log_lr


def test_log_lr_equals_ratio_of_normal_densities():
    d, se, tau = 0.3, 0.1, 0.25
    expected = np.log(stats.norm.pdf(d, 0, np.hypot(se, tau)) / stats.norm.pdf(d, 0, se))
    assert float(mixture_log_lr(d, se, tau)) == pytest.approx(expected, rel=1e-12)


def test_confidence_sequence_inverts_the_test():
    """At the edge of the confidence sequence the likelihood ratio is exactly 1/alpha."""
    se, tau, alpha = 0.04, 0.1, 0.05
    hw = float(always_valid_halfwidth(se, tau, alpha))
    assert float(mixture_log_lr(hw, se, tau)) == pytest.approx(np.log(1 / alpha), rel=1e-10)


def test_tau_for_horizon_minimises_width_at_horizon():
    se = 0.01
    tau = tau_for_horizon(se)
    best = float(always_valid_halfwidth(se, tau))
    for factor in (0.7, 1.4):
        assert float(always_valid_halfwidth(se, tau * factor)) > best
    # about 1.55x the fixed-horizon half-width at alpha = 0.05
    assert best / (1.96 * se) == pytest.approx(1.548, abs=0.01)
    assert _optimal_ratio(0.05) == pytest.approx(8.2, abs=0.2)


def test_sequential_outputs_are_monotone():
    rng = np.random.default_rng(0)
    c, t = rng.normal(0, 1, 4000), rng.normal(0.08, 1, 4000)
    res = sequential_test(c, t, looks=40)
    p = np.array([lk.p_value for lk in res.looks])
    lo = np.array([lk.ci_low for lk in res.looks])
    hi = np.array([lk.ci_high for lk in res.looks])
    assert np.all(np.diff(p) <= 0)
    assert np.all(np.diff(lo) >= 0) and np.all(np.diff(hi) <= 0)
    assert res.final.n_control == 4000
    assert len(res.to_frame()) == 40


def test_always_valid_interval_is_wider_than_naive():
    rng = np.random.default_rng(1)
    c, t = rng.normal(0, 1, 2000), rng.normal(0, 1, 2000)
    res = sequential_test(c, t, looks=1)
    lk = res.final
    assert lk.ci_high - lk.ci_low > lk.naive_ci_high - lk.naive_ci_low


def test_detects_large_effect_early():
    rng = np.random.default_rng(2)
    c, t = rng.normal(0, 1, 5000), rng.normal(0.3, 1, 5000)
    res = sequential_test(c, t, looks=50)
    assert res.stop_index is not None and res.stop_index < 25


def test_handles_shifted_large_values():
    rng = np.random.default_rng(3)
    c, t = 1e6 + rng.normal(0, 1, 1000), 1e6 + rng.normal(0, 1, 1000)
    res = sequential_test(c, t, looks=10)
    assert np.isfinite(res.final.se) and res.final.se == pytest.approx(np.sqrt(2 / 1000), rel=0.1)


def test_validation_errors():
    with pytest.raises(ValueError):
        sequential_test([1.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        sequential_test(np.ones(10), np.ones(10), looks=[0.5, 0.2])
    with pytest.raises(ValueError):
        mixture_log_lr(0.1, 0.1, tau=0.0)


@pytest.mark.slow
def test_msprt_controls_false_positives_under_continuous_peeking():
    rng = np.random.default_rng(4)
    n_sims, n = 400, 3000
    tau = tau_for_horizon(np.sqrt(2 / n))
    naive = av = 0
    for _ in range(n_sims):
        res = sequential_test(rng.normal(0, 1, n), rng.normal(0, 1, n), looks=30, tau=tau)
        av += res.stop_index is not None
        naive += res.naive_stop_index is not None
    assert av / n_sims <= 0.05 + 2 * np.sqrt(0.05 * 0.95 / n_sims)
    assert naive / n_sims > 0.12  # peeking 30 times is far above 5%
