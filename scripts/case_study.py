"""Case study: a checkout redesign with planted analysis traps and known ground truth.

    python scripts/case_study.py            # writes reports/case_study.md + figures

The simulated experiment (``abtrust.simulate.ecommerce_experiment``) randomizes
200,000 users 50/50. The redesign truly raises the per-session purchase
probability by 4%. Five traps are planted:

1. a logging bug drops 60% of *treatment* users on the ``android_legacy``
   platform from the exposure log, and those users buy less than average;
2. revenue is heavy-tailed, so its confidence interval is wide;
3. "orders per session" is a ratio metric whose sessions are correlated within users;
4. the team checks the dashboard every day;
5. fourteen secondary/guardrail metrics have no true effect at all.

A "naive" analysis (what a rushed analyst would do) is compared with the
abtrust workflow, and both are scored against the truth.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import abtrust as ab
from abtrust import plots
from abtrust.report import md_table
from abtrust.simulate import ecommerce_experiment

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports"
FIG = OUT / "figures"
DAYS = 14
ALPHA = 0.05
Z = stats.norm.ppf(1 - ALPHA / 2)


def per_session_naive(df: pd.DataFrame) -> dict:
    """Orders per session analysed as if every session were independent (the trap)."""
    c, t = df[df.variant == "control"], df[df.variant == "treatment"]
    sc, st = c.sessions.sum(), t.sessions.sum()
    rc, rt = c.orders.sum() / sc, t.orders.sum() / st
    vc, vt = rc * (1 - rc) / sc, rt * (1 - rt) / st
    rel = rt / rc - 1
    se_rel = np.sqrt(vt / rc**2 + rt**2 * vc / rc**4)
    se = np.sqrt(vc + vt)
    return dict(
        rel_effect=rel,
        rel_ci_low=rel - Z * se_rel,
        rel_ci_high=rel + Z * se_rel,
        p_value=2 * stats.norm.sf(abs(rt - rc) / se),
    )


def arms(df: pd.DataFrame, col: str) -> tuple[np.ndarray, np.ndarray]:
    return df.loc[df.variant == "control", col].to_numpy(), df.loc[df.variant == "treatment", col].to_numpy()


def covers(truth: float, lo: float, hi: float) -> str:
    return "yes" if lo <= truth <= hi else "**no**"


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    logged, full, truth_by_pop = ecommerce_experiment(n_users=200_000, seed=2026)
    truth_all = truth_by_pop["all_users"]
    truth = truth_by_pop["excluding_android_legacy"]
    nulls = truth.null_metrics + ["unsubscribed", "support_contact"]

    # ------------------------------------------------------------ naive analyst
    n_conv = ab.welch_ttest(*arms(logged, "converted"))
    n_rev = ab.welch_ttest(*arms(logged, "revenue"))
    n_ops = per_session_naive(logged)
    naive_null_p = {m: ab.welch_ttest(*arms(logged, m)).p_value for m in nulls}
    naive_false = sorted(m for m, p in naive_null_p.items() if p < ALPHA)
    looks = np.arange(1, DAYS + 1) / DAYS
    seq_logged = ab.sequential_test(*arms(logged, "converted"), looks=looks)
    naive_stop = seq_logged.naive_stop_index
    naive_stop_look = seq_logged.looks[naive_stop] if naive_stop is not None else None

    # --------------------------------------------------------- abtrust, step 1
    metrics = [
        ab.Metric("conversion", column="converted", covariate="pre_sessions", role="primary"),
        ab.Metric("revenue per user", column="revenue", covariate="pre_revenue"),
        ab.Metric("orders per session", numerator="orders", denominator="sessions"),
        ab.Metric("unsubscribed", column="unsubscribed", role="guardrail", higher_is_better=False),
        ab.Metric("support_contact", column="support_contact", role="guardrail", higher_is_better=False),
        *[ab.Metric(m, column=m) for m in truth.null_metrics],
    ]
    raw_readout = ab.analyze(logged, "variant", "control", metrics, unit_col="user_id")
    seg = ab.srm_by_segment(logged, "variant", "platform")

    # --------------------------------------------------------- abtrust, step 2
    fixed = logged[logged.platform != "android_legacy"].reset_index(drop=True)
    readout = ab.analyze(fixed, "variant", "control", metrics, unit_col="user_id")
    (OUT / "case_study_readout.md").write_text(
        readout.to_markdown("Checkout redesign - readout after fixing the SRM"), encoding="utf-8"
    )
    tbl = readout.table.set_index("metric")
    a_conv, a_rev, a_ops = tbl.loc["conversion"], tbl.loc["revenue per user"], tbl.loc["orders per session"]
    holm_false = sorted(
        m
        for m in tbl.index
        if m in ("unsubscribed", "support_contact", *truth.null_metrics) and tbl.loc[m, "p_adjusted"] < ALPHA
    )
    unadj_rev = ab.welch_ttest(*arms(fixed, "revenue"))
    fixed_naive_ops = per_session_naive(fixed)

    # Working-normal replay on clean data; tau from a hypothetical PREDECLARED baseline. Not an exact guarantee.
    yc, yt = arms(fixed, "converted")
    tau = ab.tau_from_design(np.sqrt(0.2 * 0.8), n_per_arm=len(yc), alpha=ALPHA)
    seq = ab.sequential_test(yc, yt, looks=looks, tau=tau)
    traj = seq.to_frame().assign(day=np.arange(1, DAYS + 1))
    av_stop = seq.stop_index
    fixed_naive_stop = seq.naive_stop_index
    plots.trajectory_figure(
        traj,
        FIG / "case_peeking.png",
        None if fixed_naive_stop is None else fixed_naive_stop + 1,
        None if av_stop is None else av_stop + 1,
    )

    # ------------------------------------------------------------------ forest
    def row(label, kind, rel, lo, hi, tr):
        return dict(label=label, kind=kind, rel_effect=rel, rel_ci_low=lo, rel_ci_high=hi, truth=tr)

    forest = pd.DataFrame(
        [
            row(
                "Conversion - naive (buggy log)",
                "naive",
                n_conv.rel_effect,
                n_conv.rel_ci_low,
                n_conv.rel_ci_high,
                truth_all.conversion_rel,
            ),
            row(
                "Conversion - abtrust (after SRM fix)",
                "abtrust",
                a_conv.rel_effect,
                a_conv.rel_ci_low,
                a_conv.rel_ci_high,
                truth.conversion_rel,
            ),
            row(
                "Revenue/user - plain t-test",
                "naive",
                unadj_rev.rel_effect,
                unadj_rev.rel_ci_low,
                unadj_rev.rel_ci_high,
                truth.revenue_rel,
            ),
            row(
                "Revenue/user - abtrust CUPED",
                "abtrust",
                a_rev.rel_effect,
                a_rev.rel_ci_low,
                a_rev.rel_ci_high,
                truth.revenue_rel,
            ),
            row(
                "Orders/session - per-session",
                "naive",
                fixed_naive_ops["rel_effect"],
                fixed_naive_ops["rel_ci_low"],
                fixed_naive_ops["rel_ci_high"],
                truth.orders_per_session_rel,
            ),
            row(
                "Orders/session - abtrust delta method",
                "abtrust",
                a_ops.rel_effect,
                a_ops.rel_ci_low,
                a_ops.rel_ci_high,
                truth.orders_per_session_rel,
            ),
        ]
    )
    plots.forest_figure(
        forest,
        FIG / "case_forest.png",
        "Naive vs abtrust estimates against the truth",
        "95% CIs; orange = naive, blue = abtrust. Revenue and ratio rows use the same clean data.",
    )

    # ------------------------------------------------------------------ report
    counts_logged = logged.variant.value_counts()
    lost = int(full.variant.value_counts()["treatment"] - counts_logged["treatment"])
    width = lambda lo, hi: hi - lo  # noqa: E731
    rev_shrink = 1 - width(a_rev.ci_low, a_rev.ci_high) / width(unadj_rev.ci_low, unadj_rev.ci_high)
    ops_ratio = width(fixed_naive_ops["rel_ci_low"], fixed_naive_ops["rel_ci_high"]) / width(
        a_ops.rel_ci_low, a_ops.rel_ci_high
    )
    pct = lambda x: f"{x:+.2%}"  # noqa: E731
    ci = lambda lo, hi: f"[{lo:+.2%}, {hi:+.2%}]"  # noqa: E731

    score = pd.DataFrame(
        [
            dict(
                trap="1. Logging bug (SRM)",
                naive=f"not checked; reports conversion lift {pct(n_conv.rel_effect)} {ci(n_conv.rel_ci_low, n_conv.rel_ci_high)} vs truth {pct(truth_all.conversion_rel)} ({n_conv.rel_effect / truth_all.conversion_rel - 1:+.0%} overstated)",
                abtrust=f"SRM flagged (p={raw_readout.srm.p_value:.1e}); drill-down isolates `{seg.iloc[0].platform}`; after the fix {pct(a_conv.rel_effect)} {ci(a_conv.rel_ci_low, a_conv.rel_ci_high)} vs truth {pct(truth.conversion_rel)}",
            ),
            dict(
                trap="2. Heavy-tailed revenue",
                naive=f"plain t-test on the buggy log: {ci(n_rev.rel_ci_low, n_rev.rel_ci_high)}, p={n_rev.p_value:.3f}, called significant with no multiple-testing correction",
                abtrust=f"CUPED on clean data: {ci(a_rev.rel_ci_low, a_rev.rel_ci_high)}, {rev_shrink:.0%} narrower than a plain t-test on the same data; inconclusive after Holm (p_adj={a_rev.p_adjusted:.2f})"
                if a_rev.p_adjusted >= ALPHA
                else f"CUPED on clean data: {ci(a_rev.rel_ci_low, a_rev.rel_ci_high)}, {rev_shrink:.0%} narrower than a plain t-test on the same data; significant after Holm",
            ),
            dict(
                trap="3. Ratio metric",
                naive=f"per-session CI {ci(fixed_naive_ops['rel_ci_low'], fixed_naive_ops['rel_ci_high'])} (clean data)",
                abtrust=f"delta-method CI {ci(a_ops.rel_ci_low, a_ops.rel_ci_high)} - the naive one is {1 - ops_ratio:.0%} too narrow",
            ),
            dict(
                trap="4. Daily peeking",
                naive=(
                    f"stops on day {naive_stop + 1} of the buggy log claiming {pct(naive_stop_look.effect / naive_stop_look.control_mean)}"
                )
                if naive_stop is not None
                else "never crossed p < 0.05",
                abtrust=(
                    f"working-normal approximation crosses 0.05 on day {av_stop + 1} (lift then {pct(seq.looks[av_stop].effect / seq.looks[av_stop].control_mean)}); exploratory only"
                )
                if av_stop is not None
                else "working-normal approximation did not cross 0.05 within 14 days",
            ),
            dict(
                trap=f"5. {len(nulls)} null metrics",
                naive=f"{len(naive_false)} 'significant' at p < 0.05: {', '.join(naive_false) or 'none'}",
                abtrust=f"{len(holm_false)} after Holm correction: {', '.join(holm_false) or 'none'}",
            ),
        ]
    )

    est = pd.DataFrame(
        [
            dict(
                metric="conversion",
                naive=n_conv.rel_effect,
                truth_naive=truth_all.conversion_rel,
                naive_covers=covers(truth_all.conversion_rel, n_conv.rel_ci_low, n_conv.rel_ci_high),
                abtrust=a_conv.rel_effect,
                truth_abtrust=truth.conversion_rel,
                abtrust_covers=covers(truth.conversion_rel, a_conv.rel_ci_low, a_conv.rel_ci_high),
            ),
            dict(
                metric="revenue per user",
                naive=n_rev.rel_effect,
                truth_naive=truth_all.revenue_rel,
                naive_covers=covers(truth_all.revenue_rel, n_rev.rel_ci_low, n_rev.rel_ci_high),
                abtrust=a_rev.rel_effect,
                truth_abtrust=truth.revenue_rel,
                abtrust_covers=covers(truth.revenue_rel, a_rev.rel_ci_low, a_rev.rel_ci_high),
            ),
            dict(
                metric="orders per session",
                naive=n_ops["rel_effect"],
                truth_naive=truth_all.orders_per_session_rel,
                naive_covers=covers(truth_all.orders_per_session_rel, n_ops["rel_ci_low"], n_ops["rel_ci_high"]),
                abtrust=a_ops.rel_effect,
                truth_abtrust=truth.orders_per_session_rel,
                abtrust_covers=covers(truth.orders_per_session_rel, a_ops.rel_ci_low, a_ops.rel_ci_high),
            ),
        ]
    )

    seg_view = seg[["platform", "units", "share_control", "share_treatment", "p_value", "flagged"]]
    md = [
        "# Case study: the checkout redesign that almost shipped for the wrong reason",
        "",
        "A simulated but realistic experiment with **known ground truth**: 200,000 users randomized 50/50 to the "
        "old or redesigned checkout for two weeks. The redesign truly raises each user's per-session purchase "
        f"probability by 4%, which works out to a **{pct(truth_all.conversion_rel)} lift in conversion** and "
        f"**{pct(truth_all.revenue_rel)} in revenue per user**. Sessions, order values, the two guardrails and twelve "
        "engagement metrics are untouched by the change. Five traps are planted - the same ones that break real "
        "experiments. Reproduce with `python scripts/case_study.py`.",
        "",
        "## Scorecard",
        "",
        md_table(score.rename(columns={"trap": "Trap", "naive": "Naive analysis", "abtrust": "abtrust workflow"})),
        "",
        "![Forest plot](figures/case_forest.png)",
        "",
        "## Trap 1 - the logging bug",
        "",
        f"A JavaScript error on legacy Android drops {lost:,} treatment users from the exposure log (control is "
        f"unaffected). The analytics table therefore holds {counts_logged['control']:,} control and "
        f"{counts_logged['treatment']:,} treatment users. Those lost users buy at half the usual rate, so the "
        "treatment arm that remains looks better than it should.",
        "",
        f"**abtrust** refuses to report effects: `{raw_readout.decision()}` The per-platform drill-down "
        "(`abtrust.srm_by_segment`) points straight at the cause:",
        "",
        md_table(seg_view, {"share_control": ".2%", "share_treatment": ".2%", "p_value": ".2g"}),
        "",
        "The fix used here is to drop `android_legacy` from **both** arms (the comparison stays randomized within "
        "the remaining platforms) and to report the result for that population. The ground truth for that "
        f"population is a {pct(truth.conversion_rel)} conversion lift.",
        "",
        "## Traps 2-3 - precision done right",
        "",
        f"Revenue per user has a standard deviation {fixed.revenue.std() / fixed.revenue.mean():.1f} times its mean. "
        f"CUPED with each user's pre-period revenue (correlation {np.corrcoef(fixed.revenue, fixed.pre_revenue)[0, 1]:.2f}) "
        f"removes {a_rev.variance_reduction:.0%} of the variance of the estimate, so the interval is {rev_shrink:.0%} "
        "narrower than the plain t-test on identical data - the same precision as running the experiment "
        f"{1 / (1 - a_rev.variance_reduction) - 1:.0%} longer, for free. Revenue remains "
        + ("significant" if a_rev.p_adjusted < ALPHA else "inconclusive after correction")
        + f" (p = {a_rev.p_value:.3f}, Holm-adjusted {a_rev.p_adjusted:.3f}). The naive pipeline's 'significant' revenue "
        f"result (p = {n_rev.p_value:.3f}) was computed on the biased log and never corrected for the "
        f"{len(readout.table)} comparisons in the readout. Being honest about uncertainty is part of the job: the "
        "true +4% revenue effect exists, but this experiment alone cannot confirm it.",
        "",
        "Orders per session treats sessions as independent, but sessions of one user share that user's taste. "
        f"The per-session interval is {1 - ops_ratio:.0%} narrower than the correct per-user delta-method interval. "
        "Users here differ only moderately in their purchase propensity; the validation report shows how quickly "
        "per-session false-positive rates grow as that heterogeneity rises.",
        "",
        "## Trap 4 - peeking",
        "",
        "![Daily p-values](figures/case_peeking.png)",
        "",
    ]
    naive_txt = (
        f"The naive pipeline peeks at the buggy log every day and stops on **day {naive_stop + 1}**, announcing a "
        f"{pct(naive_stop_look.effect / naive_stop_look.control_mean)} lift - about "
        f"{(naive_stop_look.effect / naive_stop_look.control_mean) / truth_all.conversion_rel:.1f}x the truth. "
        if naive_stop is not None
        else "The naive pipeline's daily p-value never crosses 0.05. "
    )
    peek_csv = OUT / "validation" / "peeking.csv"
    if peek_csv.exists():
        pk = pd.read_csv(peek_csv)
        pk = pk[(pk.scenario == "A/A (no effect)") & pk.method.str.startswith("naive") & pk.rejection_rate.notna()]
        r10, r20 = (pk.set_index("looks").rejection_rate.get(k) for k in (10, 20))
        peek_rate = f"{r10:.0%} of no-effect experiments checked 10 times and {r20:.0%} of those checked 20 times"
    else:
        peek_rate = "far more than 5% of no-effect experiments"
    clean_txt = (
        f"On the clean data (chart above) the fixed-horizon p-value first dips below 0.05 on day {fixed_naive_stop + 1}. "
        "The effect is real, so stopping there would have been the right call - by luck: the same stopping rule "
        f"declares a winner in {peek_rate} (validation report). "
        if fixed_naive_stop is not None
        else ""
    )
    if av_stop is not None:
        av_txt = (
            f"The working-normal mSPRT approximation crosses 0.05 on day {av_stop + 1}; "
            "this uses estimated variance and does NOT establish an anytime-valid stopping decision."
        )
    else:
        av_txt = (
            "The working-normal mSPRT approximation does not cross 0.05 in this simulation; "
            "this is an exploratory replay, not a formal anytime-valid test."
        )
    md += [naive_txt + clean_txt + av_txt, "", ""]
    md += [
        "## Trap 5 - many metrics",
        "",
        f"Of the {len(nulls)} metrics with no true effect, the naive analysis flags {len(naive_false)} at p < 0.05 "
        f"({', '.join(naive_false) or 'none'}). With Holm correction across all {len(readout.table)} comparisons, "
        f"abtrust flags {len(holm_false)}. "
        + ("This run happened to be lucky - " if not naive_false else "")
        + f"with {len(nulls)} independent null metrics the chance of at least one spurious 'win' is "
        f"1 - 0.95^{len(nulls)} = {1 - 0.95 ** len(nulls):.0%} per experiment (the validation report measures it).",
        "",
        "## Estimates vs truth",
        "",
        "Each analysis is scored against the truth for the population it describes: all users for the naive "
        "pipeline (run on the buggy log), all but `android_legacy` for abtrust (run after the SRM fix). Covering the "
        "truth in one run is weak evidence either way - the validation report measures coverage over thousands of runs.",
        "",
        md_table(est, {"naive": "+.2%", "truth_naive": "+.2%", "abtrust": "+.2%", "truth_abtrust": "+.2%"}),
        "",
        "## Full abtrust readout (after the fix)",
        "",
        "See [`case_study_readout.md`](case_study_readout.md) - generated by `abtrust.analyze(...).to_markdown()`.",
        "",
        f"**Decision:** {readout.decision()}",
        "",
    ]
    (OUT / "case_study.md").write_text("\n".join(md), encoding="utf-8")

    summary = dict(
        truth_all=truth_all.__dict__,
        truth_fixed=truth.__dict__,
        naive=dict(
            conversion=n_conv.to_dict(),
            revenue=n_rev.to_dict(),
            orders_per_session=fixed_naive_ops,
            false_positives=naive_false,
            peeking_stop_day=None if naive_stop is None else naive_stop + 1,
        ),
        abtrust=dict(
            srm_p=raw_readout.srm.p_value,
            decision_raw=raw_readout.decision(),
            decision_fixed=readout.decision(),
            holm_false_positives=holm_false,
            sequential_stop_day=None if av_stop is None else av_stop + 1,
            revenue_ci_shrink=rev_shrink,
            ratio_ci_naive_over_delta=ops_ratio,
        ),
    )
    (OUT / "case_study.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")

    # small clean sample for the demo app and CLI examples
    sample = fixed.sample(40_000, random_state=7).sort_values("user_id")
    cols = [
        "user_id",
        "variant",
        "platform",
        "pre_sessions",
        "pre_revenue",
        "sessions",
        "orders",
        "converted",
        "revenue",
        "unsubscribed",
        "support_contact",
    ]
    (ROOT / "data").mkdir(exist_ok=True)
    sample[cols].to_csv(ROOT / "data" / "sample_experiment.csv", index=False)
    print(score.to_string(index=False))
    print(f"\nwrote {OUT / 'case_study.md'}")


if __name__ == "__main__":
    main()
