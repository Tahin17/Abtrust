"""Figures for the validation report and case study (requires matplotlib).

One visual language across every figure: abtrust's method is always blue, the
naive/common-practice method is always orange, nominal targets are a dashed gray
reference line, and series are labelled directly as well as in a legend.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

try:  # optional dependency
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, PercentFormatter
except ImportError:  # pragma: no cover - exercised only without matplotlib
    plt = None

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
GOOD = "#2a78d6"  # abtrust method (categorical slot 1)
NAIVE = "#eb6834"  # naive method (categorical slot 2)
RAMP = ["#86b6ef", "#2a78d6", "#104281"]  # ordinal blue (sample size)


def _require() -> None:
    if plt is None:
        raise ImportError("plotting needs matplotlib: pip install 'abtrust[viz]'")


def _style(ax, title: str, subtitle: str | None = None) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelsize=9, length=0, pad=6)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=11.5, color=INK, fontweight="bold", pad=22 if subtitle else 10)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2, va="bottom")
    ax.xaxis.label.set_color(INK_2)
    ax.yaxis.label.set_color(INK_2)


def _fig(ncols: int = 1, width: float = 7.2, height: float = 4.0):
    _require()
    fig, axes = plt.subplots(1, ncols, figsize=(width, height), dpi=150, facecolor=SURFACE)
    return fig, np.atleast_1d(axes)


def _save(fig, path):
    """Save to a path (parent folders created) or any binary file-like object."""
    if isinstance(path, (str, Path)):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


def _reference(ax, y: float, label: str, x: float | None = None, below: bool = False) -> None:
    ax.axhline(y, color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2, zorder=1)
    x = ax.get_xlim()[0] if x is None else x
    ax.annotate(
        label,
        (x, y),
        xytext=(0, -4 if below else 4),
        textcoords="offset points",
        color=MUTED,
        fontsize=8.5,
        va="top" if below else "bottom",
        ha="left",
    )


def _end_label(ax, x, y, text: str, color: str, dy: float = 0.0) -> None:
    ax.annotate(
        text,
        (x, y),
        xytext=(6, dy),
        textcoords="offset points",
        color=INK_2,
        fontsize=9,
        va="center",
        ha="left",
        fontweight="bold",
    )
    ax.plot([x], [y], marker="o", markersize=5, color=color, markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=4)


def _band(ax, x, y, se, color):
    y, se = np.asarray(y), np.asarray(se)
    ax.fill_between(x, y - 1.96 * se, y + 1.96 * se, color=color, alpha=0.15, linewidth=0)


# ----------------------------------------------------------------- validation


def peeking_figure(table: pd.DataFrame, path: Path) -> Path:
    t = table[(table.scenario == "A/A (no effect)") & table.rejection_rate.notna()]
    fig, (ax,) = _fig()
    for method, color, label in (
        ("naive t-test (peeking)", NAIVE, "Naive t-test"),
        ("mSPRT (working-normal approximate)", GOOD, "Approx. mSPRT"),
        ("Hoeffding CS (bounded, valid)", "#6B4D9B", "Bounded Hoeffding"),
    ):
        s = t[t.method == method].sort_values("looks")
        ax.plot(
            s.looks,
            s.rejection_rate,
            color=color,
            linewidth=2,
            label=label,
            marker="o",
            markersize=4,
            markeredgecolor=SURFACE,
        )
        _band(ax, s.looks, s.rejection_rate, s.mcse, color)
        _end_label(ax, s.looks.iloc[-1], s.rejection_rate.iloc[-1], f"{label}  {s.rejection_rate.iloc[-1]:.1%}", color)
    ax.set_xscale("log")
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100], ["1", "2", "5", "10", "20", "50", "100"])
    ax.set_xlim(0.85, 260)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0, max(0.45, t.rejection_rate.max() * 1.1))
    ax.set_xlabel("Number of times the analyst checks the result")
    ax.set_ylabel("False-positive rate (A/A tests)")
    _reference(ax, 0.05, "promised 5%", x=2.6)
    worst = t[t.method.str.startswith("naive")].rejection_rate.max()
    _style(
        ax,
        f"Checking 100 times turns a 5% error rate into {worst:.0%}",
        "Stop at the first p < 0.05: share of no-effect experiments declared winners",
    )
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0.0, 0.93), labelcolor=INK_2)
    return _save(fig, path)


def cuped_figure(table: pd.DataFrame, path: Path) -> Path:
    fig, (ax1, ax2) = _fig(2, width=9.6, height=4.0)
    rho = np.linspace(0, 0.95, 100)
    ax1.plot(
        rho, np.sqrt(1 - rho**2), color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2, label="Theory sqrt(1 - rho^2)"
    )
    c = table[table.method == "cuped"].sort_values("rho")
    ax1.plot(
        c.rho,
        c.se_ratio,
        color=GOOD,
        marker="o",
        linewidth=0,
        markersize=7,
        markeredgecolor=SURFACE,
        label="CUPED (simulated)",
    )
    ax1.set_xlabel("Correlation of pre-period metric with outcome (rho)")
    ax1.set_ylabel("SE relative to unadjusted test")
    ax1.set_ylim(0, 1.1)
    _style(ax1, "Variance reduction matches theory", "Spread of CUPED estimates vs plain t-test")
    ax1.legend(frameon=False, fontsize=9, loc="lower left", labelcolor=INK_2)

    for method, color, label in (("welch", NAIVE, "Unadjusted t-test"), ("cuped", GOOD, "CUPED")):
        s = table[table.method == method].sort_values("rho")
        ax2.plot(
            s.rho, s.power, color=color, linewidth=2, marker="o", markersize=4, markeredgecolor=SURFACE, label=label
        )
        _band(ax2, s.rho, s.power, s.power_mcse, color)
    ax2.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax2.set_ylim(0, 1.05)
    ax2.set_xlabel("Correlation of pre-period metric with outcome (rho)")
    ax2.set_ylabel("Power (same effect, same n)")
    _style(ax2, "Same data, more power", "Probability of detecting a fixed true effect")
    ax2.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK_2)
    return _save(fig, path)


def ratio_figure(table: pd.DataFrame, path: Path) -> Path:
    fig, (ax,) = _fig()
    for method, color, label in (
        ("naive per-session", NAIVE, "Per-session (naive)"),
        ("delta method", GOOD, "Delta method"),
    ):
        s = table[table.method == method].sort_values("icc")
        ax.plot(
            s.icc,
            s.ci_coverage,
            color=color,
            linewidth=2,
            marker="o",
            markersize=4,
            markeredgecolor=SURFACE,
            label=label,
        )
        _band(ax, s.icc, s.ci_coverage, s.coverage_mcse, color)
        _end_label(
            ax,
            s.icc.iloc[-1],
            s.ci_coverage.iloc[-1],
            f"{label}  {s.ci_coverage.iloc[-1]:.0%}",
            color,
            dy=9 if method == "delta method" else 0,
        )
    ax.set_xlim(-0.01, 0.30)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0.6, 1.0)
    ax.set_xlabel("Within-user correlation of clicks (ICC)")
    ax.set_ylabel("Actual coverage of the 95% CI")
    _reference(ax, 0.95, "promised 95%", x=0.08, below=True)
    _style(ax, "Per-session CIs are overconfident", "Clicks per session, 2,000 users per arm")
    ax.legend(frameon=False, fontsize=9, loc="lower left", labelcolor=INK_2)
    return _save(fig, path)


def srm_figure(table: pd.DataFrame, path: Path) -> Path:
    fig, (ax,) = _fig()
    for color, (n, s) in zip(RAMP, table.groupby("n_total"), strict=False):
        s = s.sort_values("treatment_share")
        label = f"{n:,} users"
        ax.plot(
            s.treatment_share,
            s.detection_rate,
            color=color,
            linewidth=2,
            marker="o",
            markersize=4,
            markeredgecolor=SURFACE,
            label=label,
        )
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1%}"))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlim(0.4995, 0.5105)
    ax.set_ylim(-0.02, 1.05)
    ax.set_xlabel("True share of users landing in treatment (design: 50%)")
    ax.set_ylabel("SRM detection rate (p < 0.001)")
    _style(ax, "Small allocation bugs are invisible until traffic is large", "Chi-square SRM check")
    leg = ax.legend(
        frameon=False,
        fontsize=9,
        loc="center right",
        bbox_to_anchor=(1.0, 0.42),
        labelcolor=INK_2,
        title="Total sample size",
        title_fontsize=9,
        alignment="left",
    )
    leg.get_title().set_color(INK_2)
    return _save(fig, path)


# ------------------------------------------------------------------ case study


def trajectory_figure(frame: pd.DataFrame, path: Path, stop_naive: int | None, stop_av: int | None) -> Path:
    """Daily p-values: naive fixed-horizon vs working-normal approximation. ``frame`` has columns day, naive_p_value, p_value."""
    fig, (ax,) = _fig()
    ax.plot(
        frame.day,
        frame.naive_p_value,
        color=NAIVE,
        linewidth=2,
        marker="o",
        markersize=4,
        markeredgecolor=SURFACE,
        label="Naive t-test p-value",
    )
    ax.plot(
        frame.day,
        frame.p_value,
        color=GOOD,
        linewidth=2,
        marker="o",
        markersize=4,
        markeredgecolor=SURFACE,
        label="Working-normal mSPRT (approximate)",
    )
    ax.set_yscale("log")
    ax.set_ylim(max(min(frame.naive_p_value.min(), frame.p_value.min()) / 3, 1e-6), 1.5)
    ax.set_xticks(frame.day)
    ax.set_xlabel("Day of experiment")
    ax.set_ylabel("p-value (log scale)")
    _reference(ax, 0.05, "alpha = 0.05")
    for day, color, label in ((stop_naive, NAIVE, "naive"), (stop_av, GOOD, "approx. mSPRT")):
        if day is not None:
            ax.axvline(day, color=color, linewidth=1, alpha=0.5)
            ax.text(day, 1.1, f" {label} stops", color=INK_2, fontsize=8.5, va="top")
    _style(ax, "When could we have stopped?", "Conversion, checked once a day")
    ax.legend(frameon=False, fontsize=9, loc="lower left", labelcolor=INK_2)
    return _save(fig, path)


def forest_figure(rows: pd.DataFrame, path: Path, title: str, subtitle: str) -> Path:
    """Relative-effect intervals. ``rows`` has label, rel_effect, rel_ci_low, rel_ci_high, truth, kind (naive/abtrust)."""
    fig, (ax,) = _fig(height=0.55 * len(rows) + 1.6)
    y = np.arange(len(rows))[::-1]
    for yi, r in zip(y, rows.itertuples(index=False), strict=True):
        color = NAIVE if r.kind == "naive" else GOOD
        ax.plot([r.rel_ci_low, r.rel_ci_high], [yi, yi], color=color, linewidth=2.5, solid_capstyle="round")
        ax.plot(
            [r.rel_effect], [yi], marker="o", color=color, markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5
        )
        if np.isfinite(r.truth):
            ax.plot([r.truth], [yi], marker="|", color=INK, markersize=14, markeredgewidth=2)
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.set_yticks(y, rows.label)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Relative effect, treatment vs control (black tick = true effect)")
    _style(ax, title, subtitle)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.tick_params(axis="y", colors=INK_2)
    return _save(fig, path)
