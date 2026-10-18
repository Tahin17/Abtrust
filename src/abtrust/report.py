"""Write the validation results to Markdown, CSV and PNG figures."""

from __future__ import annotations

import json
import platform
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .provenance import file_sha256, runtime_provenance, utc_now
from .validation import StudyResult

__all__ = ["md_table", "write_validation_report", "load_validation_results", "render_validation_report"]


def md_table(df: pd.DataFrame, formats: Mapping[str, str] | None = None) -> str:
    """Render a DataFrame as a GitHub Markdown table without extra dependencies."""
    formats = dict(formats or {})
    cols = list(df.columns)
    out = [
        "| " + " | ".join(cols) + " |",
        "|" + "|".join("---:" if pd.api.types.is_numeric_dtype(df[c]) else "---" for c in cols) + "|",
    ]
    for row in df.itertuples(index=False):
        cells = []
        for c, v in zip(cols, row, strict=True):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                cells.append("")
            elif c in formats:
                cells.append(format(v, formats[c]))
            elif isinstance(v, (int, np.integer)):
                cells.append(f"{v:,}")
            elif isinstance(v, (float, np.floating)):
                cells.append(f"{v:.4g}")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def _section(name: str, r: StudyResult) -> list[str]:
    t = r.table
    lines = [f"### {r.question}", "", f"**Result:** {r.headline}", ""]
    if name == "type1_coverage":
        view = t[["metric", "n_per_arm", "false_positive_rate", "fpr_mcse", "ci_coverage", "coverage_mcse"]]
        fm = {"false_positive_rate": ".2%", "fpr_mcse": ".2%", "ci_coverage": ".2%", "coverage_mcse": ".2%"}
        lines += [
            md_table(view, fm),
            "",
            "Target: false-positive rate 5%, coverage 95%. The revenue metric is zero-inflated "
            "lognormal (8% buyers, heavy right tail), the hardest case for a t-test.",
        ]
    elif name == "peeking":
        rates = t[t.rejection_rate.notna()].pivot_table(
            index=["scenario", "looks"], columns="method", values="rejection_rate"
        )
        rates = rates.reset_index()
        rates.columns.name = None
        fm = {c: ".1%" for c in rates.columns if c not in ("scenario", "looks")}
        summary = t[t.rejection_rate.isna()][
            ["scenario", "method", "mean_sample_fraction", "simultaneous_coverage", "naive_simultaneous_coverage"]
        ]
        lines += [
            "![Peeking](figures/peeking.png)",
            "",
            "Rejection rate by number of looks (A/A = false-positive rate; other scenarios = power):",
            "Each bounded procedure uses its own monitoring schedule and error budget, starting at look 1.",
            "",
            md_table(rates, fm),
            "",
            "Cost and benefit of each sequential procedure (100 looks):",
            "",
            md_table(
                summary,
                {"mean_sample_fraction": ".0%", "simultaneous_coverage": ".1%", "naive_simultaneous_coverage": ".1%"},
            ),
            "",
            "`mean_sample_fraction` is the average fraction of planned observations used before the named "
            "procedure first rejects. `simultaneous_coverage` is the fraction of simulations whose intervals "
            "cover the true effect at every look. The **working-normal** mSPRT is empirical ONLY and does not "
            "inherit a formal anytime-valid guarantee from these rates. The bounded Hoeffding result does have "
            "a time-uniform guarantee under its independent [0,1], stable-mean assumptions, but may be extremely "
            "conservative. `gaussian_known_sd` requires independent Gaussian outcomes with genuinely known SDs, "
            "equal arm sizes and prespecified tau.",
        ]
    elif name == "cuped":
        view = t[
            [
                "rho",
                "method",
                "se_ratio",
                "theory_se_ratio",
                "reported_se_over_empirical_sd",
                "false_positive_rate",
                "power",
            ]
        ]
        fm = {
            "rho": ".1f",
            "se_ratio": ".3f",
            "theory_se_ratio": ".3f",
            "reported_se_over_empirical_sd": ".3f",
            "false_positive_rate": ".2%",
            "power": ".1%",
        }
        lines += [
            "![CUPED](figures/cuped.png)",
            "",
            md_table(view, fm),
            "",
            "`lin_hc2` is regression adjustment with treatment interactions and HC2 robust SEs (Lin, 2013). "
            "`reported_se_over_empirical_sd` close to 1 means each method's reported SE is honest.",
        ]
    elif name == "ratio_metrics":
        view = t[["icc", "method", "false_positive_rate", "ci_coverage", "naive_se_over_delta_se"]]
        fm = {"icc": ".2f", "false_positive_rate": ".2%", "ci_coverage": ".2%", "naive_se_over_delta_se": ".3f"}
        lines += ["![Ratio metrics](figures/ratio_metrics.png)", "", md_table(view, fm)]
    elif name == "srm":
        view = t.pivot_table(index="treatment_share", columns="n_total", values="detection_rate").reset_index()
        view.columns = ["treatment_share", *[f"n={c:,}" for c in view.columns[1:]]]
        fm = {c: ".1%" for c in view.columns}
        fm["treatment_share"] = ".2%"
        lines += [
            "![SRM](figures/srm.png)",
            "",
            md_table(view, fm),
            "",
            "The first row (true 50/50 split) is the false-alarm rate; the target is the 0.1% threshold.",
        ]
    elif name == "multiple_testing":
        view = t[["metrics", "scenario", "correction", "fwer", "fdr", "power"]]
        lines += [
            md_table(view, {"fwer": ".1%", "fdr": ".1%", "power": ".1%"}),
            "",
            "`fwer` = probability of at least one false positive; `fdr` = average share of false positives among "
            "rejections; `power` = share of real effects detected. Holm controls FWER, "
            "while BH controls FDR under its standard dependence assumptions; in this ALL-NULL scenario FDR = FWER. "
            "For this simulation; values slightly above 5% sit within about 1.5 Monte Carlo standard "
            "errors (roughly 0.5 points at 2,000 simulations) - note the single-metric row, where no correction "
            "is applied at all, shows the same excess, so it comes from the simulation draw.",
        ]
    elif name == "power_calibration":
        view = t[["design", "method", "n_per_arm", "planned_power", "empirical_power", "mcse", "n_sims"]]
        lines += [md_table(view, {"planned_power": ".0%", "empirical_power": ".1%", "mcse": ".1%"})]
    else:
        lines += [md_table(t), "", "Results are synthetic diagnostics under the assumptions recorded in the manifest. "
                  "The INVALID selection scenario intentionally violates the analysis assumptions; constant outcomes "
                  "are a deterministic fixture, not a guarantee for rare-event inference."]
    lo, hi = int(t.n_sims.min()), int(t.n_sims.max())
    budget = f"{hi:,} simulated experiments per cell" if lo == hi else (
        f"{lo:,}–{hi:,} simulated experiments per cell; exact counts shown in n_sims"
    )
    lines += ["", f"<sub>{budget} · {r.seconds:.0f}s</sub>", ""]
    return lines


def write_validation_report(
    results: Mapping[str, StudyResult], out_dir: str | Path = "reports", figures: bool = True
) -> Path:
    """Write ``validation.md``, one CSV per study and (optionally) PNG figures."""
    out = Path(out_dir)
    if not results:
        raise ValueError("cannot write an empty validation run")
    data_dir = out / "validation"
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, r in results.items():
        r.table.to_csv(data_dir / f"{name}.csv", index=False)
    meta = {
        "schema_version": 2,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "studies": {
            n: {"question": r.question, "headline": r.headline, "seconds": round(r.seconds, 1),
                "metadata": r.metadata, "csv_sha256": file_sha256(data_dir / f"{n}.csv")}
            for n, r in results.items()
        },
    }
    (data_dir / "summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return _render_validation_report(results, out, meta, figures)


def _render_validation_report(results: Mapping[str, StudyResult], out: Path, meta: dict, figures: bool) -> Path:
    supplemental = all(name.startswith("stress_") for name in results)

    if figures:
        from . import plots

        figdir = out / "figures"
        if "peeking" in results:
            plots.peeking_figure(results["peeking"].table, figdir / "peeking.png")
        if "cuped" in results:
            plots.cuped_figure(results["cuped"].table, figdir / "cuped.png")
        if "ratio_metrics" in results:
            plots.ratio_figure(results["ratio_metrics"].table, figdir / "ratio_metrics.png")
        if "srm" in results:
            plots.srm_figure(results["srm"].table, figdir / "srm.png")

    lines = [
        "# Supplemental stress validation (synthetic)" if supplemental else "# Validation report",
        "",
        "This report measures selected methods empirically under the listed simulations. Simulations cannot prove "
        "a general statistical guarantee. In particular the original mSPRT inserts estimated variances into "
        "a known-variance likelihood ratio: its displayed sequential results are a WORKING-NORMAL APPROXIMATION, "
        "not an exact anytime-valid test. For exact assumptions see docs/methods.md. Columns ending in `mcse` "
        "are Monte Carlo standard errors of simulated rates.",
        "",
        f"Simulation results saved {meta['generated_utc']} UTC with Python {meta['python']}, numpy {meta['numpy']}. "
        + (f"Reproduce with `abtrust stress --simulations {max(int(r.table.n_sims.max()) for r in results.values())}`. "
           "These are supplemental studies, separate from the seven core studies."
           if supplemental else "Reproduce the full core suite with `abtrust validate`; use a separate `--out` directory for reduced-budget runs."),
        "",
        "## Summary",
        "",
    ]
    lines += [f"- **{r.question}** {r.headline}" for r in results.values()]
    lines += ["", "## Details", ""]
    for name, r in results.items():
        lines += _section(name, r)
    path = out / "validation.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    rendering = {"rendered_at_utc": utc_now(), "runtime": runtime_provenance(),
                 "simulation_manifest_sha256": file_sha256(out / "validation" / "summary.json")}
    (out / "validation" / "rendering.json").write_text(json.dumps(rendering, indent=2), encoding="utf-8")
    return path


def load_validation_results(out_dir: str | Path = "reports") -> dict[str, StudyResult]:
    """Reload results written by :func:`write_validation_report` (to re-render figures)."""
    data_dir = Path(out_dir) / "validation"
    meta = json.loads((data_dir / "summary.json").read_text(encoding="utf-8"))["studies"]
    res = {}
    for name in meta:
        if Path(name).name != name or not name.replace("_", "").isalnum():
            raise ValueError(f"invalid saved study name {name!r}")
        f = data_dir / f"{name}.csv"
        if f.exists():
            m = meta.get(name, {})
            if m.get("csv_sha256") and file_sha256(f) != m["csv_sha256"]:
                raise ValueError(f"saved results checksum mismatch: {f.name}; investigate before rendering")
            res[name] = StudyResult(
                name, m.get("question", ""), pd.read_csv(f, float_precision="round_trip"),
                m.get("headline", ""), m.get("seconds", 0.0), m.get("metadata", {})
            )
        else:
            raise ValueError(f"saved results missing: {f.name}")
    return res


def render_validation_report(out_dir: str | Path = "reports", figures: bool = True) -> Path:
    """Rebuild presentation only; preserve the CSV bytes and simulation manifest."""
    out = Path(out_dir)
    results = load_validation_results(out)
    if not results:
        raise ValueError("no saved studies to render")
    meta = json.loads((out / "validation" / "summary.json").read_text(encoding="utf-8"))
    return _render_validation_report(results, out, meta, figures)
