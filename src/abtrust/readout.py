"""One-call experiment readout: SRM check, per-metric estimates, correction, verdicts.

>>> from abtrust import Metric, analyze
>>> readout = analyze(
...     df, arm_col="variant", control="control",
...     metrics=[
...         Metric("conversion", column="converted", role="primary"),
...         Metric("revenue", column="revenue", covariate="pre_revenue"),
...         Metric("clicks per session", numerator="clicks", denominator="sessions"),
...     ],
... )
>>> print(readout.to_markdown())
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from .checks import SRMResult, srm_test
from .estimators import Estimate, cuped, lin_adjustment, ratio_delta, welch_ttest
from .multiple import adjust

__all__ = ["Metric", "Readout", "analyze"]

_ROLES = ("primary", "secondary", "guardrail")


@dataclass(frozen=True)
class Metric:
    """How to compute one metric from a per-unit table.

    Give either ``column`` (a per-unit value: 0/1 conversion, revenue, ...) or
    ``numerator`` and ``denominator`` (per-unit totals of a ratio metric such as
    clicks / sessions). ``covariate`` names a pre-experiment column used for CUPED;
    pass a tuple of several columns to use Lin's regression adjustment instead.
    """

    name: str
    column: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    covariate: str | tuple[str, ...] | None = None
    role: str = "secondary"
    higher_is_better: bool = True
    max_harm: float | None = None  # absolute, predeclared tolerance for guardrails

    def __post_init__(self) -> None:
        is_mean = self.column is not None
        is_ratio = self.numerator is not None or self.denominator is not None
        if is_mean == is_ratio:
            raise ValueError(f"metric {self.name!r}: give either column, or numerator and denominator")
        if is_ratio and (self.numerator is None or self.denominator is None):
            raise ValueError(f"metric {self.name!r}: a ratio metric needs both numerator and denominator")
        if is_ratio and self.covariate is not None:
            raise ValueError(f"metric {self.name!r}: CUPED for ratio metrics is not supported")
        if self.max_harm is not None and (self.role != "guardrail" or not np.isfinite(self.max_harm) or self.max_harm < 0):
            raise ValueError(f"metric {self.name!r}: max_harm must be a nonnegative finite value on a guardrail")
        if self.role not in _ROLES:
            raise ValueError(f"metric {self.name!r}: role must be one of {_ROLES}")
        if isinstance(self.covariate, (list, tuple)):
            if not self.covariate:
                raise ValueError(f"metric {self.name!r}: covariate list is empty")
            object.__setattr__(self, "covariate", tuple(self.covariate))

    @property
    def covariates(self) -> tuple[str, ...]:
        if self.covariate is None:
            return ()
        return (self.covariate,) if isinstance(self.covariate, str) else tuple(self.covariate)

    @property
    def kind(self) -> str:
        return "mean" if self.column is not None else "ratio"

    @property
    def columns(self) -> list[str]:
        cols = [self.column] if self.column else [self.numerator, self.denominator]
        cols.extend(self.covariates)
        return [c for c in dict.fromkeys(cols) if c is not None]


@dataclass
class Readout:
    """Everything needed to make (or refuse to make) a ship decision."""

    arm_col: str
    control: str
    arm_counts: dict[str, int]
    srm: SRMResult
    table: pd.DataFrame
    alpha: float
    correction: str
    notes: list[str] = field(default_factory=list)
    data_quality_blockers: list[str] = field(default_factory=list)
    unit_verified: bool = False

    # ------------------------------------------------------------------ decision
    def decision(self) -> str:
        """Decision support, not an automated release authorization.

        A nonsignificant harmful change is NOT evidence of safety. Guardrails
        require preregistered acceptable harm margins, checked with conservative
        Bonferroni confidence bounds across every guardrail comparison.
        """
        if self.srm.flagged:
            return "DO NOT DECIDE - sample ratio mismatch; investigate missing exposure records."
        if self.data_quality_blockers:
            return "DO NOT DECIDE - data quality: " + "; ".join(self.data_quality_blockers)
        t = self.table
        bad_guard = t[(t.role == "guardrail") & (t.verdict == "significant regression")]
        if len(bad_guard):
            return "DO NOT SHIP - guardrail regression on: " + ", ".join(sorted(set(bad_guard.metric)))
        primary = t[t.role == "primary"]
        if primary.empty:
            return "REVIEW REQUIRED - no primary metric declared."
        if (primary.verdict == "significant regression").any():
            return "DO NOT SHIP - primary metric got significantly worse."
        if not (primary.verdict == "significant improvement").all():
            return "MIXED - some primary metrics improved, others are inconclusive." if (primary.verdict == "significant improvement").any() else "INCONCLUSIVE - primary improvement not demonstrated."
        guard = t[t.role == "guardrail"]
        if guard.empty:
            return "REVIEW REQUIRED - primary improved, but no guardrails configured; safety not assessed."
        if guard.max_harm.isna().any():
            return "REVIEW REQUIRED - primary improved; guardrail harm margins missing, so safety is not established."
        if (~guard.safety_pass).any():
            return "REVIEW REQUIRED - primary improved, but guardrail safety is not established within declared harm margins."
        if not self.unit_verified:
            return "REVIEW REQUIRED - unit IDs not supplied; unique randomization units were not verified."
        return "SHIP CANDIDATE (review required) - primary improved and configured guardrails passed conservative harm bounds; confirm external validity and business context."

    # ------------------------------------------------------------------ rendering
    def to_frame(self) -> pd.DataFrame:
        return self.table.copy()

    def to_markdown(self, title: str = "Experiment readout") -> str:
        lines = [f"# {title}", ""]
        arms = ", ".join(f"`{a}` n={n:,}" for a, n in self.arm_counts.items())
        lines += [f"**Arms:** {arms} (control = `{self.control}`)", ""]
        lines += [f"**Decision:** {self.decision()}", ""]
        lines += ["## 1. Sample ratio mismatch", ""]
        status = "FAIL" if self.srm.flagged else "PASS"
        lines += [f"**{status}** - {self.srm.summary()}", ""]
        n_tests = len(self.table)
        corr = {"holm": "Holm", "bh": "Benjamini-Hochberg", "none": "no"}.get(self.correction, self.correction)
        lines += [
            "## 2. Results",
            "",
            f"Two-sided tests at alpha = {self.alpha:g}, {corr} correction across {n_tests} comparison(s). "
            f"Intervals are unadjusted {1 - self.alpha:.0%} confidence intervals (Holm/BH adjusts p-values, not these intervals). "
            "Guardrail safety bounds, if configured, use Bonferroni across guardrail comparisons.",
            "",
            "| Arm | Metric | Role | Method | Control | Treatment | Absolute effect (CI) | Relative effect (CI) | p | p adj. | Verdict |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for r in self.table.itertuples(index=False):
            rel = (
                f"{_pct(r.rel_effect)} ({_pct(r.rel_ci_low)}, {_pct(r.rel_ci_high)})"
                if r.rel_effect is not None and not pd.isna(r.rel_effect)
                else "n/a"
            )
            lines.append(
                f"| {r.arm} | {r.metric} | {r.role} | {r.method} | {_num(r.control_mean)} | {_num(r.treatment_mean)} | "
                f"{_num(r.effect, signed=True)} ({_num(r.ci_low, signed=True)}, {_num(r.ci_high, signed=True)}) | {rel} | "
                f"{_p(r.p_value)} | {_p(r.p_adjusted)} | {r.verdict} |"
            )
        if self.data_quality_blockers:
            lines += ["", "## Data quality blockers", ""]
            lines += [f"- {item}" for item in self.data_quality_blockers]
        if (self.table.role == "guardrail").any():
            lines += ["", "## Guardrail safety screening", "",
                      "Absolute harm is positive when a lower-is-better guardrail rises or a higher-is-better guardrail falls. "
                      "Missing prespecified harm margins mean **not assessed**; non-significance is not proof of safety.", "",
                      "| Arm | Guardrail | Prespecified max harm | Conservative upper harm bound | Screen |",
                      "|---|---|---:|---:|---|"]
            for row in self.table[self.table.role == "guardrail"].itertuples(index=False):
                screen = "pass" if row.safety_pass else "unproven"
                lines.append(f"| {row.arm} | {row.metric} | {_num(row.max_harm)} | {_num(row.harm_upper_bound)} | {screen} |")
        if self.notes:
            lines += ["", "## 3. Notes", ""]
            lines += [f"- {n}" for n in self.notes]
        lines.append("")
        return "\n".join(lines)


def _num(x: float, signed: bool = False) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    s = f"{x:+.4g}" if signed else f"{x:.4g}"
    return s


def _pct(x: float | None) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    return f"{x:+.2%}"


def _p(x: float) -> str:
    if x < 1e-4:
        return "<0.0001"
    return f"{x:.4f}"


def _verdict(p_adj: float, effect: float, alpha: float, higher_is_better: bool, srm_flagged: bool) -> str:
    if srm_flagged:
        return "invalid (SRM)"
    if p_adj >= alpha:
        return "not significant"
    good = (effect > 0) == higher_is_better
    return "significant improvement" if good else "significant regression"


def analyze(
    df: pd.DataFrame,
    arm_col: str,
    control: str,
    metrics: Sequence[Metric],
    expected_split: Mapping[str, float] | None = None,
    alpha: float = 0.05,
    correction: str = "holm",
    srm_threshold: float = 0.001,
    unit_col: str | None = None,
    missing_threshold: float = 0.01,
) -> Readout:
    """Analyze a per-unit experiment table (one row per randomization unit).

    Every treatment arm is compared with ``control`` on every metric. Mean metrics
    with one ``covariate`` use CUPED, with several use Lin's regression adjustment;
    other mean metrics use Welch's t-test; ratio metrics use the delta method. The correction (``"holm"``, ``"bh"`` or ``"none"``)
    is applied across all arm x metric comparisons.
    """
    if not 0 <= missing_threshold <= 1:
        raise ValueError("missing_threshold must be between 0 and 1")
    if unit_col is not None and unit_col not in df.columns:
        raise KeyError(f"unit column {unit_col!r} not found")
    if arm_col not in df.columns:
        raise KeyError(f"arm column {arm_col!r} not found")
    if not metrics:
        raise ValueError("pass at least one Metric")
    names = [m.name for m in metrics]
    if len(names) != len(set(names)):
        raise ValueError("metric names must be unique")
    missing = sorted({c for m in metrics for c in m.columns if c not in df.columns})
    if missing:
        raise KeyError(f"columns not found in data: {missing}")
    # Do not permit infinities or string-formatted outcomes to silently pass
    # into statistical estimators (which can otherwise produce misleading NaNs).
    for column in sorted({col for m in metrics for col in m.columns}):
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise ValueError(f"outcome or covariate {column!r} must be numeric")
        if np.isinf(df[column].to_numpy(dtype=float)).any():
            raise ValueError(f"outcome or covariate {column!r} contains infinity; clean the data first")
    if df[arm_col].isna().any():
        raise ValueError("arm column contains missing values; do not silently treat them as a new arm")
    if unit_col is not None:
        if df[unit_col].isna().any() or df[unit_col].duplicated().any():
            raise ValueError(f"unit column {unit_col!r} must be nonmissing and unique (one row per randomized unit)")
    arms = df[arm_col].astype(str)
    control = str(control)
    if control not in set(arms):
        raise ValueError(f"control arm {control!r} not present in column {arm_col!r}")
    treatments = sorted(a for a in arms.unique() if a != control)
    if not treatments:
        raise ValueError("data contains only the control arm")
    order = [control, *treatments]
    counts = {a: int((arms == a).sum()) for a in order}

    if expected_split is None:
        ratios = None
    else:
        unknown = set(expected_split) - set(order)
        if unknown or set(order) - set(expected_split):
            raise ValueError("expected_split must give a ratio for every arm present in the data")
        ratios = [float(expected_split[a]) for a in order]
    srm = srm_test([counts[a] for a in order], ratios, threshold=srm_threshold)

    rows: list[dict] = []
    notes: list[str] = []
    blockers: list[str] = []
    if unit_col is None:
        notes.append("No unit_col was provided: unique randomization units could not be verified.")
    n_guard = len(treatments) * sum(m.role == "guardrail" for m in metrics)
    for arm in treatments:
        for m in metrics:
            sub = df.loc[arms.isin([control, arm]), [*m.columns]].assign(_arm=arms[arms.isin([control, arm])])
            n_before = len(sub)
            before_counts = sub["_arm"].value_counts()
            sub = sub.dropna()
            after_counts = sub["_arm"].value_counts()
            if len(sub) < n_before:
                notes.append(f"{m.name} ({arm}): dropped {n_before - len(sub):,} row(s) with missing values.")
                rates = {}
                for group in (control, arm):
                    before = int(before_counts.get(group, 0))
                    after = int(after_counts.get(group, 0))
                    rates[group] = (before - after) / before if before else 1.0
                notes.append(f"{m.name} ({arm}): missingness control={rates[control]:.2%}, treatment={rates[arm]:.2%}; available units control={int(after_counts.get(control, 0)):,}, treatment={int(after_counts.get(arm, 0)):,}.")
                if max(rates.values()) > missing_threshold or abs(rates[control] - rates[arm]) > missing_threshold:
                    blockers.append(f"{m.name} ({arm}) missingness exceeds threshold {missing_threshold:.1%} (control={rates[control]:.1%}, treatment={rates[arm]:.1%})")
            if int(after_counts.get(control, 0)) < 2 or int(after_counts.get(arm, 0)) < 2:
                raise ValueError(f"{m.name} ({arm}): fewer than 2 complete observations in an arm")
            is_c = (sub["_arm"] == control).to_numpy()
            est: Estimate
            unadjusted: Estimate | None = None
            if m.kind == "ratio":
                est = ratio_delta(
                    sub.loc[is_c, m.numerator],
                    sub.loc[is_c, m.denominator],
                    sub.loc[~is_c, m.numerator],
                    sub.loc[~is_c, m.denominator],
                    alpha=alpha,
                )
            elif m.covariates:
                y_c, y_t = sub.loc[is_c, m.column], sub.loc[~is_c, m.column]
                if len(m.covariates) == 1:
                    cov = m.covariates[0]
                    est = cuped(y_c, y_t, sub.loc[is_c, cov], sub.loc[~is_c, cov], alpha=alpha)
                    how = f"CUPED with `{cov}` (corr {est.extras['covariate_corr']:.2f})"
                else:
                    est = lin_adjustment(
                        sub[m.column], (~is_c).astype(float), sub[list(m.covariates)].to_numpy(), alpha=alpha
                    )
                    how = "Regression adjustment (Lin, HC2) with " + ", ".join(f"`{c}`" for c in m.covariates)
                unadjusted = welch_ttest(y_c, y_t, alpha=alpha)
                shrink = 1 - est.ci_width / unadjusted.ci_width if unadjusted.ci_width > 0 else 0.0
                reduction = 1 - (est.se / unadjusted.se) ** 2 if unadjusted.se > 0 else 0.0
                gain = (
                    f"cut the variance of the estimate by {reduction:.1%} (CI {shrink:.1%} narrower than unadjusted)"
                    if reduction >= 0.005
                    else "made no material difference to precision - the covariates barely predict this metric"
                )
                notes.append(
                    f"{m.name} ({arm}): {how} {gain}; unadjusted estimate {_num(unadjusted.effect, True)}, "
                    f"p={_p(unadjusted.p_value)}."
                )
            else:
                est = welch_ttest(sub.loc[is_c, m.column], sub.loc[~is_c, m.column], alpha=alpha)
            rows.append(
                {
                    "arm": arm,
                    "metric": m.name,
                    "role": m.role,
                    "max_harm": m.max_harm if m.role == "guardrail" else np.nan,
                    "higher_is_better": m.higher_is_better,
                    "method": est.method,
                    "n_control": est.n_control,
                    "n_treatment": est.n_treatment,
                    "control_mean": est.control_mean,
                    "treatment_mean": est.treatment_mean,
                    "effect": est.effect,
                    "se": est.se,
                    "degrees_freedom": est.extras.get("df", np.nan),
                    "ci_low": est.ci_low,
                    "ci_high": est.ci_high,
                    "rel_effect": est.rel_effect,
                    "rel_ci_low": est.rel_ci_low,
                    "rel_ci_high": est.rel_ci_high,
                    "p_value": est.p_value,
                    "unadjusted_effect": unadjusted.effect if unadjusted else np.nan,
                    "unadjusted_se": unadjusted.se if unadjusted else np.nan,
                    "variance_reduction": 1 - (est.se / unadjusted.se) ** 2
                    if unadjusted and unadjusted.se > 0
                    else np.nan,
                }
            )
    table = pd.DataFrame(rows)
    table["p_adjusted"] = adjust(table["p_value"].to_numpy(), correction)
    table["verdict"] = [
        _verdict(r.p_adjusted, r.effect, alpha, r.higher_is_better, srm.flagged) for r in table.itertuples(index=False)
    ]
    # The harm direction is positive for lower-is-better metrics, negative otherwise.
    # Use per-comparison Bonferroni critical values to conservatively bound all
    # configured guardrails at the same time (t critical for Welch, normal otherwise).
    table["harm_upper_bound"] = np.nan
    table["safety_pass"] = False
    if n_guard:
        for index, r in table[table.role == "guardrail"].iterrows():
            df_ = r.degrees_freedom
            crit = (stats.t.ppf(1 - alpha / (2 * n_guard), df_)
                    if np.isfinite(df_) else stats.norm.ppf(1 - alpha / (2 * n_guard)))
            harmful_effect = r.effect if not r.higher_is_better else -r.effect
            bound = float(harmful_effect + crit * r.se)
            table.at[index, "harm_upper_bound"] = bound
            table.at[index, "safety_pass"] = bool(np.isfinite(r.max_harm) and bound <= r.max_harm)
        notes.append("Guardrail safety uses two-sided Bonferroni-adjusted conservative bounds; harm margins must be chosen before observing outcomes. Passing is not a deployment authorization.")
    notes.append("Absolute-effect and relative-effect intervals use different approximations; they can straddle zero differently near the significance threshold. P-values test the absolute effect.")
    if any(m.kind == "ratio" for m in metrics):
        notes.append("Ratio metrics are analysed per randomization unit with the delta method, not per event.")
    return Readout(arm_col, control, counts, srm, table, alpha, correction.lower(), notes, blockers, unit_col is not None)
