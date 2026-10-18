# abtrust: Run Guide

Everything you need to install, run, check and publish the **abtrust** project: what it is, what your laptop needs, every command in order, what output to expect, and what to do when something goes wrong.

---

## 1. What this project is

**abtrust** is a Python library, command-line tool and demo app for analysing A/B tests correctly. Its distinguishing feature is that every statistical method ships with a **Monte Carlo validation study**: the library's own code is run on thousands of simulated experiments where the true answer is known, to prove it does what it claims.

It is built for your data-scientist portfolio. It is not an NLP project and not a generic classifier.

### What it covers

| Module | What it does |
|---|---|
| `abtrust.design` | Sample size, minimum detectable effect (MDE) and power |
| `abtrust.checks` | Sample ratio mismatch (SRM) test, plus per-segment drill-down |
| `abtrust.estimators` | Welch t-test, delta-method ratio metrics, CUPED, Lin regression adjustment |
| `abtrust.sequential` | Always-valid p-values (mixture SPRT), safe to check daily |
| `abtrust.multiple` | Holm and Benjamini-Hochberg corrections |
| `abtrust.readout` | One-call `analyze()` that produces a verdict and a Markdown report |
| `abtrust.validation` | The seven Monte Carlo studies behind every claim |

### Headline results (from `reports/validation.md`)

| Question | Common practice | abtrust |
|---|---|---|
| Checking results every day (100 looks) | 38.1% false positives | 1.6% with the always-valid test |
| Using pre-experiment data (CUPED, correlation 0.7) | 50% power | 79% power, same data |
| Orders-per-session metric | Per-session CI covers the truth 78% of the time | Delta method: 94.7% |
| 14 metrics with no real effect | 52% chance of a false "win" | 5.7% with Holm correction |
| Planned 80% power | n/a | 79.4%, 80.2% and 79.8% achieved |

### The case study

A simulated 200,000-user checkout redesign with five planted traps and a known true lift of about +3.2%. The naive analysis reports +4.45% (overstated by 40%) because a logging bug drops legacy-Android users from one group. abtrust flags the mismatch, finds the platform responsible, and after the fix estimates +3.30% against a true +3.16%.

> **Be honest about this in interviews and in the README:** the case study is **simulated**. Only the Hillstrom analysis (Step 10) uses real data.

---

## 2. What your laptop needs

Your machine: Ryzen 7 5800H, RTX 3050 4 GB, 16 GB RAM. **That is far more than enough. You do not need RunPod or Colab.**

| Requirement | Needed | Notes |
|---|---|---|
| Python | 3.10 to 3.13 | Check with `python --version` |
| Packages | numpy, scipy, pandas | Installed automatically |
| Plots | matplotlib | Needed for figures; installed with the dev extras, or `pip install matplotlib` |
| Demo app | streamlit | Installed with the `[app]` extra |
| GPU | **Not used** | No CUDA, PyTorch or drivers needed |
| RAM | 4 GB is plenty | See measurements below |
| Disk | Under 100 MB | |
| Internet | Install time, plus once for Step 10 | |

### Measured on a weaker cloud machine (2 cores, 7 GB RAM)

| Job | Peak RAM | Time |
|---|---|---|
| Full validation suite (`abtrust validate`) | 125 MB | 111 s |
| Case study (`python scripts/case_study.py`) | 332 MB | 4 s |

Your 8-core CPU will be as fast or faster.

### Not yet confirmed on your machine

- `pytest` itself could not be installed in the build environment, so the 48 tests were run with a stand-in runner. **Your first real `pytest` run is the true check.**
- The Streamlit app was only tested against a stand-in.
- `scripts/hillstrom.py` has never run against the real download, because the build environment had no internet.

If any of these fail, send me the full error message.

---

## 3. Step-by-step instructions

Run every block from inside the project folder unless told otherwise.

### Step 1: Prerequisites

1. **Python 3.10 to 3.13.** Check with `python --version` (Windows: `py --version`). If it is missing or older, install it from python.org. On Windows, tick **"Add python.exe to PATH"**.
2. **Git.** Check with `git --version`. If missing, install it from git-scm.com.
3. **A terminal:** PowerShell on Windows, Terminal on macOS or Linux.

### Step 2: Unpack the project

Extract `abtrust.zip`, for example to `C:\Projects\` or `~/projects/`, then:

```bash
cd path/to/abtrust
```

List the folder (`dir` on Windows, `ls` elsewhere). You should see `pyproject.toml`, `src`, `tests`, `scripts` and `README.md`. If you only see another folder called `abtrust`, `cd` into that one as well.

### Step 3: Create a virtual environment

This keeps abtrust's packages separate from the rest of your system.

**Windows (PowerShell):**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```
If PowerShell says scripts are disabled, run this once and activate again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now start with `(.venv)`. **Re-activate the environment every time you open a new terminal.**

### Step 4: Install

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
abtrust --version
```

The last command should print `abtrust 0.1.0`. The `-e` flag means code edits take effect immediately.

### Step 5: Run the tests

```bash
pytest
```

**Expected:** `48 passed`. Do not push to GitHub until this is green. Optional lint check (CI runs it too):

```bash
ruff check .
```

### Step 6: Plan an experiment

```bash
abtrust plan --baseline 0.10 --mde 0.05 --relative --daily 20000
```

**Expected:**
```
57,760 control + 57,760 treatment = 115,520 units (MDE=0.005, alpha=0.05, power=80%)
At 20,000 new units/day: 5.8 days (round up to whole weeks).
```

- `--baseline` is your current conversion rate; `--mde` is the smallest lift you care about; `--relative` means the MDE is a percentage of the baseline.
- For a continuous metric such as revenue, use `--sd` instead of `--baseline`.
- If you have a pre-experiment covariate, add `--rho 0.5` (its correlation with the metric) to see how much sample size CUPED saves.

### Step 7: Analyze the sample experiment

The repo includes a 40,000-user simulated experiment. Run this as **one line** (the `\` line breaks in the README only work in bash):

```bash
abtrust analyze data/sample_experiment.csv --arm variant --control control --metric converted:pre_sessions --metric revenue:pre_revenue --metric unsubscribed --ratio orders/sessions --primary converted --guardrail unsubscribed --lower-is-better unsubscribed
```

**Expected:** a Markdown readout with three parts:
1. The sample ratio mismatch check, which must pass before anything else counts.
2. A table of every metric: lift, confidence interval, adjusted p-value and verdict.
3. A final recommendation (SHIP, MIXED, INCONCLUSIVE and so on).

Add `--out reports/my_readout.md` to save it to a file.

**To use your own data**, you need a CSV with one row per user, one column holding the arm label, and one column per metric. In `--metric COLUMN:COVARIATE`, the part after the colon is a pre-experiment column used for CUPED.

### Step 8: Run the case study

```bash
python scripts/case_study.py
```

Takes about 4 seconds. It writes `reports/case_study.md`, `reports/case_study.json`, `reports/case_study_readout.md`, figures in `reports/figures/`, and regenerates `data/sample_experiment.csv`.

### Step 9: Run the validation suite

Quick version first, written to a scratch folder so it cannot overwrite your real reports:

```bash
abtrust validate --scale 0.1 --out scratch_reports
```

Then the full run (about 2 minutes):

```bash
abtrust validate
```

It writes `reports/validation.md` (every README number comes from here), `reports/validation/*.csv`, and the figures.

> **Never commit a `--scale 0.1` run over `reports/`.** It uses far fewer simulations, so its rates are noisier and will not match the README.
>
> If you see a message about matplotlib, run `pip install matplotlib` and run it again.

### Step 10: Run the real-data analysis (most important step)

This needs internet and turns the project from "simulated only" into "validated on real data":

```bash
python scripts/hillstrom.py
```

It downloads the public Hillstrom e-mail experiment (64,000 customers: men's e-mail, women's e-mail, or no e-mail), runs the full workflow, and writes `reports/hillstrom.md`.

Afterwards:
1. Open `reports/hillstrom.md` and read it.
2. Add one sentence with the real result to the README's "Real data" section.
3. If the download fails, send me the error.

### Step 11: Launch the demo app

```bash
pip install -e ".[app]"
streamlit run app/streamlit_app.py
```

Your browser opens at `http://localhost:8501` with three tabs: analyze a CSV, plan a test, and watch peeking fail. Upload `data/sample_experiment.csv` in the analyze tab to try it. Stop the app with `Ctrl+C`.

### Step 12: Push to GitHub

1. On github.com click **New repository**, name it `abtrust`, and leave it **empty** (no README, no license).
2. In the project folder:

```bash
git init
git add .
git commit -m "Initial release: abtrust v0.1.0"
git branch -M main
git remote add origin https://github.com/KingKarim5/abtrust.git
git push -u origin main
```

If git asks who you are, run this once and commit again, using the email attached to your GitHub account (so the commits show on your contribution graph):

```bash
git config --global user.name "MD. Nafiul Haque Nafee"
git config --global user.email "your-github-email@example.com"
```

If the push asks for a password, GitHub needs a personal access token (Settings, Developer settings, Tokens) or a login through the GitHub CLI (`gh auth login`).

3. Open the **Actions** tab. The CI workflow starts by itself and should turn green within a couple of minutes. If it fails, send me the log.
4. Polish the repo page: add a description, add topics (`ab-testing`, `experimentation`, `statistics`, `causal-inference`, `python`), and pin the repo on your profile.

---

## 4. What to expect: output files

| Command | Files produced |
|---|---|
| `abtrust validate` | `reports/validation.md`, `reports/validation/*.csv`, `reports/validation/summary.json`, `reports/figures/*.png` |
| `python scripts/case_study.py` | `reports/case_study.md`, `.json`, `case_study_readout.md`, figures, `data/sample_experiment.csv` |
| `python scripts/hillstrom.py` | `reports/hillstrom.md` |
| `abtrust analyze ... --out X` | `X` (a Markdown readout) |

### Do your numbers have to match the README exactly?

The README numbers come from a full-scale validation run. A full `abtrust validate` should reproduce them, or come very close if the random seeds differ. A `--scale 0.1` run will not match, by design. Rates in `validation.md` come with Monte Carlo standard errors, so small differences are normal.

---

## 5. Repository layout

```
src/abtrust/       library (design, checks, estimators, sequential, multiple, readout, validation, plots, cli)
tests/             48 unit, statistical and smoke tests
scripts/           case_study.py, hillstrom.py
reports/           validation.md, case_study.md, figures/, raw CSV results
docs/methods.md    derivations, assumptions, references
app/               Streamlit demo
data/              sample_experiment.csv (40,000 simulated users)
```

---

## 6. Limitations (say these out loud, they strengthen the project)

- **Normal approximations.** Validated down to 500 users per arm on heavy-tailed revenue. For much smaller tests, use a permutation test.
- **Conservative decision rule.** An SRM blocks all conclusions, any guardrail regression blocks shipping, and Holm correction spans every arm-by-metric comparison.
- **mSPRT assumes a stable population.** Strong weekly seasonality violates this; run whole weeks.
- **Ratio metrics with treatment-affected denominators** (spend per visitor when the treatment changes who visits) are diagnostics, not causal effects.
- **Not covered:** Bayesian analysis, heterogeneous-effect estimation, interference between units (marketplaces, social networks), switchback designs.
- **The headline case study is simulated.** Only the Hillstrom analysis is real data.

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `abtrust: command not found` | The virtual environment is not active. Repeat the Step 3 activation command. |
| `No module named abtrust` | You skipped `pip install -e ".[dev]"`, or ran it outside the project folder. |
| `pip` cannot find a package | Upgrade pip and check your internet connection. |
| PowerShell blocks `Activate.ps1` | Run the `Set-ExecutionPolicy` command from Step 3. |
| `python` opens the Microsoft Store (Windows) | Use `py` instead, or turn off the "App execution aliases" for Python in Windows settings. |
| Streamlit port already in use | Run with `--server.port 8502`. |
| `validate` mentions matplotlib | `pip install matplotlib`, then run again. |
| A test fails | Copy the full error and send it to me. This is the first real `pytest` run. |
| CI fails on GitHub but passes locally | Send me the Actions log; usually a Python-version or lint difference. |

---

## 8. Using it on your profile

- **README first.** It already has the results table, the case study and the peeking figure. Add the real Hillstrom result after Step 10.
- **One-line description for the repo and your CV:** *"abtrust: A/B-test analysis toolkit (SRM, CUPED, delta-method ratio metrics, always-valid sequential tests, multiple-testing control), with a Monte Carlo suite that validates each method against known ground truth."*
- **Interview talking points:** why checking results daily inflates false positives from 5% to 38%, how CUPED buys power for free, why per-session analysis understates uncertainty, and why an SRM must be fixed before reading any result.
- **Keep it honest.** Say the case study is simulated, say what the validation shows (and its power cost for always-valid tests), and show the limitations above.

---

*Author: MD. Nafiul Haque Nafee (BRAC University, CSE). Licence: MIT.*
