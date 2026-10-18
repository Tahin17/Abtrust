"""Real-data case study: Kevin Hillstrom's MineThatData e-mail experiment (2008).

64,000 customers who bought in the last 12 months were randomized into three
groups for a two-week e-mail campaign: a men's merchandise e-mail, a women's
merchandise e-mail, or no e-mail. Outcomes: site visit, conversion and spend.
Pre-treatment covariates include last year's spend (``history``) and months since
last purchase (``recency``) - ideal for regression adjustment.

    python scripts/hillstrom.py                 # downloads the CSV (~4 MB) and writes reports/hillstrom.md
    python scripts/hillstrom.py --csv my.csv    # use a copy you downloaded yourself

If the download fails, get the CSV from the MineThatData blog post "Kevin
Hillstrom's MineThatData E-Mail Analytics And Data Mining Challenge" (2008) and
pass it with ``--csv``.
"""

from __future__ import annotations

import argparse
import io
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

import abtrust as ab
from abtrust.report import md_table

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports"
CACHE = ROOT / "data" / "hillstrom.csv"
SOURCES = [
    "http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv",
    "https://hillstorm1.s3.us-east-2.amazonaws.com/hillstorm_no_indices.csv.gz",
]
REQUIRED = {"recency", "history", "mens", "womens", "newbie", "segment", "visit", "conversion", "spend"}
CONTROL = "No E-Mail"


def load(csv: str | None) -> pd.DataFrame:
    if csv:
        return pd.read_csv(csv)
    if CACHE.exists():
        return pd.read_csv(CACHE)
    errors = []
    for url in SOURCES:
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 - fixed, trusted URLs
                raw = resp.read()
            df = pd.read_csv(io.BytesIO(raw), compression="gzip" if url.endswith(".gz") else None)
            CACHE.parent.mkdir(exist_ok=True)
            df.to_csv(CACHE, index=False)
            print(f"downloaded {len(df):,} rows from {url}")
            return df
        except Exception as exc:  # pragma: no cover - network dependent
            errors.append(f"{url}: {exc}")
    raise SystemExit(
        "could not download the Hillstrom data:\n  " + "\n  ".join(errors) + "\nDownload it manually and pass --csv"
    )


def analyze_hillstrom(df: pd.DataFrame) -> tuple[str, ab.Readout]:
    """Full readout plus an exploratory subgroup table, as Markdown."""
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"not the Hillstrom schema; missing columns {sorted(missing)}")
    df = df.copy()
    covs = ("history", "recency")
    metrics = [
        ab.Metric("visit", column="visit", covariate=covs, role="primary"),
        ab.Metric("conversion", column="conversion", covariate=covs),
        ab.Metric("spend per customer", column="spend", covariate=covs),
        ab.Metric("spend per visitor", numerator="spend", denominator="visit"),
    ]
    arms = sorted(df.segment.unique())
    # The original published file has no stable, documented participant ID.
    # Do not fabricate IDs from row position: that would make the uniqueness
    # check appear to pass without verifying the original randomization units.
    id_columns = [c for c in ("customer_id", "user_id") if c in df.columns]
    unit_col = id_columns[0] if id_columns else None
    readout = ab.analyze(df, "segment", CONTROL, metrics,
                         expected_split={a: 1 / 3 for a in arms}, unit_col=unit_col)

    # exploratory: does each e-mail work on customers who bought that category last year?
    rows = []
    for label, mask in (
        ("bought men's last year", df.mens == 1),
        ("bought women's last year", df.womens == 1),
        ("new customers", df.newbie == 1),
        ("returning customers", df.newbie == 0),
    ):
        sub = df[mask]
        for arm in [a for a in arms if a != CONTROL]:
            c = sub.loc[sub.segment == CONTROL, "visit"]
            t = sub.loc[sub.segment == arm, "visit"]
            est = ab.welch_ttest(c, t)
            rows.append(
                dict(
                    subgroup=label,
                    arm=arm,
                    n=len(c) + len(t),
                    control_rate=est.control_mean,
                    treatment_rate=est.treatment_mean,
                    rel_lift=est.rel_effect,
                    ci_low=est.rel_ci_low,
                    ci_high=est.rel_ci_high,
                    p_value=est.p_value,
                )
            )
    sg = pd.DataFrame(rows)
    sg["p_holm"] = ab.holm(sg.p_value)

    md = readout.to_markdown("Hillstrom e-mail experiment - abtrust readout").splitlines()
    # Direct randomized comparison between the TWO e-mail variants, rather than
    # choosing solely by which lift against no e-mail happens to be larger.
    pair = df[df.segment.isin(["Womens E-Mail", "Mens E-Mail"])].copy()
    pairwise = ab.analyze(pair, "segment", "Womens E-Mail", metrics,
                         expected_split={"Womens E-Mail": 0.5, "Mens E-Mail": 0.5}, unit_col=unit_col)
    pt = pairwise.table.copy()
    pt["contrast"] = "Mens E-Mail minus Womens E-Mail"
    ptview = pt[["metric", "effect", "ci_low", "ci_high", "p_value", "p_adjusted", "verdict"]]
    md += ["", "## Direct comparison: men's versus women's email", "",
           "Randomized pairwise comparison among recipients of either message (men's minus women's). "
           "Four metrics are Holm-adjusted across this direct comparison; the direct comparison is "
           "essential before claiming one message outperformed the other. This is a separate exploratory "
           "family of four tests; Holm correction is NOT joint across the 8 control contrasts and these 4 tests. "
           "Do not interpret the two families as a single confirmatory analysis.", "",
           md_table(ptview, {"effect": "+.4g", "ci_low": "+.4g", "ci_high": "+.4g",
                            "p_value": ".3g", "p_adjusted": ".3g"}), ""]
    md += [
        "",
        "## Exploratory: visit lift by customer subgroup",
        "",
        "Subgroups are defined by pre-treatment attributes only. Holm correction is applied across the "
        f"{len(sg)} subgroup tests; treat these as hypotheses for the next experiment, not conclusions.",
        "",
        md_table(
            sg,
            {
                "control_rate": ".2%",
                "treatment_rate": ".2%",
                "rel_lift": "+.1%",
                "ci_low": "+.1%",
                "ci_high": "+.1%",
                "p_value": ".2g",
                "p_holm": ".2g",
            },
        ),
        "",
        "## Caveat: spend per visitor",
        "",
        "Spend per visitor divides by a post-treatment quantity: the e-mail changes *who* visits. If it brings in "
        "less-committed visitors, spend per visitor can fall even though spend per customer rises. That makes it a "
        "useful diagnostic but not a causal effect on any fixed group of people; decisions should rest on the "
        "per-customer metrics, whose denominator (everyone randomized) the treatment cannot change.",
        "",
        "## Data provenance and deployment-safety limitations",
        "",
        "The publicly distributed Hillstrom dataset does not document a stable original customer ID. "
        "By default the script therefore cannot verify that every row represents a distinct randomized person. "
        "If an input file supplies a `customer_id` or `user_id` column, the analysis verifies its uniqueness; "
        "an artificially generated row number is NOT a substitute for a source identifier.",
        "",
        "The public dataset contains no prespecified unsubscribe, complaint, delivery or adverse-experience "
        "guardrail outcomes. A significant visit or conversion improvement is NOT evidence that deployment is "
        "safe or beneficial after messaging costs. The decision remains REVIEW REQUIRED and requires a business "
        "and safety review.",
        "",
        "Exploratory subgroup contrasts are not treatment-by-subgroup interaction tests: a significant change "
        "in one subgroup and a nonsignificant change in another do not establish that effects differ. "
        "Use a prespecified interaction test in a future experiment.",
        "",
        "## How this was produced",
        "",
        "`python scripts/hillstrom.py` - visit, conversion and spend use Lin regression adjustment on last year's "
        "spend (`history`) and `recency` with HC2 robust standard errors; spend per visitor is a ratio metric "
        "(delta method); Holm correction across all arm x metric comparisons; SRM check against the designed "
        "1/3 split.",
        "",
    ]
    return "\n".join(md), readout


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", help="path to the Hillstrom CSV (skips the download)")
    ap.add_argument("--out", default=str(OUT / "hillstrom.md"))
    args = ap.parse_args()
    df = load(args.csv)
    md, readout = analyze_hillstrom(df)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(md, encoding="utf-8")
    print(readout.srm.summary())
    print(readout.decision())
    print(f"wrote {args.out}")


def synthetic_hillstrom(n: int = 64_000, seed: int = 0) -> pd.DataFrame:
    """A stand-in with the real schema (used by the tests; NOT the real data)."""
    rng = np.random.default_rng(seed)
    seg = rng.choice(["Mens E-Mail", "Womens E-Mail", CONTROL], n)
    mens = (rng.random(n) < 0.55).astype(int)
    womens = np.where(mens == 1, (rng.random(n) < 0.2).astype(int), 1)
    history = np.round(rng.gamma(1.2, 200, n) + 30, 2)
    recency = rng.integers(1, 13, n)
    base = 0.08 + 0.04 * (history > 300) - 0.003 * recency
    lift = np.where(seg == "Mens E-Mail", 0.07 * mens + 0.02, np.where(seg == "Womens E-Mail", 0.05 * womens, 0.0))
    visit = (rng.random(n) < np.clip(base + lift, 0, 1)).astype(int)
    conversion = visit * (rng.random(n) < 0.08).astype(int)
    spend = np.round(conversion * rng.lognormal(4.5, 0.6, n), 2)
    return pd.DataFrame(
        {
            "recency": recency,
            "history_segment": "",
            "history": history,
            "mens": mens,
            "womens": womens,
            "zip_code": rng.choice(["Urban", "Suburban", "Rural"], n),
            "newbie": (rng.random(n) < 0.5).astype(int),
            "channel": rng.choice(["Web", "Phone", "Multichannel"], n),
            "segment": seg,
            "visit": visit,
            "conversion": conversion,
            "spend": spend,
        }
    )


if __name__ == "__main__":
    main()
