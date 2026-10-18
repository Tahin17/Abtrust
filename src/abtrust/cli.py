"""Command-line interface.

    abtrust plan --baseline 0.10 --mde 0.05 --relative --daily 20000
    abtrust plan --sd 42.0 --mde 1.5 --rho 0.5
    abtrust analyze data.csv --arm variant --control control \\
        --metric converted --metric revenue:pre_revenue --ratio orders/sessions --primary converted
    abtrust validate --scale 0.1 --out reports
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _cmd_plan(a: argparse.Namespace) -> int:
    from .design import sample_size_mean, sample_size_proportion

    if a.baseline is not None:
        plan = sample_size_proportion(a.baseline, a.mde, a.alpha, a.power, a.ratio, relative=a.relative)
    elif a.sd is not None:
        vr = a.rho**2 if a.rho else 0.0
        plan = sample_size_mean(a.mde, a.sd, a.alpha, a.power, a.ratio, variance_reduction=vr)
    else:
        print("error: give --baseline (conversion metric) or --sd (mean metric)", file=sys.stderr)
        return 2
    print(plan)
    if a.daily:
        print(f"At {a.daily:,.0f} new units/day: {plan.days(a.daily):.1f} days (round up to whole weeks).")
    return 0


def _parse_metrics(a: argparse.Namespace):
    from .readout import Metric

    primary = set(a.primary or [])
    guard = set(a.guardrail or [])
    lower = set(a.lower_is_better or [])
    margins = {}
    for item in a.guardrail_max_harm or []:
        name, sep, value = item.partition("=")
        if not sep:
            raise SystemExit("--guardrail-max-harm must be NAME=ABSOLUTE_MARGIN")
        try:
            margins[name] = float(value)
        except ValueError as exc:
            raise SystemExit(f"invalid guardrail margin {item!r}") from exc

    def role(name: str) -> str:
        return "primary" if name in primary else "guardrail" if name in guard else "secondary"

    metrics = []
    for spec in a.metric or []:
        col, _, cov = spec.partition(":")
        covs = tuple(c for c in cov.split(",") if c)
        covariate = None if not covs else covs[0] if len(covs) == 1 else covs
        metrics.append(Metric(col, column=col, covariate=covariate, role=role(col), higher_is_better=col not in lower, max_harm=margins.get(col)))
    for spec in a.ratio or []:
        num, sep, den = spec.partition("/")
        if not sep:
            raise SystemExit(f"error: --ratio expects NUMERATOR/DENOMINATOR, got {spec!r}")
        name = f"{num}/{den}"
        metrics.append(
            Metric(name, numerator=num, denominator=den, role=role(name), higher_is_better=name not in lower, max_harm=margins.get(name))
        )
    if not metrics:
        raise SystemExit("error: pass at least one --metric or --ratio")
    return metrics


def _cmd_analyze(a: argparse.Namespace) -> int:
    import pandas as pd

    from .readout import analyze

    df = pd.read_csv(a.data)
    split = None
    if a.split:
        parts = [float(x) for x in a.split.split(",")]
        arms = [str(a.control), *sorted(x for x in df[a.arm].astype(str).unique() if x != str(a.control))]
        if len(parts) != len(arms):
            raise SystemExit(f"error: --split needs {len(arms)} values in the order {arms}")
        split = dict(zip(arms, parts, strict=True))
    readout = analyze(
        df, a.arm, a.control, _parse_metrics(a), expected_split=split, alpha=a.alpha, correction=a.correction,
        unit_col=a.unit, missing_threshold=a.missing_threshold
    )
    md = readout.to_markdown(title=a.title)
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        print(f"Readout written to {a.out}")
        print(readout.decision())
    else:
        print(md)
    return 0


def _cmd_validate(a: argparse.Namespace) -> int:
    from .report import write_validation_report
    from .validation import run_all

    results = run_all(scale=a.scale, only=a.only)
    try:
        path = write_validation_report(results, a.out, figures=not a.no_figures)
    except ImportError as exc:
        print(f"{exc}; writing report without figures", file=sys.stderr)
        path = write_validation_report(results, a.out, figures=False)
    print(f"Report written to {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="abtrust", description="A/B test analysis you can trust.")
    p.add_argument("--version", action="version", version=f"abtrust {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser("plan", help="sample size for a planned experiment")
    pl.add_argument("--baseline", type=float, help="baseline conversion rate (conversion metric)")
    pl.add_argument("--sd", type=float, help="per-unit standard deviation (mean metric)")
    pl.add_argument("--mde", type=float, required=True, help="minimum detectable effect")
    pl.add_argument("--relative", action="store_true", help="--mde is relative to the baseline rate")
    pl.add_argument("--rho", type=float, default=0.0, help="correlation with a CUPED covariate (mean metric)")
    pl.add_argument("--alpha", type=float, default=0.05)
    pl.add_argument("--power", type=float, default=0.80)
    pl.add_argument("--ratio", type=float, default=1.0, help="n_treatment / n_control")
    pl.add_argument("--daily", type=float, help="new units entering per day, to estimate duration")
    pl.set_defaults(func=_cmd_plan)

    an = sub.add_parser("analyze", help="readout for a per-unit CSV (one row per user)")
    an.add_argument("data", help="CSV with one row per randomization unit")
    an.add_argument("--arm", required=True, help="column holding the arm label")
    an.add_argument("--control", required=True, help="label of the control arm")
    an.add_argument(
        "--metric", action="append", help="COLUMN, COLUMN:PRE_COVARIATE (CUPED) or COLUMN:COV1,COV2 (Lin); repeatable"
    )
    an.add_argument("--ratio", action="append", help="NUMERATOR/DENOMINATOR ratio metric; repeatable")
    an.add_argument("--primary", action="append", help="metric name that decides the experiment; repeatable")
    an.add_argument("--guardrail", action="append", help="metric that must not regress; repeatable")
    an.add_argument("--lower-is-better", action="append", help="metric where a decrease is good; repeatable")
    an.add_argument("--unit", help="unique randomized user ID column, e.g. user_id")
    an.add_argument("--missing-threshold", type=float, default=0.01,
                    help="block decisions when missingness in either arm or its imbalance exceeds this fraction")
    an.add_argument("--guardrail-max-harm", action="append", metavar="NAME=DELTA",
                    help="predeclared maximum acceptable ABSOLUTE harmful change (repeat for each guardrail)")
    an.add_argument("--split", help="designed allocation, control first, e.g. 50,50")
    an.add_argument("--alpha", type=float, default=0.05)
    an.add_argument("--correction", default="holm", choices=["holm", "bh", "none"])
    an.add_argument("--title", default="Experiment readout")
    an.add_argument("--out", help="write Markdown here instead of printing")
    an.set_defaults(func=_cmd_analyze)

    va = sub.add_parser("validate", help="run the Monte Carlo validation suite")
    va.add_argument("--scale", type=float, default=1.0, help="multiply simulation counts (0.1 = quick)")
    va.add_argument("--only", nargs="+", help="run only these studies")
    va.add_argument("--out", default="reports", help="output directory")
    va.add_argument("--no-figures", action="store_true")
    va.set_defaults(func=_cmd_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
