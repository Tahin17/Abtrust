import numpy as np
import pytest
from scipy import stats

from abtrust import cuped, lin_adjustment, ratio_delta, welch_ttest
from abtrust.simulate import pre_post_normal, sessions_clicks


def test_welch_matches_scipy():
    rng = np.random.default_rng(0)
    c, t = rng.normal(10, 2, 500), rng.normal(10.3, 3, 700)
    est = welch_ttest(c, t)
    ref = stats.ttest_ind(t, c, equal_var=False)
    assert est.p_value == pytest.approx(ref.pvalue, rel=1e-10)
    ci = ref.confidence_interval()
    assert est.ci_low == pytest.approx(ci.low, rel=1e-10)
    assert est.ci_high == pytest.approx(ci.high, rel=1e-10)
    assert est.effect == pytest.approx(t.mean() - c.mean())


def test_relative_effect_and_interval():
    rng = np.random.default_rng(1)
    c, t = rng.normal(100, 10, 5000), rng.normal(105, 10, 5000)
    est = welch_ttest(c, t)
    assert est.rel_effect == pytest.approx(t.mean() / c.mean() - 1)
    assert est.rel_ci_low < est.rel_effect < est.rel_ci_high
    assert est.rel_ci_low > 0  # 5% lift with n=5000 is unmistakable


def test_relative_effect_undefined_for_zero_control_mean():
    est = welch_ttest([-1.0, 1.0, -1.0, 1.0], [0.5, 1.5, 0.5, 1.5])
    assert est.rel_effect is None


def test_input_validation():
    with pytest.raises(ValueError, match="at least 2"):
        welch_ttest([1.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="NaN"):
        welch_ttest([1.0, np.nan, 2.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="alpha"):
        welch_ttest([1.0, 2.0], [1.0, 2.0], alpha=1.5)


def test_ratio_with_unit_denominators_equals_mean_comparison():
    rng = np.random.default_rng(2)
    nc, nt = rng.normal(5, 1, 400), rng.normal(5.2, 1, 400)
    ones = np.ones(400)
    r = ratio_delta(nc, ones, nt, ones)
    w = welch_ttest(nc, nt)
    assert r.effect == pytest.approx(w.effect)
    # delta-method variance uses n-1 like Welch, so SEs agree exactly
    assert r.se == pytest.approx(w.se, rel=1e-12)


def test_ratio_point_estimate_is_ratio_of_totals():
    rng = np.random.default_rng(3)
    cc, sc = sessions_clicks(rng, 3000, icc=0.1)
    ct, st = sessions_clicks(rng, 3000, icc=0.1, lift=0.1)
    est = ratio_delta(cc, sc, ct, st)
    assert est.control_mean == pytest.approx(cc.sum() / sc.sum())
    assert est.treatment_mean == pytest.approx(ct.sum() / st.sum())


def test_ratio_rejects_bad_denominator():
    with pytest.raises(ValueError, match="positive mean"):
        ratio_delta([1, 2], [0, 0], [1, 2], [1, 1])
    with pytest.raises(ValueError, match="one entry per unit"):
        ratio_delta([1, 2, 3], [1, 1], [1, 2], [1, 1])


def test_cuped_with_constant_covariate_equals_welch():
    rng = np.random.default_rng(4)
    yc, yt = rng.normal(0, 1, 300), rng.normal(0.2, 1, 300)
    est = cuped(yc, yt, np.ones(300), np.ones(300))
    ref = welch_ttest(yc, yt)
    assert est.effect == pytest.approx(ref.effect)
    assert est.se == pytest.approx(ref.se)
    assert est.extras["theta"] == 0.0


def test_cuped_reduces_variance_by_rho_squared():
    rng = np.random.default_rng(5)
    xc, yc = pre_post_normal(rng, 20_000, rho=0.8)
    xt, yt = pre_post_normal(rng, 20_000, rho=0.8, effect=0.05)
    est = cuped(yc, yt, xc, xt)
    assert est.extras["variance_reduction"] == pytest.approx(0.64, abs=0.02)
    assert est.se < 0.65 * welch_ttest(yc, yt).se


def test_lin_without_covariate_information_reproduces_neyman_se():
    """With no covariate signal, HC2 regression SE equals the Welch/Neyman SE exactly."""
    rng = np.random.default_rng(6)
    yc, yt = rng.exponential(2.0, 250), rng.exponential(2.5, 350)
    y = np.r_[yc, yt]
    treat = np.r_[np.zeros(250), np.ones(350)]
    est = lin_adjustment(y, treat, np.zeros((600, 1)))
    ref = welch_ttest(yc, yt)
    assert est.effect == pytest.approx(ref.effect, rel=1e-10)
    assert est.se == pytest.approx(ref.se, rel=1e-8)
    assert est.control_mean == pytest.approx(yc.mean())


def test_lin_agrees_with_cuped_for_one_covariate():
    rng = np.random.default_rng(7)
    xc, yc = pre_post_normal(rng, 5000, rho=0.6)
    xt, yt = pre_post_normal(rng, 5000, rho=0.6, effect=0.1)
    a = cuped(yc, yt, xc, xt)
    b = lin_adjustment(np.r_[yc, yt], np.r_[np.zeros(5000), np.ones(5000)], np.r_[xc, xt])
    assert b.effect == pytest.approx(a.effect, abs=0.01)
    assert b.se == pytest.approx(a.se, rel=0.02)


def test_lin_multiple_covariates_and_validation():
    rng = np.random.default_rng(8)
    n = 4000
    X = rng.normal(size=(n, 3))
    treat = (rng.random(n) < 0.5).astype(float)
    y = 1.0 + 0.3 * treat + X @ np.array([0.5, -0.2, 0.1]) + rng.normal(0, 1, n)
    est = lin_adjustment(y, treat, X)
    assert est.ci_low < 0.3 < est.ci_high
    assert est.extras["n_covariates"] == 3
    with pytest.raises(ValueError, match="coded 0"):
        lin_adjustment(y, treat * 2, X)


def test_estimate_to_dict_flattens_extras():
    d = welch_ttest([1.0, 2.0, 3.0], [2.0, 3.0, 4.0]).to_dict()
    assert "extra_df" in d and "extras" not in d
