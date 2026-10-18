"""Monte Carlo validation suite: does each method do what it promises?

A statistical method is a claim ("this interval covers the truth 95% of the time",
"this test is wrong at most 5% of the time"). The functions here check those
claims by simulating thousands of experiments with *known* ground truth and
running the actual :mod:`abtrust` code on each one. Every study returns a tidy
``pandas.DataFrame`` including Monte Carlo standard errors, so the claims can be
judged statistically rather than by eyeballing.

Run everything with ``abtrust validate``.
"""

from __future__ import annotations

import hashlib
import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from .checks import srm_test
from .design import sample_size_mean, sample_size_proportion
from .estimators import cuped, lin_adjustment, ratio_delta, welch_ttest
from .multiple import adjust
from .provenance import runtime_provenance, utc_now
from .sequential import sequential_test, tau_from_design
from .simulate import pre_post_normal, sessions_clicks, zero_inflated_lognormal

__all__ = [
    "StudyResult",
    "study_type1_coverage",
    "study_peeking",
    "study_cuped",
    "study_ratio_metrics",
    "study_srm",
    "study_power_calibration",
    "study_multiple_testing",
    "run_all",
]

ALPHA = 0.05


@dataclass
class StudyResult:
    name: str
    question: str
    table: pd.DataFrame
    headline: str
    seconds: float
    metadata: dict = field(default_factory=dict)


def _mcse(rate: float, n: int) -> float:
    return float(np.sqrt(max(rate * (1 - rate), 1e-12) / n))


def _table(rows: list[dict], **design) -> pd.DataFrame:
    table = pd.DataFrame(rows)
    table.attrs["design"] = design
    return table


# ----------------------------------------------------------------- 1. type-I error


def study_type1_coverage(n_sims: int = 4000, seed: int = 1) -> pd.DataFrame:
    """Welch t-test: false-positive rate under A/A and CI coverage under a real effect.

    Uses a conversion metric and a heavy-tailed, zero-inflated revenue metric at
    several sample sizes. Heavy tails are where the normal approximation behind the
    t-test is most likely to break at small n.
    """
    rng = np.random.default_rng(seed)
    p_conv, rev = 0.05, dict(p_purchase=0.08, mu=3.5, sigma=1.2)
    rev_mean = rev["p_purchase"] * np.exp(rev["mu"] + rev["sigma"] ** 2 / 2)
    lift = 0.05
    rows = []
    for metric in ("conversion", "revenue"):
        for n in (500, 2_000, 10_000):
            fp = cover = 0
            for _ in range(n_sims):
                if metric == "conversion":
                    c = (rng.random(n) < p_conv).astype(float)
                    a = (rng.random(n) < p_conv).astype(float)
                    t = (rng.random(n) < p_conv * (1 + lift)).astype(float)
                    true_effect = p_conv * lift
                else:
                    c = zero_inflated_lognormal(rng, n, **rev)
                    a = zero_inflated_lognormal(rng, n, **rev)
                    t = zero_inflated_lognormal(rng, n, multiplier=1 + lift, **rev)
                    true_effect = rev_mean * lift
                fp += welch_ttest(c, a, ALPHA).p_value < ALPHA
                est = welch_ttest(c, t, ALPHA)
                cover += est.ci_low <= true_effect <= est.ci_high
            fpr, cov = fp / n_sims, cover / n_sims
            rows.append(
                dict(
                    metric=metric,
                    n_per_arm=n,
                    false_positive_rate=fpr,
                    fpr_mcse=_mcse(fpr, n_sims),
                    ci_coverage=cov,
                    coverage_mcse=_mcse(cov, n_sims),
                    n_sims=n_sims,
                )
            )
    return _table(rows, conversion_rate=p_conv, revenue=rev, relative_effect=lift,
                  n_per_arm=[500, 2000, 10000], alpha=ALPHA)


# ------------------------------------------------------------------- 2. peeking


def study_peeking(n_sims: int = 3000, seed: int = 2, n_max: int = 10_000, base_rate: float = 0.10) -> pd.DataFrame:
    """Peeking with fixed-horizon tests vs the working-normal mSPRT approximation.

    Each simulated experiment has up to ``n_max`` users per arm and is analysed at
    K evenly spaced looks (K = 1 ... 100). The peeking analyst stops at the first
    look with p < 0.05; the plug-in mSPRT analyst uses exploratory sequential p-values. Scenarios:
    no effect (A/A), an effect equal to the 80%-power MDE, and twice the MDE.
    """
    rng = np.random.default_rng(seed)
    sd = np.sqrt(base_rate * (1 - base_rate))
    tau = tau_from_design(sd, n_max, ALPHA)
    se_h = sd * np.sqrt(2 / n_max)
    mde = (stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(0.8)) * se_h
    look_grid = (1, 2, 5, 10, 20, 50, 100)
    rows = []
    for scenario, effect in (("A/A (no effect)", 0.0), ("effect = MDE", mde), ("effect = 2 x MDE", 2 * mde)):
        naive_reject = {k: 0 for k in look_grid}
        av_reject = {k: 0 for k in look_grid}
        bounded_reject = {k: 0 for k in look_grid}
        stop_frac = []
        bounded_stop_frac = []
        naive_cover_all = av_cover_all = bounded_cover_all = 0
        for _ in range(n_sims):
            c = (rng.random(n_max) < base_rate).astype(float)
            t = (rng.random(n_max) < base_rate + effect).astype(float)
            res = sequential_test(c, t, looks=100, tau=tau, alpha=ALPHA)
            looks = res.looks
            naive_p = np.array([lk.naive_p_value for lk in looks])
            av_p = np.minimum(np.exp(-np.clip([lk.log_lr for lk in looks], -700, 700)), 1.0)
            for k in look_grid:
                idx = np.arange(100 // k - 1, 100, 100 // k)
                naive_reject[k] += bool(np.any(naive_p[idx] < ALPHA))
                av_reject[k] += bool(np.any(av_p[idx] < ALPHA))
                # Each monitoring design starts spending at look 1. Subsampling
                # the 100-look spending schedule understates the smaller design's
                # budget and does not evaluate sequential_test(..., looks=k).
                bounded = sequential_test(c, t, looks=k, mode="bounded", alpha=ALPHA)
                bounded_reject[k] += bounded.stop_index is not None
            stop = res.stop_index
            stop_frac.append(1.0 if stop is None else looks[stop].n_control / n_max)
            # The final loop iteration is the actual 100-look bounded procedure.
            bstop = bounded.stop_index
            bounded_stop_frac.append(1.0 if bstop is None else bounded.looks[bstop].n_control / n_max)
            naive_cover_all += all(lk.naive_ci_low <= effect <= lk.naive_ci_high for lk in looks)
            av_cover_all += looks[-1].ci_low <= effect <= looks[-1].ci_high  # running intersection
            bounded_cover_all += bounded.final.ci_low <= effect <= bounded.final.ci_high
        for k in look_grid:
            for method, counts in (("naive t-test (peeking)", naive_reject), ("mSPRT (working-normal approximate)", av_reject), ("Hoeffding CS (bounded, valid)", bounded_reject)):
                rate = counts[k] / n_sims
                rows.append(
                    dict(
                        scenario=scenario,
                        effect=effect,
                        method=method,
                        looks=k,
                        rejection_rate=rate,
                        mcse=_mcse(rate, n_sims),
                        n_sims=n_sims,
                    )
                )
        rows.append(
            dict(
                scenario=scenario,
                effect=effect,
                method="mSPRT (working-normal approximate)",
                looks=100,
                rejection_rate=np.nan,
                mcse=np.nan,
                n_sims=n_sims,
                mean_sample_fraction=float(np.mean(stop_frac)),
                simultaneous_coverage=av_cover_all / n_sims,
                naive_simultaneous_coverage=naive_cover_all / n_sims,
            )
        )
        rows.append(dict(scenario=scenario, effect=effect,
                         method="Hoeffding CS (bounded, valid)", looks=100,
                         rejection_rate=np.nan, mcse=np.nan, n_sims=n_sims,
                         mean_sample_fraction=float(np.mean(bounded_stop_frac)),
                         simultaneous_coverage=bounded_cover_all / n_sims,
                         naive_simultaneous_coverage=naive_cover_all / n_sims))
    return _table(rows, n_per_arm=n_max, baseline=base_rate, mde=mde, looks=list(look_grid),
                  tau=tau, alpha=ALPHA, effect_multipliers=[0, 1, 2],
                  modes=["working_normal", "bounded"])


# ---------------------------------------------------------------------- 3. CUPED


def study_cuped(n_sims: int = 3000, seed: int = 3, n: int = 1_000) -> pd.DataFrame:
    """CUPED and Lin adjustment: variance reduction vs theory, type-I error, power.

    Theory: with ``corr(x, y) = rho`` the standard error shrinks by a factor of
    ``sqrt(1 - rho^2)``. ``se_ratio`` is the empirical spread of each estimator relative
    to the unadjusted one; ``reported_se_over_empirical_sd`` near 1 means the standard
    errors the method reports are honest. The effect size is set so the unadjusted
    test has ~50% power.
    """
    rng = np.random.default_rng(seed)
    effect = 2.0 * np.sqrt(2 / n)  # unadjusted z ~ 2 -> ~52% power with sd = 1
    rows = []
    for rho in (0.0, 0.3, 0.5, 0.7, 0.9):
        est = {"welch": [], "cuped": [], "lin_hc2": []}
        ses = {"welch": [], "cuped": [], "lin_hc2": []}
        rej = {"welch": 0, "cuped": 0, "lin_hc2": 0}
        fp = {"welch": 0, "cuped": 0, "lin_hc2": 0}
        for _ in range(n_sims):
            for null in (True, False):
                xc, yc = pre_post_normal(rng, n, rho)
                xt, yt = pre_post_normal(rng, n, rho, effect=0.0 if null else effect)
                treat = np.r_[np.zeros(n), np.ones(n)]
                res = {
                    "welch": welch_ttest(yc, yt, ALPHA),
                    "cuped": cuped(yc, yt, xc, xt, ALPHA),
                    "lin_hc2": lin_adjustment(np.r_[yc, yt], treat, np.r_[xc, xt], ALPHA),
                }
                for m, r in res.items():
                    if null:
                        fp[m] += r.p_value < ALPHA
                    else:
                        est[m].append(r.effect)
                        ses[m].append(r.se)
                        rej[m] += r.p_value < ALPHA
        sd_welch = np.std(est["welch"], ddof=1)
        for m in ("welch", "cuped", "lin_hc2"):
            fpr, pw = fp[m] / n_sims, rej[m] / n_sims
            rows.append(
                dict(
                    rho=rho,
                    method=m,
                    se_ratio=np.std(est[m], ddof=1) / sd_welch,
                    theory_se_ratio=1.0 if m == "welch" else np.sqrt(1 - rho**2),
                    reported_se_over_empirical_sd=np.mean(ses[m]) / np.std(est[m], ddof=1),
                    false_positive_rate=fpr,
                    fpr_mcse=_mcse(fpr, n_sims),
                    power=pw,
                    power_mcse=_mcse(pw, n_sims),
                    n_sims=n_sims,
                )
            )
    return _table(rows, n_per_arm=n, effect=effect, mean=10.0, sd=1.0,
                  rho=[0.0, 0.3, 0.5, 0.7, 0.9], alpha=ALPHA)


# --------------------------------------------------------------- 4. ratio metrics


def _naive_session_test(cc: np.ndarray, sc: np.ndarray, ct: np.ndarray, st: np.ndarray) -> tuple[float, float, float]:
    """The common mistake: treat every session as an independent Bernoulli trial."""
    rc, rt = cc.sum() / sc.sum(), ct.sum() / st.sum()
    se = np.sqrt(rc * (1 - rc) / sc.sum() + rt * (1 - rt) / st.sum())
    d = rt - rc
    return d, se, 2 * stats.norm.sf(abs(d) / se)


def study_ratio_metrics(n_sims: int = 3000, seed: int = 4, n_users: int = 2_000) -> pd.DataFrame:
    """Clicks per session: per-session (naive) vs per-user delta-method inference.

    ``icc`` is the intra-user correlation of click behaviour. Real products sit
    well above zero: some users click a lot, others never do.
    """
    rng = np.random.default_rng(seed)
    ctr, lift = 0.10, 0.05
    z = stats.norm.ppf(1 - ALPHA / 2)
    rows = []
    for icc in (0.0, 0.02, 0.05, 0.10, 0.20):
        fp = {"naive per-session": 0, "delta method": 0}
        cover = {"naive per-session": 0, "delta method": 0}
        se_ratio = []
        for _ in range(n_sims):
            cc, sc = sessions_clicks(rng, n_users, ctr, icc)
            ca, sa = sessions_clicks(rng, n_users, ctr, icc)
            ct, st = sessions_clicks(rng, n_users, ctr, icc, lift=lift)
            # A/A
            fp["naive per-session"] += _naive_session_test(cc, sc, ca, sa)[2] < ALPHA
            fp["delta method"] += ratio_delta(cc, sc, ca, sa, ALPHA).p_value < ALPHA
            # A/B coverage of the true difference ctr * lift
            truth = ctr * lift
            d, se, _ = _naive_session_test(cc, sc, ct, st)
            cover["naive per-session"] += d - z * se <= truth <= d + z * se
            est = ratio_delta(cc, sc, ct, st, ALPHA)
            cover["delta method"] += est.ci_low <= truth <= est.ci_high
            se_ratio.append(se / est.se)
        for m in fp:
            fpr, cov = fp[m] / n_sims, cover[m] / n_sims
            rows.append(
                dict(
                    icc=icc,
                    method=m,
                    false_positive_rate=fpr,
                    fpr_mcse=_mcse(fpr, n_sims),
                    ci_coverage=cov,
                    coverage_mcse=_mcse(cov, n_sims),
                    naive_se_over_delta_se=float(np.mean(se_ratio)),
                    n_sims=n_sims,
                )
            )
    return _table(rows, n_users=n_users, ctr=ctr, relative_effect=lift, mean_sessions=6.0,
                  icc=[0.0, 0.02, 0.05, 0.10, 0.20], alpha=ALPHA)


# ------------------------------------------------------------------------- 5. SRM


def study_srm(n_sims: int = 2000, seed: int = 5) -> pd.DataFrame:
    """How often the SRM check fires, by sample size and true allocation skew."""
    rng = np.random.default_rng(seed)
    rows = []
    for n_total in (10_000, 100_000, 1_000_000):
        for share in (0.500, 0.501, 0.5025, 0.505, 0.510):
            n_t = rng.binomial(n_total, share, size=n_sims)
            flagged = sum(srm_test([n_total - k, k]).flagged for k in n_t)
            rate = flagged / n_sims
            rows.append(
                dict(
                    n_total=n_total, treatment_share=share, detection_rate=rate, mcse=_mcse(rate, n_sims), n_sims=n_sims
                )
            )
    return _table(rows, n_total=[10000, 100000, 1000000], expected_split=[0.5, 0.5],
                  treatment_share=[0.500, 0.501, 0.5025, 0.505, 0.510], threshold=0.001)


# --------------------------------------------------------- 6. power calibration


def study_power_calibration(n_sims: int = 2000, seed: int = 6) -> pd.DataFrame:
    """Do designs planned for 80% power actually achieve 80% power?"""
    rng = np.random.default_rng(seed)
    rows = []

    # conversion: 10% baseline, +10% relative MDE
    plan = sample_size_proportion(0.10, 0.10, relative=True, power=0.8)
    n = plan.n_control
    hits = sum(
        welch_ttest((rng.random(n) < 0.10).astype(float), (rng.random(n) < 0.11).astype(float)).p_value < ALPHA
        for _ in range(n_sims)
    )
    rows.append(
        dict(
            design="conversion 10% -> 11%",
            method="welch",
            n_per_arm=n,
            planned_power=0.8,
            empirical_power=hits / n_sims,
            mcse=_mcse(hits / n_sims, n_sims),
            n_sims=n_sims,
        )
    )

    # heavy-tailed revenue: +20% relative MDE, sd from the known distribution
    p, mu, sg = 0.08, 3.5, 1.2
    mean = p * np.exp(mu + sg**2 / 2)
    sd = np.sqrt(p * np.exp(2 * mu + 2 * sg**2) - mean**2)
    plan = sample_size_mean(0.2 * mean, sd, power=0.8, sd_treatment=sd * 1.2)
    n = plan.n_control
    sims = max(n_sims // 4, 200)
    hits = sum(
        welch_ttest(zero_inflated_lognormal(rng, n, p, mu, sg), zero_inflated_lognormal(rng, n, p, mu, sg, 1.2)).p_value
        < ALPHA
        for _ in range(sims)
    )
    rows.append(
        dict(
            design="revenue (zero-inflated lognormal) +20%",
            method="welch",
            n_per_arm=n,
            planned_power=0.8,
            empirical_power=hits / sims,
            mcse=_mcse(hits / sims, sims),
            n_sims=sims,
        )
    )

    # CUPED-planned design: rho = 0.6 -> variance_reduction = 0.36
    rho, eff = 0.6, 0.1
    plan_raw = sample_size_mean(eff, 1.0, power=0.8)
    plan = sample_size_mean(eff, 1.0, power=0.8, variance_reduction=rho**2)
    n = plan.n_control
    hits = 0
    for _ in range(n_sims):
        xc, yc = pre_post_normal(rng, n, rho)
        xt, yt = pre_post_normal(rng, n, rho, effect=eff)
        hits += cuped(yc, yt, xc, xt).p_value < ALPHA
    rows.append(
        dict(
            design=f"CUPED-planned, rho=0.6 (n {plan_raw.n_control:,} -> {n:,})",
            method="cuped",
            n_per_arm=n,
            planned_power=0.8,
            empirical_power=hits / n_sims,
            mcse=_mcse(hits / n_sims, n_sims),
            n_sims=n_sims,
        )
    )
    return _table(rows, target_power=0.8, conversion={"baseline": 0.10, "relative_effect": 0.10},
                  revenue={"p_purchase": p, "mu": mu, "sigma": sg, "relative_effect": 0.2},
                  cuped={"rho": rho, "effect": eff, "sd": 1.0}, alpha=ALPHA)


# ------------------------------------------------------------ 7. multiple testing


def study_multiple_testing(n_sims: int = 3000, seed: int = 7, n: int = 2_000) -> pd.DataFrame:
    """Many metrics, one experiment: chance of at least one false "win".

    Each simulated experiment tests ``m`` metrics with no true effect (Welch tests
    on independent normal metrics) plus, in the second scenario, ``m / 5`` metrics
    with a real effect, to show what each correction costs in power.
    """
    rng = np.random.default_rng(seed)
    effect = 3.0 * np.sqrt(2 / n)  # ~85% power per real metric
    rows = []
    for m in (1, 5, 14, 50):
        for scenario in ("all null", "20% real effects"):
            n_real = 0 if scenario == "all null" else max(m // 5, 1)
            any_false = {"none": 0, "holm": 0, "bh": 0}
            false_share = {"none": [], "holm": [], "bh": []}
            found = {"none": 0, "holm": 0, "bh": 0}
            for _ in range(n_sims):
                shifts = np.r_[np.full(n_real, effect), np.zeros(m - n_real)]
                p = np.array([welch_ttest(rng.standard_normal(n), rng.standard_normal(n) + s).p_value for s in shifts])
                is_null = shifts == 0
                for method in any_false:
                    rej = adjust(p, method) < ALPHA
                    any_false[method] += bool(np.any(rej & is_null))
                    false_share[method].append((rej & is_null).sum() / max(rej.sum(), 1))
                    found[method] += int((rej & ~is_null).sum())
            for method in any_false:
                fwer = any_false[method] / n_sims
                rows.append(
                    dict(
                        metrics=m,
                        scenario=scenario,
                        correction=method,
                        fwer=fwer,
                        fwer_mcse=_mcse(fwer, n_sims),
                        fdr=float(np.mean(false_share[method])),
                        power=found[method] / (n_sims * n_real) if n_real else np.nan,
                        n_sims=n_sims,
                    )
                )
    return _table(rows, n_per_arm=n, effect=effect, metrics=[1, 5, 14, 50],
                  real_metric_count="max(metrics // 5, 1) in the alternative scenario", alpha=ALPHA)


# --------------------------------------------------------------------- runner


def _headline(name: str, t: pd.DataFrame) -> str:
    if name == "type1_coverage":
        return (
            f"Welch false-positive rate {t.false_positive_rate.min():.1%}-{t.false_positive_rate.max():.1%} "
            f"and 95% CI coverage {t.ci_coverage.min():.1%}-{t.ci_coverage.max():.1%} across metrics and sizes."
        )
    if name == "peeking":
        aa = t[(t.scenario == "A/A (no effect)") & (t.looks == 100) & t.rejection_rate.notna()]
        naive = aa[aa.method.str.startswith("naive")].rejection_rate.iloc[0]
        av = aa[aa.method.str.startswith("mSPRT")].rejection_rate.iloc[0]
        return f"Peeking 100 times inflates false positives to {naive:.1%}; working-normal mSPRT has {av:.1%} empirically (not a formal guarantee)."
    if name == "cuped":
        r = t[(t.rho == 0.7) & (t.method == "cuped")].iloc[0]
        w = t[(t.rho == 0.7) & (t.method == "welch")].iloc[0]
        return (
            f"At rho=0.7 CUPED shrinks the SE to {r.se_ratio:.2f}x (theory {r.theory_se_ratio:.2f}x) and lifts "
            f"power from {w.power:.0%} to {r.power:.0%} with false-positive rate {r.false_positive_rate:.1%}."
        )
    if name == "ratio_metrics":
        r = t[(t.icc == 0.10) & (t.method == "naive per-session")].iloc[0]
        d = t[(t.icc == 0.10) & (t.method == "delta method")].iloc[0]
        return (
            f"At ICC=0.10, per-session analysis has a {r.false_positive_rate:.1%} false-positive rate; "
            f"the delta method has {d.false_positive_rate:.1%}."
        )
    if name == "srm":
        null = t[t.treatment_share == 0.5]
        return f"SRM check false-alarm rate {null.detection_rate.max():.2%} at threshold 0.001; detects a 50.5/49.5 split at n=100k {t[(t.n_total == 100_000) & (t.treatment_share == 0.505)].detection_rate.iloc[0]:.0%} of the time."
    if name == "multiple_testing":
        t14 = t[(t.metrics == 14) & (t.scenario == "all null")].set_index("correction")
        return (
            f"With 14 null metrics, P(at least one false win) is {t14.loc['none', 'fwer']:.0%} uncorrected, "
            f"{t14.loc['holm', 'fwer']:.1%} with Holm, {t14.loc['bh', 'fwer']:.1%} with Benjamini-Hochberg."
        )
    if name == "power_calibration":
        return "Planned 80% power -> empirical " + ", ".join(f"{p:.1%}" for p in t.empirical_power) + "."
    return ""


STUDIES: dict[str, tuple[str, Callable[..., pd.DataFrame], int]] = {
    "type1_coverage": (
        "Does the Welch test hold its 5% error rate and 95% coverage, even on heavy-tailed revenue?",
        study_type1_coverage,
        4000,
    ),
    "peeking": ("How does naive peeking compare with a working-normal mSPRT approximation?", study_peeking, 3000),
    "cuped": (
        "Does CUPED reduce variance as much as theory says, without inflating false positives?",
        study_cuped,
        3000,
    ),
    "ratio_metrics": (
        "What happens if a ratio metric is analysed per event instead of per user?",
        study_ratio_metrics,
        3000,
    ),
    "srm": ("How sensitive is the SRM check, and how often does it false-alarm?", study_srm, 2000),
    "power_calibration": ("Do 80%-power designs actually deliver 80% power?", study_power_calibration, 2000),
    "multiple_testing": ("How often does a many-metric readout produce a false win?", study_multiple_testing, 2000),
}


def run_all(scale: float = 1.0, only: list[str] | None = None, verbose: bool = True) -> dict[str, StudyResult]:
    """Run every study. ``scale`` multiplies the number of simulations (0.1 = quick)."""
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("scale must be finite and positive")
    if only is not None and (not only or set(only) - set(STUDIES)):
        raise ValueError(f"unknown or empty study selection; choose from {', '.join(STUDIES)}")
    runtime = runtime_provenance()
    out: dict[str, StudyResult] = {}
    for name, (question, fn, default_sims) in STUDIES.items():
        if only and name not in only:
            continue
        sims = max(int(default_sims * scale), 50)
        started = utc_now()
        t0 = time.perf_counter()
        table = fn(n_sims=sims)
        secs = time.perf_counter() - t0
        bound = inspect.signature(fn).bind_partial(n_sims=sims)
        bound.apply_defaults()
        metadata = {"simulated_at_utc": started, "runtime": runtime, "scale": scale,
                    "parameters": dict(bound.arguments), "alpha": ALPHA,
                    "implementation_sha256": hashlib.sha256(inspect.getsource(fn).encode("utf-8")).hexdigest(),
                    "scenario_configuration": table.attrs.get("design", {})}
        out[name] = StudyResult(name, question, table, _headline(name, table), secs, metadata)
        if verbose:
            print(f"[{name}] {secs:.1f}s  {out[name].headline}", flush=True)
    return out
