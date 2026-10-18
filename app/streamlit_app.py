"""abtrust demo app.

    pip install -e ".[app]"
    streamlit run app/streamlit_app.py

Three tabs: analyze an experiment CSV, plan a sample size, and watch peeking
inflate false positives live.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import abtrust as ab
from abtrust import plots
from abtrust.app_support import (
    arm_labels,
    expected_split_from_percentages,
    load_uploaded_csv,
    parse_harm_margin,
    validate_table,
)

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_experiment.csv"

st.set_page_config(page_title="abtrust - A/B tests you can trust", layout="wide")
st.title("abtrust")
st.caption(
    "A/B test analysis where every method is validated by simulation: SRM checks, CUPED, "
    "delta-method ratio metrics, sequential testing (assumptions stated) and multiple-testing control."
)

analyze_tab, plan_tab, peek_tab = st.tabs(["Analyze an experiment", "Plan sample size", "Why peeking fails"])


@st.cache_data
def load_sample() -> pd.DataFrame:
    return pd.read_csv(SAMPLE)


# ---------------------------------------------------------------------------- analyze
with analyze_tab:
    st.caption("Choose the RANDOMIZED experiment design, not the split you happened to observe. "
               "Outcomes and confidence intervals are descriptive evidence, not a shipping authorization.")
    source = st.radio("Data", ["Sample experiment (40,000 users)", "Upload a CSV"], horizontal=True)
    df = None
    if source.startswith("Upload"):
        upload = st.file_uploader("CSV: one row per randomized customer (max 25 MB)", type="csv")
        if upload is not None:
            try:
                df = load_uploaded_csv(upload.getvalue())
            except ValueError as exc:
                st.error(str(exc))
    else:
        try:
            df = load_sample()
            validate_table(df)
        except (ValueError, OSError, pd.errors.ParserError) as exc:
            st.error(f"Sample dataset could not be loaded: {exc}")

    if df is None:
        st.info("Select the included sample or upload a UTF-8 CSV with arm labels and numeric outcomes.")
    else:
        st.dataframe(df.head(20), width="stretch")
        cols = list(df.columns)
        numeric = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
        arm_col = st.selectbox("Arm column (experiment group)", cols, index=cols.index("variant") if "variant" in cols else 0)
        try:
            arm_values = arm_labels(df, arm_col)
        except ValueError as exc:
            st.error(str(exc))
            arm_values = []
        if arm_values:
            control = st.selectbox("Control arm (old experience)", arm_values,
                                   index=arm_values.index("control") if "control" in arm_values else 0)
            allocation_choice = st.radio("Expected allocation from the experiment design",
                                         ["Equal split", "Custom allocation (%)"], horizontal=True)
            expected_split = None
            input_errors = []
            if allocation_choice == "Custom allocation (%)":
                st.caption("Enter the split that was planned BEFORE collecting data. Percentages must sum to 100.")
                split_cols = st.columns(len(arm_values))
                shares = {}
                for slot, arm_name in zip(split_cols, arm_values, strict=True):
                    with slot:
                        shares[arm_name] = st.number_input(
                            f"Planned % — {arm_name}", min_value=0.0, max_value=100.0,
                            value=100.0 / len(arm_values), step=0.1,
                            format="%.2f", key=f"allocation_{arm_name}",
                        )
                try:
                    expected_split = expected_split_from_percentages(arm_values, shares)
                except ValueError as exc:
                    input_errors.append(str(exc))
            else:
                st.caption(f"Assuming {100 / len(arm_values):.2f}% per arm by experiment design. "
                           "Change to custom allocation for unequal or multi-arm designs.")
            left, right = st.columns(2)
            with left:
                defaults = [c for c in ("converted", "revenue", "unsubscribed", "support_contact") if c in numeric]
                metric_cols = st.multiselect("Metrics (numeric per-user outcomes)", numeric, default=defaults)
                primary = st.selectbox("Primary metric (main experiment outcome)",
                                       ["(none)", *metric_cols], index=1 if metric_cols else 0)
                unit_col = st.selectbox("Unique randomized unit ID (strongly recommended)", ["(not provided)", *cols],
                                        index=cols.index("user_id") + 1 if "user_id" in cols else 0)
                if unit_col == "(not provided)":
                    st.warning("No unique IDs: the project cannot check that each user appears exactly once.")
                guardrails = st.multiselect("Guardrail metrics (risks to constrain)",
                                            [m for m in metric_cols if m != primary],
                                            default=[m for m in ("unsubscribed", "support_contact")
                                                     if m in metric_cols and m != primary])
                harm_margins, higher_is_better = {}, {}
                for g in guardrails:
                    direction = st.selectbox(f"Desired direction for {g}", ["Lower is better", "Higher is better"],
                                             key=f"guardrail_dir_{g}")
                    higher_is_better[g] = direction == "Higher is better"
                    raw = st.text_input(
                        f"Max acceptable ABSOLUTE harm for {g} (predeclared; blank = unassessed)",
                        "", key=f"margin_{g}",
                    )
                    try:
                        harm_margins[g] = parse_harm_margin(raw, g)
                    except ValueError as exc:
                        input_errors.append(str(exc))
            with right:
                covariates = {}
                for m in metric_cols:
                    guess = {"revenue": "pre_revenue", "converted": "pre_sessions"}.get(m, "(none)")
                    options = ["(none)", *[c for c in numeric if c != m]]
                    cov = st.selectbox(
                        f"Pre-experiment covariate for {m} (CUPED)", options,
                        index=options.index(guess) if guess in options else 0,
                    )
                    if cov != "(none)":
                        covariates[m] = cov
                if len(numeric) >= 2:
                    use_ratio = st.checkbox("Add a ratio metric", value={"orders", "sessions"} <= set(numeric))
                else:
                    use_ratio = False
                ratio = None
                if use_ratio:
                    num = st.selectbox("Numerator", numeric,
                                       index=numeric.index("orders") if "orders" in numeric else 0)
                    den = st.selectbox("Denominator", numeric,
                                       index=numeric.index("sessions") if "sessions" in numeric else 1)
                    ratio = (num, den)
                    if num == den:
                        input_errors.append("Ratio numerator and denominator must be different columns.")
                correction = st.selectbox("Multiple-testing correction", ["holm", "bh", "none"])
                alpha = st.number_input("Alpha (significance level)", min_value=0.001, max_value=0.2,
                                        value=0.05, step=0.01, format="%.3f", key="analysis_alpha")
                missing_threshold = st.number_input("Maximum missing fraction per arm",
                                                    min_value=0.0, max_value=1.0, value=0.01,
                                                    step=0.005, format="%.3f")
                st.caption("P-values are adjusted across comparisons, but the displayed confidence intervals "
                           "are UNADJUSTED. Guardrail upper harm bounds are adjusted separately (Bonferroni). "
                           "Absolute and relative intervals may differ near zero due to approximation.")

            if not metric_cols and ratio is None:
                input_errors.append("Select at least one metric.")
            for message in input_errors:
                st.error(message)
            if not input_errors:
                metrics = [
                    ab.Metric(m, column=m, covariate=covariates.get(m),
                              role="primary" if m == primary else "guardrail" if m in guardrails else "secondary",
                              higher_is_better=higher_is_better.get(m, True),
                              max_harm=harm_margins.get(m))
                    for m in metric_cols
                ]
                if ratio:
                    metrics.append(ab.Metric(f"{ratio[0]}/{ratio[1]}", numerator=ratio[0], denominator=ratio[1]))
                try:
                    readout = ab.analyze(
                        df, arm_col, control, metrics, expected_split=expected_split,
                        alpha=alpha, correction=correction,
                        unit_col=None if unit_col == "(not provided)" else unit_col,
                        missing_threshold=missing_threshold,
                    )
                except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
                    st.error(f"Analysis could not be completed: {exc}")
                else:
                    decision = readout.decision()
                    (st.error if decision.startswith("DO NOT") else st.success if decision.startswith("SHIP") else st.info)(
                        decision
                    )
                    srm = readout.srm
                    (st.error if srm.flagged else st.success)(
                        ("SRM check FAILED - " if srm.flagged else "SRM check passed - ") + srm.summary()
                    )
                    st.caption("Effects show treatment minus control. Relative lift divides by the control baseline. "
                               f"Unadjusted {1 - readout.alpha:.0%} CIs are not multiplicity-corrected, even when Holm-adjusted "
                               "p-values appear in the same table.")
                    table = readout.table
                    fields = ["arm", "metric", "role", "method", "n_control", "n_treatment",
                              "control_mean", "treatment_mean", "effect", "ci_low", "ci_high",
                              "rel_effect", "rel_ci_low", "rel_ci_high", "p_value", "p_adjusted",
                              "harm_upper_bound", "safety_pass", "verdict"]
                    view = table[fields]
                    st.dataframe(view.style.format(
                        {"control_mean": "{:.4g}", "treatment_mean": "{:.4g}",
                         "effect": "{:+.4g}", "ci_low": "{:+.4g}", "ci_high": "{:+.4g}",
                         "rel_effect": "{:+.2%}", "rel_ci_low": "{:+.2%}",
                         "rel_ci_high": "{:+.2%}", "p_value": "{:.4f}", "p_adjusted": "{:.4f}",
                         "harm_upper_bound": "{:.4g}"}, na_rep="n/a"), width="stretch")
                    if (table.role == "guardrail").any():
                        st.caption("Guardrail safety_pass requires a predeclared harm margin and a conservative "
                                   "upper bound below it. A nonsignificant harmful change is NOT proof of safety.")
                    rows = table.replace([np.inf, -np.inf], np.nan).dropna(
                        subset=["rel_effect", "rel_ci_low", "rel_ci_high"]
                    ).assign(label=lambda d: d.arm + " - " + d.metric, kind="abtrust", truth=np.nan)
                    if len(rows):
                        try:
                            buf = io.BytesIO()
                            plots.forest_figure(
                                rows[["label", "rel_effect", "rel_ci_low", "rel_ci_high", "truth", "kind"]],
                                buf, "Relative effects", f"Unadjusted {1 - readout.alpha:.0%} confidence intervals",
                            )
                            st.image(buf.getvalue())
                        except (ValueError, RuntimeError) as exc:
                            st.warning(f"The plot could not be generated, but the readout is available: {exc}")
                    for note in readout.notes:
                        st.markdown(f"- {note}")
                    st.download_button("Download readout (Markdown)", readout.to_markdown(),
                                       file_name="readout.md", mime="text/markdown")

# ------------------------------------------------------------------------------- plan
with plan_tab:
    kind = st.radio("Metric type", ["Conversion rate", "Continuous (revenue, time...)"], horizontal=True)
    c1, c2, c3 = st.columns(3)
    alpha = c3.number_input("alpha", 0.001, 0.2, 0.05, step=0.01)
    power = c3.number_input("power", 0.5, 0.99, 0.8, step=0.05)
    plan = None
    if kind == "Conversion rate":
        base = c1.number_input("Baseline rate", 0.001, 0.999, 0.10, step=0.01, format="%.3f")
        mde = c2.number_input("Relative MDE", 0.001, 2.0, 0.05, step=0.01, format="%.3f")
        treatment_rate = base * (1 + mde)
        if not 0 < treatment_rate < 1:
            st.error(f"The planned treatment rate would be {treatment_rate:.1%}. "
                     "Choose a baseline and relative MDE that keep it strictly between 0% and 100%.")
        else:
            plan = ab.sample_size_proportion(base, mde, alpha, power, relative=True)
    else:
        sd = c1.number_input("Standard deviation per user", 0.001, 1e9, 40.0)
        mde = c2.number_input("Absolute MDE", 0.0001, 1e9, 1.0)
        rho = c2.slider("Correlation with pre-period metric (CUPED)", 0.0, 0.95, 0.0)
        plan = ab.sample_size_mean(mde, sd, alpha, power, variance_reduction=rho**2)
    daily = st.number_input("Users entering the experiment per day", 1, 100_000_000, 20_000)
    if plan is not None:
        m1, m2, m3 = st.columns(3)
        m1.metric("Users per arm", f"{plan.n_control:,}")
        m2.metric("Total users", f"{plan.total:,}")
        m3.metric("Days", f"{plan.days(daily):.1f}")
        st.caption("Round the duration up to whole weeks so every weekday is represented equally.")

# ------------------------------------------------------------------------------- peek
with peek_tab:
    st.markdown(
        "Simulate experiments with **no true effect**. Ordinary tests cannot be repeatedly inspected "
        "without increasing false positives. Choose a finite-sample bounded-data method (valid for 0/1 outcomes) "
        "or the legacy working-normal mSPRT approximation (empirical diagnostic only)."
    )
    p1, p2 = st.columns(2)
    looks = p1.slider("Looks per experiment", 1, 100, 20)
    sims = p2.slider("Simulated experiments", 100, 2000, 400, step=100)
    method = st.selectbox("Sequential method", ["Bounded 0/1 (rigorous Hoeffding)",
                                                   "Working-normal mSPRT (approximate, not guaranteed)"])
    if st.button("Run simulation"):
        rng = np.random.default_rng(0)
        n, rate = 4000, 0.10
        tau = ab.tau_from_design(np.sqrt(rate * (1 - rate)), n)
        naive = av = 0
        for _ in range(sims):
            res = ab.sequential_test(
                (rng.random(n) < rate).astype(float), (rng.random(n) < rate).astype(float), looks=looks, tau=tau if method.startswith("Working") else None,
                mode="working_normal" if method.startswith("Working") else "bounded"
            )
            naive += res.naive_stop_index is not None
            av += res.stop_index is not None
        a1, a2 = st.columns(2)
        a1.metric(
            "Naive t-test false positives",
            f"{naive / sims:.1%}",
            delta=f"{naive / sims - 0.05:+.1%} vs promised 5%",
            delta_color="inverse",
        )
        a2.metric("Sequential procedure false positives", f"{av / sims:.1%}")
        if method.startswith("Working"):
            st.warning("Working-normal mSPRT uses estimated variance: a low simulated false-positive rate is not "
                       "an exact anytime-valid guarantee. Set tau from a predeclared design.")
        else:
            st.caption("Hoeffding + summable error spending protects bounded independent [0,1] per-unit outcomes "
                       "at prespecified monitoring looks; it can be conservative.")
