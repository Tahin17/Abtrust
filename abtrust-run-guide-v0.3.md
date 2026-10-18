# abtrust v0.3.0 — Windows / VS Code Run & Verification Guide

This guide applies to **abtrust v0.3.0**, which adds configurable planned allocations, safer Streamlit inputs, strengthened CSV checks, and more explicit Hillstrom caveats.

## 1. Historical ZIP upgrade instructions

The current checkout already contains these changes and has Git history. **Do not rename or replace it to run verification.** Continue with section 2 using the existing environment, or use the clean `.venv_verify` created during verification. See `docs/REPRODUCIBILITY.md` for the current workflow.

The following steps apply only when upgrading an older extracted copy:

1. In VS Code, press **Ctrl+C** in the terminal running the Streamlit app.
2. In File Explorer, rename `D:\Programming\abtrust` to `D:\Programming\abtrust-v0.2-backup`.
3. Extract `abtrust-v0.3.0-improved.zip` into `D:\Programming\`, so the new location is `D:\Programming\abtrust` and it contains `pyproject.toml`, `app`, `scripts`, `src`, and `tests` directly.
4. Open the new folder in **VS Code → File → Open Folder**. Do not copy the old `.venv`; recreate it below.

## 2. Set up Python in Windows PowerShell

Use Python 3.10–3.13 (3.10 is the version used in your screenshots).

If your existing `.venv_v03` works, keep using it rather than recreating an active environment:

```powershell
cd D:\Programming\abtrust
.\.venv_v03\Scripts\Activate.ps1
```

The following setup is for a **new** environment only. If `.venv` already exists or its executable is locked, choose an unused environment name.

```powershell
cd D:\Programming\abtrust
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,app]"
```

If execution is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` once in that terminal, then activate again. In VS Code, choose the interpreter `.venv\Scripts\python.exe` using **Ctrl+Shift+P → Python: Select Interpreter**.

## 3. Verify the code

```powershell
abtrust --version
ruff check .
python -m pytest
```

Expected version: **0.3.0**. On 19 October, **122 tests passed with the actual Streamlit AppTest enabled** in a fresh Windows/Python 3.10.11 environment. Without the opt-in variable, expect **121 passed, 1 skipped**. See `docs/RELEASE_VERIFICATION.md` for the current environment and remaining limits.

The extra AppTest requires the installed app dependency and can be run with:

```powershell
$env:ABTRUST_RUN_STREAMLIT_INTEGRATION="1"
python -m pytest -q tests/test_streamlit_integration.py
Remove-Item Env:\ABTRUST_RUN_STREAMLIT_INTEGRATION
```

This automated UI smoke test is also included as a **separate GitHub Actions job**. It is a supplement, not a substitute for checking the browser interactions.

The complete full-budget workflow is also available as one command (allow several minutes):

```powershell
.\.venv_verify\Scripts\python.exe scripts/verify.py --integration --full
```

## 4. Reproduce the reports

```powershell
python scripts/case_study.py
abtrust validate
python scripts/hillstrom.py
```

Files appear under `reports\`. `hillstrom.py` downloads its original 64,000-row dataset if `data\hillstrom.csv` is absent. You can alternatively pass your own copy with `--csv`.

The reported **REVIEW REQUIRED** Hillstrom outcome is intentional. The public dataset lacks a verified original customer ID and configured harm guardrails, so positive visit/conversion results alone do not authorize sending the campaign.

## 5. Launch and exercise the dashboard

```powershell
python -m streamlit run app/streamlit_app.py
```

Open the **Local URL printed by Streamlit** (usually `http://localhost:8501`; another port may be used if occupied). In **Analyze an experiment**:

1. Choose **Sample experiment**. You should see the readout, SRM result, plot, and **Download readout (Markdown)** button.
2. Choose **Equal split** if the experiment was designed to allocate equal percentages. For unequal designs, select **Custom allocation (%)** and enter the percentages planned before collecting data (for example, 20 for control, 80 for treatment). They must total 100%.
3. Choose a **unique randomized unit ID**, usually `user_id`. Do not manufacture row numbers to pretend the original data includes IDs.
4. Select a **primary metric** and optionally **guardrails**. For each guardrail set the desired direction (lower/higher) and a **predeclared maximum acceptable absolute harm**. Blank means *safety not assessed*, not zero harm.
5. **Missing fraction** is the tolerated missing-data rate or imbalance per arm. The app blocks analysis when input validation fails.
6. Read the label above the results: Holm/BH adjusts the **p-values**, not the displayed **unadjusted confidence intervals**. Guardrail harm bounds are Bonferroni-adjusted separately.
7. Try **Upload a CSV** with a correctly formatted file. You can upload `data\sample_experiment.csv` itself. Try a missing/incorrect column to see readable error feedback rather than a full stack trace.
8. In **Plan sample size**, try baseline 0.10, relative MDE 0.05, alpha 0.05, and power 0.80. A baseline/MDE combination implying a treatment rate of 100% or more displays an error until corrected. In **Why peeking fails**, compare the bounded Hoeffding procedure and working-normal approximation. Do not treat the latter as a formal anytime-valid guarantee.

A detailed [manual test checklist](docs/DASHBOARD_QA.md) is included.

## 6. Useful commands

| Command | Meaning |
|---|---|
| `abtrust --version` | Show installed project version |
| `ruff check .` | Lint your source code |
| `python -m pytest` | Run automated tests |
| `abtrust validate --scale 0.1 --out scratch_reports` | Quick validation, without overwriting full reports |
| `abtrust validate` | Full-scale Monte Carlo validation |
| `python scripts/case_study.py` | Simulated 200,000-user checkout case study |
| `python scripts/hillstrom.py` | Real-data 64,000-customer email experiment |
| `python -m streamlit run app/streamlit_app.py` | Launch interactive dashboard |

## 7. Scope and honest claims

- The checkout case study is **synthetic**. The Hillstrom data is a **public real-world randomized experiment**.
- The **working-normal mSPRT** is exploratory; its observed false-positive rate in simulations is not a mathematical anytime-valid guarantee.
- The **bounded Hoeffding** mode has explicitly stated assumptions and can be very conservative. Do not confuse a test passing with adequate power.
- `SHIP CANDIDATE (review required)` means configured statistical screens passed, **not** approval to release a product.
- The Hillstrom file has no stable documented original user IDs; its integrity at the original-unit level cannot be independently checked from the public CSV.
- The **actual Streamlit browser** must be tried on your laptop. This ZIP contains tests, including a CI AppTest, but our offline environment could not run the live browser interface.

## 8. GitHub publication

Keep source, documentation, tests, and generated reports. Exclude `.venv`, `.venv_v03`, `.pytest_cache`, `.ruff_cache`, `__pycache__`, and `data/hillstrom.csv` from commits and release archives. Keep `.git` locally for version history but exclude it from release ZIPs. Run `ruff check .` and `python -m pytest` again before publishing. The `.gitignore` covers the usual generated files.
