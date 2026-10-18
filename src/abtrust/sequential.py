"""Sequential analyses with explicitly differentiated guarantees.

* ``mode='working_normal'`` retains the original plug-in-variance mixture-SPRT
  calculation for backwards-compatible demonstrations. Estimated standard errors
  are inserted in a *known-variance* Gaussian likelihood ratio; this is NOT an
  exact nonnegative martingale and is NOT certified anytime-valid.
* ``mode='bounded'`` gives a finite-sample confidence sequence for independent
  per-unit observations in [0, 1] via Hoeffding's inequality and summable
  alpha-spending over the ordered monitoring looks. This is genuinely safe for
  optional stopping at those looks under the stated independent, bounded,
  fixed-population assumptions (not for clustered/nonrandomized time series).
* ``mode='gaussian_known_sd'`` uses the exact Gaussian normal-mixture LR for
  independent normally distributed observations with KNOWN per-arm SDs and a
  mixing scale ``tau`` chosen before seeing outcomes. Both are required.

The old functions ``mixture_log_lr`` and ``always_valid_halfwidth`` give the
known-variance algebra; do not interpret their plug-in use as a guarantee.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import ArrayLike
from scipy import optimize, stats

from ._inputs import finite_scalar, positive_integer, positive_scalar


def _alpha(alpha: float) -> float:
    alpha = finite_scalar(alpha, "alpha")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    return alpha


def _standard_errors(se: ArrayLike) -> np.ndarray:
    values = np.asarray(se, dtype=float)
    if not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("standard errors must be finite and nonnegative")
    return values

__all__ = [
    "Look",
    "SequentialResult",
    "mixture_log_lr",
    "always_valid_halfwidth",
    "tau_for_horizon",
    "tau_from_design",
    "sequential_test",
]


def mixture_log_lr(effect: ArrayLike, se: ArrayLike, tau: float, theta0: float = 0.0) -> np.ndarray:
    """Log of the normal-mixture likelihood ratio for an observed effect.

    Vectorised over ``effect`` and ``se``.
    """
    tau = positive_scalar(tau, "tau")
    theta0 = finite_scalar(theta0, "theta0")
    d = np.asarray(effect, dtype=float) - theta0
    if not np.all(np.isfinite(d)):
        raise ValueError("effects must be finite")
    s2 = _standard_errors(se) ** 2
    t2 = tau**2
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 0.5 * np.log(s2 / (s2 + t2)) + t2 * d**2 / (2.0 * s2 * (s2 + t2))
    return np.where(s2 > 0, out, np.where(d == 0, 0.0, np.inf))


def always_valid_halfwidth(se: ArrayLike, tau: float, alpha: float = 0.05) -> np.ndarray:
    """Half-width of the (1 - alpha) normal-mixture confidence sequence."""
    tau = positive_scalar(tau, "tau")
    alpha = _alpha(alpha)
    s2 = _standard_errors(se) ** 2
    t2 = tau**2
    with np.errstate(divide="ignore", invalid="ignore"):
        hw = np.sqrt(s2 * (s2 + t2) / t2 * np.log((s2 + t2) / (s2 * alpha**2)))
    return np.where(s2 > 0, hw, 0.0)


@lru_cache(maxsize=64)
def _optimal_ratio(alpha: float) -> float:
    """``r* = tau^2 / s^2`` minimising the confidence-sequence width at one sample size."""

    def width_sq(log_r: float) -> float:
        r = np.exp(log_r)
        return (1.0 + 1.0 / r) * np.log((1.0 + r) / alpha**2)

    res = optimize.minimize_scalar(width_sq, bounds=(-10.0, 15.0), method="bounded")
    return float(np.exp(res.x))


def tau_for_horizon(se_at_horizon: float, alpha: float = 0.05) -> float:
    """Mixing scale that makes the confidence sequence tightest at the planned horizon.

    ``se_at_horizon`` is the standard error of the difference in means you expect
    at the planned final sample size (e.g. from historical data).
    """
    se_at_horizon = positive_scalar(se_at_horizon, "se_at_horizon")
    alpha = _alpha(alpha)
    return float(np.sqrt(_optimal_ratio(alpha)) * se_at_horizon)


def tau_from_design(
    sd: float, n_per_arm: int, alpha: float = 0.05, sd_treatment: float | None = None, ratio: float = 1.0
) -> float:
    """Convenience wrapper: ``tau`` from the metric's standard deviation and planned size."""
    sd = positive_scalar(sd, "sd")
    n_per_arm = positive_integer(n_per_arm, "n_per_arm", minimum=2)
    ratio = positive_scalar(ratio, "ratio")
    sd_t = sd if sd_treatment is None else positive_scalar(sd_treatment, "sd_treatment")
    se = np.sqrt(sd**2 / n_per_arm + sd_t**2 / (ratio * n_per_arm))
    return tau_for_horizon(float(se), alpha)


@dataclass(frozen=True)
class Look:
    """State of the experiment at one interim analysis."""

    n_control: int
    n_treatment: int
    control_mean: float
    treatment_mean: float
    effect: float
    se: float
    log_lr: float
    p_value: float
    ci_low: float
    ci_high: float
    naive_p_value: float
    naive_ci_low: float
    naive_ci_high: float


@dataclass(frozen=True)
class SequentialResult:
    looks: tuple[Look, ...]
    alpha: float
    tau: float | None
    mode: str = "working_normal"

    @property
    def is_anytime_valid(self) -> bool:
        """Whether a time-uniform guarantee applies, conditional on mode assumptions."""
        return self.mode in {"bounded", "gaussian_known_sd"}

    @property
    def guarantee_note(self) -> str:
        if self.mode == "bounded":
            return "Hoeffding confidence sequence: valid for independent [0,1] outcomes at the specified looks."
        if self.mode == "gaussian_known_sd":
            return "Normal-mixture confidence sequence: valid for independent Gaussian observations with prespecified known SD and tau."
        return "WORKING-NORMAL APPROXIMATION ONLY: plug-in variance destroys the claimed exact anytime-valid guarantee."

    @property
    def stop_index(self) -> int | None:
        """Index of the first look at which the always-valid test rejects."""
        for i, look in enumerate(self.looks):
            if look.p_value < self.alpha:
                return i
        return None

    @property
    def naive_stop_index(self) -> int | None:
        """First look at which a peeking analyst would have declared significance."""
        for i, look in enumerate(self.looks):
            if look.naive_p_value < self.alpha:
                return i
        return None

    @property
    def final(self) -> Look:
        return self.looks[-1]

    def to_frame(self):
        import pandas as pd

        return pd.DataFrame([asdict(look) for look in self.looks])


def _look_counts(n: int, looks: int | Sequence[float]) -> np.ndarray:
    if isinstance(looks, (bool, np.bool_)):
        raise ValueError("looks must be a positive integer or increasing fractions")
    if isinstance(looks, (int, np.integer)):
        if looks < 1:
            raise ValueError("looks must be >= 1")
        fractions = np.arange(1, looks + 1) / looks
    else:
        fractions = np.asarray(looks, dtype=float)
        if (fractions.ndim != 1 or not fractions.size or not np.all(np.isfinite(fractions))
                or np.any((fractions <= 0) | (fractions > 1)) or np.any(np.diff(fractions) <= 0)):
            raise ValueError("looks must be increasing fractions in (0, 1]")
    return np.floor(fractions * n).astype(int)


def sequential_test(
    control: ArrayLike,
    treatment: ArrayLike,
    looks: int | Sequence[float] = 20,
    tau: float | None = None,
    alpha: float = 0.05,
    mode: str = "working_normal",
    known_sd: float | tuple[float, float] | None = None,
) -> SequentialResult:
    """Replay an experiment look by look using an explicitly selected method.

    Parameters
    ----------
    control, treatment:
        Per-unit outcomes **in arrival order**.
    looks:
        Number of evenly spaced interim looks, or increasing fractions of the data.
    tau:
        Mixing scale fixed in advance (see :func:`tau_for_horizon`). The legacy
        working_normal default derives it from the FULL dataset if omitted. This
        is ONLY for illustrative historical replays, not sequential guarantees.
    alpha:
        Nominal error rate; an exact time-uniform guarantee applies only in
        ``bounded`` and ``gaussian_known_sd`` modes under their assumptions.
    mode:
        ``working_normal`` (legacy approximation; default), ``bounded``
        (independent [0,1] measurements), or ``gaussian_known_sd``.
    known_sd:
        Known per-user SD or pair (control_sd, treatment_sd). Required in the
        Gaussian exact mode; it must be specified independent of these outcomes.

    The returned looks also carry the *naive* fixed-horizon p-value and interval at
    each look, so you can see what a peeking analyst would have concluded.
    """
    c = np.asarray(control, dtype=float).ravel()
    t = np.asarray(treatment, dtype=float).ravel()
    if c.size < 2 or t.size < 2:
        raise ValueError("each arm needs at least 2 observations")
    if not (np.all(np.isfinite(c)) and np.all(np.isfinite(t))):
        raise ValueError("outcomes contain NaN or infinite values")
    alpha = _alpha(alpha)
    if mode not in {"working_normal", "bounded", "gaussian_known_sd"}:
        raise ValueError("mode must be working_normal, bounded, or gaussian_known_sd")
    if tau is not None:
        tau = positive_scalar(tau, "tau")
    if known_sd is not None and mode == "working_normal":
        raise ValueError("known_sd is only used in gaussian_known_sd mode")
    if mode == "gaussian_known_sd" and c.size != t.size:
        raise ValueError("gaussian_known_sd currently requires paired equal arm sizes at all looks")
    if mode == "bounded":
        if np.any(c < 0) or np.any(c > 1) or np.any(t < 0) or np.any(t > 1):
            raise ValueError("bounded mode requires every observation in [0, 1]")
        if known_sd is not None or tau is not None:
            raise ValueError("bounded mode does not use known_sd or tau")
    elif mode == "gaussian_known_sd":
        if known_sd is None or tau is None:
            raise ValueError("gaussian_known_sd needs known_sd AND prespecified tau")
        if np.isscalar(known_sd):
            sd_c = sd_t = float(known_sd)
        else:
            if len(known_sd) != 2:
                raise ValueError("known_sd must be a scalar or two-element tuple")
            sd_c, sd_t = (float(x) for x in known_sd)
        if not (np.isfinite(sd_c) and np.isfinite(sd_t) and sd_c > 0 and sd_t > 0):
            raise ValueError("known SDs must be finite and positive")
    elif tau is None:
        # Legacy exploratory replay; the design scale is estimated from ALL data.
        # This is not a valid prospective sequential test.
        se_h = np.sqrt(c.var(ddof=1) / c.size + t.var(ddof=1) / t.size)
        tau = tau_for_horizon(float(se_h) if se_h > 0 else 1e-12, alpha)

    n_c_all = _look_counts(c.size, looks)
    n_t_all = _look_counts(t.size, looks)
    keep = (n_c_all >= 2) & (n_t_all >= 2)
    if not np.any(keep):
        raise ValueError("no look had at least 2 observations per arm; use fewer looks")
    n_c, n_t = n_c_all[keep], n_t_all[keep]
    if len(set(zip(n_c, n_t, strict=True))) != len(n_c):
        raise ValueError("some monitoring looks contain identical sample counts; use fewer looks")

    # sufficient statistics at every look from cumulative sums (one pass, vectorised).
    # Shifting both arms by the same constant leaves differences and variances unchanged
    # but avoids cancellation error in sum(x^2) - n * mean^2 for large-valued metrics.
    shift = float(np.median(np.concatenate([c[:50], t[:50]])))
    c, t = c - shift, t - shift
    cs_c, cs_t = np.cumsum(c)[n_c - 1], np.cumsum(t)[n_t - 1]
    sq_c, sq_t = np.cumsum(c**2)[n_c - 1], np.cumsum(t**2)[n_t - 1]
    m_c, m_t = cs_c / n_c, cs_t / n_t
    v_c = np.maximum((sq_c - n_c * m_c**2) / (n_c - 1), 0.0)
    v_t = np.maximum((sq_t - n_t * m_t**2) / (n_t - 1), 0.0)
    se = np.sqrt(v_c / n_c + v_t / n_t)
    d = m_t - m_c

    if mode == "bounded":
        # P(|effect - true_effect| >= h) <= 2 exp(-2 h² / (1/n_c + 1/n_t)).
        # Spend alpha * 6 / (pi² k²) at the kth prespecified look; total <= alpha.
        # The running intersection forms a genuine confidence sequence.
        k = np.arange(1, d.size + 1, dtype=float)
        spend_weight = 6.0 / (np.pi**2 * k**2)
        sigma2_weight = 1.0 / n_c + 1.0 / n_t
        hw = np.sqrt(sigma2_weight / 2 * np.log(2 / (alpha * spend_weight)))
        log_lr = -2 * d**2 / sigma2_weight + np.log(2 / spend_weight)
        p_at_look = np.exp(np.clip(log_lr, -745, 700))
        p_av = np.minimum.accumulate(np.minimum(p_at_look, 1.0))
    else:
        infer_se = se if mode == "working_normal" else np.sqrt(sd_c**2 / n_c + sd_t**2 / n_t)
        log_lr = mixture_log_lr(d, infer_se, tau)
        p_av = np.minimum.accumulate(np.minimum(np.exp(-np.clip(log_lr, -700, 700)), 1.0))
        hw = always_valid_halfwidth(infer_se, tau, alpha)
    display_se = se if mode != "gaussian_known_sd" else infer_se
    ci_lo = np.maximum.accumulate(d - hw)
    ci_hi = np.minimum.accumulate(d + hw)
    z = stats.norm.ppf(1 - alpha / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        naive_p = np.where(se > 0, 2 * stats.norm.sf(np.abs(d) / se), (d == 0).astype(float))

    out = [
        Look(
            n_control=int(n_c[i]),
            n_treatment=int(n_t[i]),
            control_mean=float(m_c[i] + shift),
            treatment_mean=float(m_t[i] + shift),
            effect=float(d[i]),
            se=float(display_se[i]),
            log_lr=float(log_lr[i]),
            p_value=float(p_av[i]),
            ci_low=float(ci_lo[i]),
            ci_high=float(ci_hi[i]),
            naive_p_value=float(naive_p[i]),
            naive_ci_low=float(d[i] - z * se[i]),
            naive_ci_high=float(d[i] + z * se[i]),
        )
        for i in range(d.size)
    ]
    return SequentialResult(tuple(out), alpha, float(tau) if tau is not None else None, mode)
