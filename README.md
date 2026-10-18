# abtrust

**A/B test analysis toolkit with reproducible simulation-based checks (not mathematical proofs).**

> v0.3.0 adds planned allocation settings for unequal experiments, safer CSV/guardrail handling, clearer results, and stronger tests. **This is a research/portfolio toolkit, not deployment certification.**

[![CI](https://github.com/Tahin17/Abtrust/actions/workflows/ci.yml/badge.svg)](https://github.com/Tahin17/Abtrust/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Most A/B-test mistakes are not exotic. Teams check the dashboard every day and stop at the first p < 0.05.
They analyse clicks per session as if sessions were independent. They miss a logging bug that silently
drops users from one arm. They report 20 metrics and celebrate the one that moved. Each mistake produces
confident, wrong decisions.

`abtrust` is a small Python library and CLI for SRM checks, CUPED variance
reduction, delta-method ratio metrics, sequential methods with explicit validity assumptions, multiple-testing control and power
analysis - and includes **a Monte Carlo validation suite** that tests the library's own methods
under documented synthetic conditions. Simulation cannot prove general validity.

<p align="center"><img src="reports/figures/peeking.png" width="680" alt="False-positive rate vs number of looks: naive t-test rises to 38%, mSPRT stays below 2%"></p>

## What the validation suite shows

| Question | Common practice | abtrust | Evidence |
|---|---|---|---|
| Does checking results daily break the test? | Peeking 20x: **25.4%** false positives (100x: **38.1%**) | working-normal mSPRT (empirical only): **1.3%** (1.6%) | [Study 2](reports/validation.md#how-does-naive-peeking-compare-with-a-working-normal-msprt-approximation) |
| Can pre-period data buy precision for free? | Plain t-test: 50% power | CUPED at rho = 0.7: **79% power**, same data, 5.3% false positives | [Study 3](reports/validation.md#does-cuped-reduce-variance-as-much-as-theory-says-without-inflating-false-positives) |
| Are per-session metrics safe? | Per-session CI covers the truth **78%** of the time (ICC = 0.2) | Delta method: **94.7%** | [Study 4](reports/validation.md#what-happens-if-a-ratio-metric-is-analysed-per-event-instead-of-per-user) |
| How often does a 14-metric readout "find" a winner by chance? | **52%** of experiments | Holm: **5.7%** (5% within Monte Carlo error) | [Study 7](reports/validation.md#how-often-does-a-many-metric-readout-produce-a-false-win) |
| Does the SRM check catch broken experiments without crying wolf? | - | 0.10% false alarms; catches a 50.5/49.5 split **45%** of the time at 100k users, always at 1M | [Study 5](reports/validation.md#how-sensitive-is-the-srm-check-and-how-often-does-it-false-alarm) |
| Do power calculations deliver? | - | Planned 80% -> **79.4%, 80.2%, 79.8%** empirical | [Study 6](reports/validation.md#do-80-power-designs-actually-deliver-80-power) |
| Is the t-test OK on heavy-tailed revenue? | - | 3.9-5.1% false positives, 94.4-95.9% coverage from n = 500 per arm | [Study 1](reports/validation.md#does-the-welch-test-hold-its-5-error-rate-and-95-coverage-even-on-heavy-tailed-revenue) |

Every rate comes with its Monte Carlo standard error in [`reports/validation.md`](reports/validation.md).
Sequential inference is not free: at exactly the MDE, approximate mSPRT with 100 looks detects the effect 48% of the
time versus 78% for a single fixed-horizon test - but at twice the MDE it stops after 36% of the planned
sample on average. The report shows both sides.

The bounded procedure also depends strongly on the monitoring schedule: at twice the MDE, the corrected
validation measures **78.8% power with one look** versus **0.23% with 100 looks** in this scenario.
Each schedule now uses its own error budget. See [current verification](docs/RELEASE_VERIFICATION.md).

## Case study: the checkout redesign that almost shipped for the wrong reason

A realistic simulated experiment - 200,000 users, a redesign with a true **+3.2% conversion lift** - with five
planted traps. [Full write-up](reports/case_study.md).

| Trap | Naive analysis | abtrust workflow |
|---|---|---|
| Logging bug drops legacy-Android users from treatment | Reports **+4.45%** (40% overstated) | **SRM flagged** (p = 1.8e-8), per-platform drill-down finds the bug; after the fix **+3.30%** vs truth +3.16% |
| Daily peeking | Stops on **day 2** claiming +5.3% | Legacy working-normal approximation crosses on day 11; exploratory, not certified anytime-valid |
| Heavy-tailed revenue | "Significant" (p = 0.025) on the biased log, no correction | CUPED: 11% less variance; honestly inconclusive after correcting for 17 comparisons |
| Orders per session | Per-session CI 8% too narrow | Per-user delta method |

<p align="center"><img src="reports/figures/case_forest.png" width="640" alt="Naive vs abtrust estimates against the true effect"></p>

## Quickstart

```bash
git clone https://github.com/Tahin17/Abtrust.git && cd Abtrust
pip install -e ".[dev]"          # core needs only numpy, scipy, pandas
pytest                           # 121 tests (+ 1 optional Streamlit AppTest)
```

**Plan** an experiment:

```console
$ abtrust plan --baseline 0.10 --mde 0.05 --relative --daily 20000
57,760 control + 57,760 treatment = 115,520 units (MDE=0.005, alpha=0.05, power=80%)
At 20,000 new units/day: 5.8 days (round up to whole weeks).
```

**Analyze** a per-user CSV (the bundled sample has 40,000 users):

```console
$ abtrust analyze data/sample_experiment.csv --arm variant --control control \
    --metric converted:pre_sessions --metric revenue:pre_revenue --ratio orders/sessions \
    --primary converted --guardrail unsubscribed --metric unsubscribed --lower-is-better unsubscribed --unit user_id
```

**Python API:**

```python
import pandas as pd
import abtrust as ab

df = pd.read_csv("data/sample_experiment.csv")
readout = ab.analyze(
    df, arm_col="variant", control="control", unit_col="user_id",
    metrics=[
        ab.Metric("conversion", column="converted", covariate="pre_sessions", role="primary"),
        ab.Metric("revenue", column="revenue", covariate="pre_revenue"),          # CUPED
        ab.Metric("orders per session", numerator="orders", denominator="sessions"),  # delta method
        ab.Metric("unsubscribed", column="unsubscribed", role="guardrail", higher_is_better=False, max_harm=0.002),  # choose before launch
    ],
)
print(readout.decision())     # SRM gate -> guardrails -> primary metric
print(readout.to_markdown())  # shareable readout

# replay an experiment with the BOUNDED binary-outcome anytime-valid procedure
seq = ab.sequential_test(df.query("variant == 'control'").converted,
                         df.query("variant == 'treatment'").converted, looks=14, mode="bounded")
print(seq.stop_index, seq.final.p_value)
```

**Demo app** (analyze a CSV, plan a test, watch peeking fail live):

```bash
pip install -e ".[app]" && streamlit run app/streamlit_app.py
```

## What's inside

| Module | Methods |
|---|---|
| `abtrust.design` | sample size / MDE / power for conversion and continuous metrics, unequal splits, CUPED-aware planning |
| `abtrust.checks` | SRM chi-square test and per-segment SRM drill-down |
| `abtrust.estimators` | Welch t-test, delta-method relative lift, ratio metrics (delta method), CUPED, Lin regression adjustment with HC2 SEs |
| `abtrust.sequential` | rigorous bounded-outcome confidence sequence, exact known-SD Gaussian mixture, and clearly labelled working-normal approximation |
| `abtrust.multiple` | Holm, Benjamini-Hochberg |
| `abtrust.readout` | one-call `analyze()` with verdicts, a conservative decision rule and a Markdown report |
| `abtrust.validation` | the seven Monte Carlo studies behind every claim above |

The math, assumptions and references for each method are in [`docs/methods.md`](docs/methods.md).

## Reproduce everything

```bash
abtrust validate                    # full suite, several minutes; --scale 0.1 for a quick run
python scripts/case_study.py        # case study + figures + data/sample_experiment.csv
python scripts/hillstrom.py         # real data (below)
```

The full local workflow is also available as one command:

```powershell
python scripts/verify.py --integration --full
```

This records actual check exit codes, runs the seven full-budget core studies and separate supplemental
stress studies, and regenerates the application reports. It uses the existing cached Hillstrom CSV when
available and records whether real data was run. See [reproducibility instructions](docs/REPRODUCIBILITY.md).

```powershell
abtrust stress --simulations 2000    # supplemental diagnostics in reports/stress/
abtrust render --out reports        # presentation only; verifies and preserves raw results
python scripts/dashboard_fixtures.py  # explicitly synthetic browser fixtures in scratch_qa/
```

Study manifests record actual seeds, budgets, settings, software versions, source hashes and CSV checksums.
The [learning walkthrough and three-minute demo](docs/LEARNING_AND_DEMO.md) explains the results from first principles.

## Real data: the Hillstrom e-mail experiment

[`scripts/hillstrom.py`](scripts/hillstrom.py) analyses Kevin Hillstrom's public MineThatData experiment:
64,000 customers randomized to a men's e-mail, a women's e-mail or no e-mail. It runs the SRM check against the
1/3 split, Lin regression adjustment on last year's spend and recency, a delta-method spend-per-visitor metric
(with a caveat about post-treatment denominators), Holm correction, and an exploratory subgroup table. Run it
once to download the data and write [`reports/hillstrom.md`](reports/hillstrom.md).

## v0.3 dashboard and quality controls

The [Windows / VS Code run guide](abtrust-run-guide-v0.3.md) contains step-by-step installation and instructions.
The interactive dashboard supports **equal or custom designed allocations** (for example, 20%/80% or 33.33%/33.33%/33.34%), explicit per-user IDs, predeclared guardrail harm margins and their desired direction, and input validation for uploaded CSVs. **Do not infer the planned split from observed group counts.** See [dashboard QA checklist](docs/DASHBOARD_QA.md).

The Hillstrom file does not document stable source user IDs and lacks messaging-safety guardrail outcomes. The direct men's-versus-women's comparison is a **separate exploratory testing family**; it should not be treated as a preplanned confirmatory result alongside the original arm-vs-control contrasts. The correct decision remains **REVIEW REQUIRED** even when conversion rises.

The readout displays **unadjusted confidence intervals**, separately corrected p-values (Holm or BH), and conservative Bonferroni guardrail harm bounds. These quantities should not be conflated.

## Design decisions and limitations

- **Many fixed-horizon estimates use normal approximations.** Validated down to 500 users per arm on heavy-tailed revenue; for
  much smaller tests use a permutation test.
- **Rare-event intervals need particular caution.** In the supplemental 0.2%-baseline, 400-users-per-arm
  scenario, nominal 95% Welch intervals covered the nonzero effect only 84.75% of the time. This approximation
  is not established as reliable in that sparse setting; see [the stress report](reports/stress/validation.md).
- **The decision rule is deliberately conservative**: an SRM or excessive missingness blocks all conclusions; 
  missing predeclared guardrail margins lead to REVIEW REQUIRED, and Holm correction spans arm x metric comparisons. Teams that pre-register a single
  primary metric can relax this with `correction="none"` on that metric alone.
- **Sequential assumptions matter.** The plug-in mSPRT is exploratory, not proved anytime-valid. For a rigorous time-uniform bound use `mode="bounded"` with independent outcomes in [0,1], or `mode="gaussian_known_sd"` with genuinely known Gaussian SD and a prespecified `tau`. Both require a stable population and valid randomization.
- **Ratio metrics with treatment-affected denominators** (spend per visitor when the treatment changes who
  visits) are diagnostics, not causal effects on a fixed group - see the Hillstrom report.
- Not covered (yet): Bayesian analysis, variance-weighted heterogeneous-effect estimation, interference between
  units (marketplaces, social networks), switchback designs.

## Repository layout

```
src/abtrust/       library (design, checks, estimators, sequential, multiple, readout, validation, plots, cli)
tests/             unit, statistical and smoke tests
scripts/           case_study.py, hillstrom.py
reports/           validation.md, case_study.md, figures/, raw CSV results
docs/methods.md    derivations, assumptions, references
app/               Streamlit demo
data/              sample_experiment.csv (40,000 simulated users)
```

## References

Kohavi, Tang & Xu, *Trustworthy Online Controlled Experiments* (2020) - the book this project's name nods to -
plus Deng et al. (2013, 2018), Lin (2013), Johari et al. (2017), Howard et al. (2021) and Fabijan et al. (2019);
full list in [`docs/methods.md`](docs/methods.md#references).

---

Built by **MD. Nafiul Haque Nafee** (BRAC University, CSE) - MIT licensed.
