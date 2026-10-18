"""Data-quality checks that must pass before any effect estimate is trusted.

Sample ratio mismatch (SRM) - observing, say, 50.6% / 49.4% when the design
promised 50/50 - is the most common sign that an experiment is broken: a logging
bug, a redirect that loses users, bot filtering that treats arms differently.
When it fires, the arms are no longer comparable and the effect estimate is
biased in an unknown direction. Industry practice (Fabijan et al., KDD 2019) is
to test with a chi-square goodness-of-fit test at a strict threshold such as
p < 0.001 and to stop the analysis until the cause is found.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

__all__ = ["SRMResult", "srm_test", "srm_by_segment"]


@dataclass(frozen=True)
class SRMResult:
    observed: tuple[int, ...]
    expected_ratios: tuple[float, ...]
    statistic: float
    p_value: float
    threshold: float

    @property
    def flagged(self) -> bool:
        """``True`` when the allocation is implausible under the design."""
        return self.p_value < self.threshold

    @property
    def observed_ratios(self) -> tuple[float, ...]:
        total = sum(self.observed)
        return tuple(o / total for o in self.observed)

    def summary(self) -> str:
        obs = ", ".join(f"{r:.2%}" for r in self.observed_ratios)
        exp = ", ".join(f"{r:.2%}" for r in self.expected_ratios)
        verdict = "SRM DETECTED - do not trust effect estimates" if self.flagged else "no SRM"
        return f"{verdict}: observed [{obs}] vs expected [{exp}], chi2={self.statistic:.2f}, p={self.p_value:.2g}"


def srm_test(
    counts: Sequence[int],
    expected_ratios: Sequence[float] | None = None,
    threshold: float = 0.001,
) -> SRMResult:
    """Chi-square goodness-of-fit test for sample ratio mismatch.

    Parameters
    ----------
    counts: units observed in each arm, e.g. ``[50_412, 49_588]``.
    expected_ratios: designed allocation (normalised automatically); equal split if omitted.
    threshold: p-value below which SRM is declared. 0.001 keeps false alarms rare
        when SRM is checked on every experiment.
    """
    if not np.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("SRM threshold must be between zero and one")
    obs = np.asarray(counts, dtype=float)
    if obs.ndim != 1 or obs.size < 2:
        raise ValueError("counts needs one entry per arm (at least two arms)")
    if not np.all(np.isfinite(obs)) or np.any(obs < 0) or not np.allclose(obs, np.round(obs)):
        raise ValueError("counts must be non-negative integers")
    if obs.sum() == 0:
        raise ValueError("no units observed")
    ratios = np.full(obs.size, 1.0 / obs.size) if expected_ratios is None else np.asarray(expected_ratios, float)
    if ratios.shape != obs.shape or not np.all(np.isfinite(ratios)) or np.any(ratios <= 0):
        raise ValueError("expected_ratios must be positive with one entry per arm")
    ratios = ratios / ratios.sum()
    stat, p = stats.chisquare(obs, f_exp=ratios * obs.sum())
    return SRMResult(
        observed=tuple(int(o) for o in obs),
        expected_ratios=tuple(float(r) for r in ratios),
        statistic=float(stat),
        p_value=float(p),
        threshold=threshold,
    )


def srm_by_segment(
    df: pd.DataFrame,
    arm_col: str,
    segment_col: str,
    expected_split: Mapping[str, float] | None = None,
    threshold: float = 0.001,
) -> pd.DataFrame:
    """Run the SRM test inside each segment (platform, browser, country, ...).

    When the overall check fails, the segment that carries the mismatch usually
    points straight at the bug - e.g. one platform whose exposure logging breaks in
    one arm. Segments are sorted by p-value, most suspicious first.
    """
    arms = sorted(df[arm_col].astype(str).unique())
    ratios = None if expected_split is None else [float(expected_split[a]) for a in arms]
    rows = []
    for seg, sub in df.groupby(segment_col, sort=True):
        counts = sub[arm_col].astype(str).value_counts().reindex(arms, fill_value=0)
        res = srm_test(counts.to_numpy(), ratios, threshold)
        row = {segment_col: seg, "units": int(counts.sum())}
        row.update({f"share_{a}": r for a, r in zip(arms, res.observed_ratios, strict=True)})
        row.update({"chi2": res.statistic, "p_value": res.p_value, "flagged": res.flagged})
        rows.append(row)
    return pd.DataFrame(rows).sort_values("p_value").reset_index(drop=True)
