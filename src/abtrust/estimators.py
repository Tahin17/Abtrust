"""Fixed-horizon effect estimators for two-arm experiments.

Every estimator returns an :class:`Estimate`, so different methods can be compared
side by side, and every one of them is checked by Monte Carlo simulation in
:mod:`abtrust.validation` (type-I error, confidence-interval coverage, variance
reduction).

Methods
-------
* :func:`welch_ttest` - difference in means with Welch's unequal-variance t-test.
  Works for continuous metrics and for 0/1 conversion metrics alike.
* :func:`ratio_delta` - ratio metrics (clicks per session, revenue per order)
  whose analysis unit differs from the randomization unit, using the delta method.
* :func:`cuped` - CUPED variance reduction with a pre-experiment covariate
  (Deng, Xu, Kohavi & Walker, 2013).
* :func:`lin_adjustment` - fully interacted regression adjustment with HC2 robust
  standard errors (Lin, 2013); handles several covariates.

Relative effects (``treatment / control - 1``) come with delta-method confidence
intervals that account for the uncertainty in the control mean.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

import numpy as np
from numpy.typing import ArrayLike
from scipy import special

__all__ = [
    "Estimate",
    "welch_ttest",
    "ratio_delta",
    "cuped",
    "lin_adjustment",
]


@dataclass(frozen=True)
class Estimate:
    """Result of comparing a treatment arm against control on one metric."""

    method: str
    n_control: int
    n_treatment: int
    control_mean: float
    treatment_mean: float
    effect: float
    se: float
    ci_low: float
    ci_high: float
    p_value: float
    alpha: float
    rel_effect: float | None = None
    rel_ci_low: float | None = None
    rel_ci_high: float | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def significant(self) -> bool:
        """``True`` when the two-sided p-value is below ``alpha``."""
        return self.p_value < self.alpha

    @property
    def ci_width(self) -> float:
        return self.ci_high - self.ci_low

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        extras = out.pop("extras")
        out.update({f"extra_{k}": v for k, v in extras.items()})
        return out


# --------------------------------------------------------------------------- helpers


def _as_1d(x: ArrayLike, name: str, min_size: int = 2) -> np.ndarray:
    arr = np.asarray(x, dtype=float).ravel()
    if arr.size < min_size:
        raise ValueError(f"{name} needs at least {min_size} observations, got {arr.size}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains NaN or infinite values; clean them first")
    return arr


def _check_alpha(alpha: float) -> None:
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")


def _relative_ci(
    mean_c: float, mean_t: float, var_mean_c: float, var_mean_t: float, alpha: float, cov: float = 0.0
) -> tuple[float | None, float | None, float | None]:
    """Delta-method CI for ``mean_t / mean_c - 1``.

    ``cov`` is the covariance between the two mean estimators (zero for independent
    arms, non-zero for regression-based estimators).
    """
    if not np.isfinite(mean_c) or abs(mean_c) < 1e-12:
        return None, None, None
    ratio = mean_t / mean_c
    # gradient of g(c, t) = t / c  ->  (-t / c^2, 1 / c)
    g_c, g_t = -mean_t / mean_c**2, 1.0 / mean_c
    var = g_c**2 * var_mean_c + g_t**2 * var_mean_t + 2.0 * g_c * g_t * cov
    se = float(np.sqrt(max(var, 0.0)))
    z = special.ndtri(1.0 - alpha / 2.0)
    return ratio - 1.0, ratio - 1.0 - z * se, ratio - 1.0 + z * se


def _assemble(
    *,
    method: str,
    n_c: int,
    n_t: int,
    mean_c: float,
    mean_t: float,
    var_mean_c: float,
    var_mean_t: float,
    alpha: float,
    df: float | None,
    effect: float | None = None,
    se: float | None = None,
    cov_means: float = 0.0,
    extras: dict[str, Any] | None = None,
) -> Estimate:
    effect = mean_t - mean_c if effect is None else effect
    se = float(np.sqrt(var_mean_c + var_mean_t - 2.0 * cov_means)) if se is None else se
    normal = df is None or not np.isfinite(df)
    if se > 0:
        stat = abs(effect / se)
        # scipy.special is ~30x faster than scipy.stats for scalar calls (matters in simulations)
        p_value = float(2.0 * (special.ndtr(-stat) if normal else special.stdtr(df, -stat)))
        crit = float(special.ndtri(1.0 - alpha / 2.0) if normal else special.stdtrit(df, 1.0 - alpha / 2.0))
    else:  # degenerate: no variance at all
        p_value = 1.0 if effect == 0 else 0.0
        crit = 0.0
    rel, rel_lo, rel_hi = _relative_ci(mean_c, mean_t, var_mean_c, var_mean_t, alpha, cov_means)
    return Estimate(
        method=method,
        n_control=int(n_c),
        n_treatment=int(n_t),
        control_mean=float(mean_c),
        treatment_mean=float(mean_t),
        effect=float(effect),
        se=float(se),
        ci_low=float(effect - crit * se),
        ci_high=float(effect + crit * se),
        p_value=p_value,
        alpha=alpha,
        rel_effect=rel,
        rel_ci_low=rel_lo,
        rel_ci_high=rel_hi,
        extras=dict(extras or {}),
    )


# ------------------------------------------------------------------------ estimators


def welch_ttest(control: ArrayLike, treatment: ArrayLike, alpha: float = 0.05) -> Estimate:
    """Difference in means with Welch's t-test (unequal variances).

    Parameters
    ----------
    control, treatment:
        One value per randomization unit (user). 0/1 values give a conversion-rate test.
    alpha:
        Two-sided significance level; the confidence level is ``1 - alpha``.
    """
    _check_alpha(alpha)
    c = _as_1d(control, "control")
    t = _as_1d(treatment, "treatment")
    n_c, n_t = c.size, t.size
    a, b = c.var(ddof=1) / n_c, t.var(ddof=1) / n_t
    denom = (a**2 / (n_c - 1) if a else 0.0) + (b**2 / (n_t - 1) if b else 0.0)
    df = (a + b) ** 2 / denom if denom > 0 else float(n_c + n_t - 2)
    return _assemble(
        method="welch",
        n_c=n_c,
        n_t=n_t,
        mean_c=c.mean(),
        mean_t=t.mean(),
        var_mean_c=a,
        var_mean_t=b,
        alpha=alpha,
        df=df,
        extras={"df": float(df)},
    )


def _ratio_moments(num: np.ndarray, den: np.ndarray) -> tuple[float, float, int]:
    """Ratio of means and the delta-method variance of that ratio for one arm."""
    n = num.size
    mu_n, mu_d = num.mean(), den.mean()
    if mu_d <= 0:
        raise ValueError("denominator must have a positive mean (e.g. sessions per user)")
    cov = np.cov(num, den, ddof=1)
    s_nn, s_dd, s_nd = cov[0, 0], cov[1, 1], cov[0, 1]
    ratio = mu_n / mu_d
    var = (s_nn / mu_d**2 - 2.0 * mu_n * s_nd / mu_d**3 + mu_n**2 * s_dd / mu_d**4) / n
    return float(ratio), float(max(var, 0.0)), n


def ratio_delta(
    numerator_control: ArrayLike,
    denominator_control: ArrayLike,
    numerator_treatment: ArrayLike,
    denominator_treatment: ArrayLike,
    alpha: float = 0.05,
) -> Estimate:
    """Compare ratio metrics such as clicks per session using the delta method.

    Inputs are **per randomization unit** totals: for "clicks per session" pass each
    user's total clicks as the numerator and each user's session count as the
    denominator. Treating sessions as independent (the common mistake) ignores the
    correlation between sessions of the same user and gives confidence intervals
    that are too narrow; :mod:`abtrust.validation` quantifies by how much.
    """
    _check_alpha(alpha)
    nc_, dc_ = _as_1d(numerator_control, "numerator_control"), _as_1d(denominator_control, "denominator_control")
    nt_, dt_ = (
        _as_1d(numerator_treatment, "numerator_treatment"),
        _as_1d(denominator_treatment, "denominator_treatment"),
    )
    if nc_.size != dc_.size or nt_.size != dt_.size:
        raise ValueError("numerator and denominator must have one entry per unit in each arm")
    r_c, v_c, n_c = _ratio_moments(nc_, dc_)
    r_t, v_t, n_t = _ratio_moments(nt_, dt_)
    return _assemble(
        method="delta_ratio",
        n_c=n_c,
        n_t=n_t,
        mean_c=r_c,
        mean_t=r_t,
        var_mean_c=v_c,
        var_mean_t=v_t,
        alpha=alpha,
        df=None,
        extras={"denominator_total_control": float(dc_.sum()), "denominator_total_treatment": float(dt_.sum())},
    )


def cuped(
    y_control: ArrayLike,
    y_treatment: ArrayLike,
    x_control: ArrayLike,
    x_treatment: ArrayLike,
    alpha: float = 0.05,
) -> Estimate:
    """CUPED: reduce variance with a pre-experiment covariate.

    The adjusted outcome is ``y - theta * (x - mean(x))`` with
    ``theta = cov(x, y) / var(x)`` estimated on both arms pooled. Because ``x`` is
    measured before randomization, the adjustment cannot bias the treatment effect;
    it removes the part of ``y``'s variance that ``x`` predicts, shrinking the
    variance by roughly ``corr(x, y) ** 2``.

    ``x`` must be unaffected by treatment (use pre-period data only).
    """
    _check_alpha(alpha)
    yc, yt = _as_1d(y_control, "y_control"), _as_1d(y_treatment, "y_treatment")
    xc, xt = _as_1d(x_control, "x_control"), _as_1d(x_treatment, "x_treatment")
    if yc.size != xc.size or yt.size != xt.size:
        raise ValueError("each outcome needs exactly one covariate value")
    y = np.concatenate([yc, yt])
    x = np.concatenate([xc, xt])
    var_x = x.var(ddof=1)
    theta = float(np.cov(x, y, ddof=1)[0, 1] / var_x) if var_x > 0 else 0.0
    x_bar = x.mean()
    yc_adj = yc - theta * (xc - x_bar)
    yt_adj = yt - theta * (xt - x_bar)
    base = welch_ttest(yc_adj, yt_adj, alpha=alpha)
    var_y = y.var(ddof=1)
    var_adj = np.concatenate([yc_adj, yt_adj]).var(ddof=1)
    reduction = float(1.0 - var_adj / var_y) if var_y > 0 else 0.0
    corr = float(np.corrcoef(x, y)[0, 1]) if var_x > 0 and var_y > 0 else 0.0
    extras = dict(base.extras)
    extras.update({"theta": theta, "variance_reduction": reduction, "covariate_corr": corr})
    return replace(base, method="cuped", extras=extras)


def lin_adjustment(
    y: ArrayLike,
    treatment: ArrayLike,
    covariates: ArrayLike,
    alpha: float = 0.05,
) -> Estimate:
    """Regression adjustment with treatment-by-covariate interactions (Lin, 2013).

    Fits ``y ~ 1 + T + Xc + T:Xc`` with covariates centred at their overall mean, so
    the coefficient on ``T`` is the average treatment effect. Standard errors are
    HC2 heteroskedasticity-robust, which keeps inference valid even when the
    regression model is wrong. With one covariate this is CUPED with separate slopes
    per arm; with several (or with an ML prediction as covariate) it is the
    CUPAC-style generalisation.
    """
    _check_alpha(alpha)
    yv = _as_1d(y, "y")
    tv = _as_1d(treatment, "treatment")
    if not np.all(np.isin(tv, (0.0, 1.0))):
        raise ValueError("treatment must be coded 0 (control) / 1 (treatment)")
    X = np.asarray(covariates, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    if X.shape[0] != yv.size or tv.size != yv.size:
        raise ValueError("y, treatment and covariates must have the same number of rows")
    if not np.all(np.isfinite(X)):
        raise ValueError("covariates contain NaN or infinite values")
    n_t = int(tv.sum())
    n_c = int(yv.size - n_t)
    if n_c < 2 or n_t < 2:
        raise ValueError("each arm needs at least 2 observations")

    Xc = X - X.mean(axis=0)
    design = np.column_stack([np.ones_like(yv), tv, Xc, Xc * tv[:, None]])
    n, p = design.shape
    xtx_inv = np.linalg.pinv(design.T @ design)
    beta = xtx_inv @ design.T @ yv
    resid = yv - design @ beta
    leverage = np.einsum("ij,jk,ik->i", design, xtx_inv, design)
    omega = resid**2 / np.clip(1.0 - leverage, 1e-12, None)
    meat = (design * omega[:, None]).T @ design
    vcov = xtx_inv @ meat @ xtx_inv  # HC2 sandwich

    b0, b1 = beta[0], beta[1]
    v00, v11, v01 = vcov[0, 0], vcov[1, 1], vcov[0, 1]
    # control mean = b0, treatment mean = b0 + b1 (both at the covariate mean)
    var_mean_t = v00 + v11 + 2.0 * v01
    cov_c_t = v00 + v01
    return _assemble(
        method="lin_hc2",
        n_c=n_c,
        n_t=n_t,
        mean_c=b0,
        mean_t=b0 + b1,
        var_mean_c=v00,
        var_mean_t=var_mean_t,
        cov_means=cov_c_t,
        effect=b1,
        se=float(np.sqrt(v11)),
        alpha=alpha,
        df=float(n - p),
        extras={"n_covariates": X.shape[1], "r_squared": float(1.0 - resid.var() / yv.var()) if yv.var() > 0 else 0.0},
    )
