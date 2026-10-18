"""Experiment design: sample size, minimum detectable effect and power.

All formulas use the two-sided normal approximation that matches the Welch test in
:mod:`abtrust.estimators`. ``variance_reduction`` lets you plan for CUPED: pass the
expected ``corr(pre_metric, metric) ** 2`` and the required sample size shrinks by
the factor ``1 - variance_reduction``. Calibration of these formulas (do 80%-power
designs really reach 80% power?) is checked by simulation in
:mod:`abtrust.validation`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy import stats

from ._inputs import finite_scalar, positive_integer, positive_scalar

__all__ = [
    "SampleSize",
    "sample_size_mean",
    "sample_size_proportion",
    "mde_mean",
    "power_mean",
]


@dataclass(frozen=True)
class SampleSize:
    """Required units per arm for a two-arm test."""

    n_control: int
    n_treatment: int
    mde: float
    alpha: float
    power: float

    @property
    def total(self) -> int:
        return self.n_control + self.n_treatment

    def days(self, daily_units: float) -> float:
        """Days needed if ``daily_units`` new units enter the experiment per day."""
        daily_units = positive_scalar(daily_units, "daily_units")
        return self.total / daily_units

    def __str__(self) -> str:
        return (
            f"{self.n_control:,} control + {self.n_treatment:,} treatment = {self.total:,} units "
            f"(MDE={self.mde:g}, alpha={self.alpha:g}, power={self.power:.0%})"
        )


def _validate(alpha: float, power: float, ratio: float, variance_reduction: float) -> None:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    if not 0 < power < 1:
        raise ValueError("power must be in (0, 1)")
    positive_scalar(ratio, "ratio (n_treatment / n_control)")
    if not 0 <= variance_reduction < 1:
        raise ValueError("variance_reduction must be in [0, 1)")


def _z_sum(alpha: float, power: float) -> float:
    return stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)


def sample_size_mean(
    mde: float,
    sd: float,
    alpha: float = 0.05,
    power: float = 0.80,
    ratio: float = 1.0,
    variance_reduction: float = 0.0,
    sd_treatment: float | None = None,
) -> SampleSize:
    """Units per arm to detect an absolute difference ``mde`` in a mean metric.

    Parameters
    ----------
    mde: smallest absolute effect worth detecting (same units as the metric).
    sd: standard deviation of the metric per unit in control.
    ratio: ``n_treatment / n_control`` (1.0 = equal split).
    variance_reduction: expected CUPED variance reduction, ``rho ** 2``.
    sd_treatment: treatment-arm standard deviation if it differs from ``sd``.
    """
    _validate(alpha, power, ratio, variance_reduction)
    mde = finite_scalar(mde, "mde")
    if mde == 0:
        raise ValueError("mde must be non-zero")
    sd = positive_scalar(sd, "sd")
    sd_t = sd if sd_treatment is None else positive_scalar(sd_treatment, "sd_treatment")
    scale = 1.0 - variance_reduction
    n_c = _z_sum(alpha, power) ** 2 * scale * (sd**2 + sd_t**2 / ratio) / mde**2
    n_c = max(2, math.ceil(2 / ratio), math.ceil(n_c))
    return SampleSize(n_c, math.ceil(n_c * ratio), abs(mde), alpha, power)


def sample_size_proportion(
    baseline: float,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.80,
    ratio: float = 1.0,
    relative: bool = False,
) -> SampleSize:
    """Units per arm to detect a change in a conversion rate.

    ``mde`` is absolute (0.005 = +0.5 percentage points) unless ``relative=True``
    (0.05 = +5% of the baseline rate).
    """
    if not 0 < baseline < 1:
        raise ValueError("baseline must be a rate in (0, 1)")
    mde = finite_scalar(mde, "mde")
    if mde == 0:
        raise ValueError("mde must be non-zero")
    delta = baseline * mde if relative else mde
    p_t = baseline + delta
    if not 0 < p_t < 1:
        raise ValueError("baseline + mde must stay inside (0, 1)")
    _validate(alpha, power, ratio, 0.0)
    var_c = baseline * (1 - baseline)
    var_t = p_t * (1 - p_t)
    n_c = math.ceil(_z_sum(alpha, power) ** 2 * (var_c + var_t / ratio) / delta**2)
    n_c = max(2, math.ceil(2 / ratio), n_c)
    return SampleSize(n_c, math.ceil(n_c * ratio), abs(delta), alpha, power)


def _se(n_control: int, sd: float, ratio: float, variance_reduction: float) -> float:
    n_control = positive_integer(n_control, "n_control", minimum=2)
    sd = positive_scalar(sd, "sd")
    return math.sqrt((1 - variance_reduction) * sd**2 * (1 / n_control + 1 / (ratio * n_control)))


def mde_mean(
    n_control: int,
    sd: float,
    alpha: float = 0.05,
    power: float = 0.80,
    ratio: float = 1.0,
    variance_reduction: float = 0.0,
) -> float:
    """Smallest absolute effect detectable with the given sample size and power."""
    _validate(alpha, power, ratio, variance_reduction)
    return _z_sum(alpha, power) * _se(n_control, sd, ratio, variance_reduction)


def power_mean(
    n_control: int,
    mde: float,
    sd: float,
    alpha: float = 0.05,
    ratio: float = 1.0,
    variance_reduction: float = 0.0,
) -> float:
    """Probability that a two-sided test rejects when the true effect is ``mde``."""
    _validate(alpha, 0.5, ratio, variance_reduction)
    mde = finite_scalar(mde, "mde")
    se = _se(n_control, sd, ratio, variance_reduction)
    z = stats.norm.ppf(1 - alpha / 2)
    shift = abs(mde) / se
    return float(stats.norm.cdf(shift - z) + stats.norm.cdf(-shift - z))
