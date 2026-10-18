# abtrust v0.2.0 — Windows / VS Code run guide

This guide is for your **Windows laptop** and existing project under `D:\Programming\abtrust`. All commands below are **PowerShell commands**, entered in the **VS Code terminal**. Python 3.10–3.13 is supported. The CPU is sufficient; your NVIDIA GPU is not needed.

## 0. What changed in this release

- Safer experiment conclusions: without guardrails or without predeclared acceptable harm margins, a significant primary effect produces **REVIEW REQUIRED**, not automatic **SHIP**. Passing a screen is **not** authorization to deploy.
- Guardrail safety now includes a conservative Bonferroni upper confidence bound on **absolute harm**. A nonsignificant regression does not imply safety.
- Optional `unit_col` verifies there is one row per randomized user; missingness is reported by arm and decisions are blocked if missingness or its imbalance exceeds the configured threshold (default **1%**). Supply user IDs when available.
- 95% displayed confidence intervals are labelled as **unadjusted**; Holm/BH corrections apply to p-values. Separate relative-effect CIs can straddle zero differently owing to approximation differences.
- Sequential analysis distinguishes **working-normal mSPRT (approximation only)**, **bounded [0,1] Hoeffding confidence sequences** (time-uniform under stated assumptions), and **Gaussian-known-SD mixture testing** (known variance, equal arm sample sizes, prespecified `tau`). The previous 1.6% simulation result is NOT an exact error guarantee.
- The Hillstrom script now generates a direct **Men's E-Mail vs Women's E-Mail** comparison, not only each treatment vs control.
- The simulation plots and reports are regenerated; tests include additional edge cases.

## 1. Back up your working version

You can keep the old version rather than overwrite anything:

1. Close the old Streamlit server from its terminal with `Ctrl+C`.
2. In File Explorer, rename `D:\Programming\abtrust` to `D:\Programming\abtrust-old` (or copy that folder somewhere safe).
3. Extract the **new ZIP** into `D:\Programming\`. It contains a top-level `abtrust` folder. You should end up with `D:\Programming\abtrust\pyproject.toml`, plus `src`, `app`, `scripts`, `tests`, `data`, `docs`, and `reports`.
4. **Do not copy the old `.venv` folder.** Create a new environment for the new version.

> If you already have Git changes or personal datasets, back them up separately before renaming the old directory. `data/hillstrom.csv` might be cached in your old copy; if present, you can copy that **CSV only** to the new project's `data` folder to avoid another download.

## 2. Open in VS Code

1. In VS Code select **File → Open Folder** and choose `D:\Programming\abtrust`.
2. Select **Terminal → New Terminal**. Confirm you are inside the extracted folder:

```powershell
cd D:\Programming\abtrust
Get-ChildItem pyproject.toml
```

## 3. Create and activate the virtual environment

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell refuses to activate it, run **for this terminal session only**:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Expected prompt: `(.venv) PS D:\Programming\abtrust>`.

If `py -3.10` is unavailable, check `py -0p` for installed Python versions. You may use any Python 3.10–3.13 installation; for example, `py -3.11 -m venv .venv`.

## 4. Install the package and select Python

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev,app]"
abtrust --version
```

Expected version: **`abtrust 0.2.0`**.

In VS Code press `Ctrl+Shift+P` → **Python: Select Interpreter** → select `D:\Programming\abtrust\.venv\Scripts\python.exe`. Always run from the project root using this environment, not from the global Python interpreter.

## 5. Verify everything

Run each command separately. Avoid pasting lines beginning with `>>` from terminal screenshots; that indicates continuation mode.

```powershell
python -m pytest
ruff check .
```

The revised test suite currently has **55 passing tests** in the build environment. The new version still needs verification on your laptop. For a quick working test:

```powershell
python scripts/case_study.py
```

Expected files: `reports/case_study.md`, `reports/case_study_readout.md`, and `reports/figures/case_forest.png` and `case_peeking.png`.

**Important:** The fixed case study may now say `REVIEW REQUIRED - ... guardrail harm margins missing`. This is the intended safer behavior, **not an error**. The example does not assume that a statistically nonsignificant guardrail change is safe.

## 6. Reproduce the validation studies

Run a quick validation into a scratch folder first so you do not replace full-size reports:

```powershell
abtrust validate --scale 0.1 --out scratch_reports
```

Then reproduce the complete validation suite, which takes longer:

```powershell
abtrust validate
```

The full command writes `reports/validation.md`, CSV results in `reports/validation/`, and PNG figures in `reports/figures/`. Rates vary slightly by Monte Carlo simulation; quick `--scale 0.1` results are noisy and should **not** replace full results in your README.

Note the new `peeking` study displays three approaches: naive repeated tests, *working-normal approximate* mSPRT, and *bounded, time-uniform* Hoeffding confidence sequences. The exact bounds can be conservative.

## 7. Run the real Hillstrom experiment

```powershell
python scripts/hillstrom.py
```

It downloads (or reuses cached) data and writes `reports/hillstrom.md`. In addition to the original treatment-vs-control results, the updated report contains a **direct men's versus women's email comparison**. Do not declare one message superior based only on their separate lifts against control.

If the download is blocked, use a legitimate local copy of the original public CSV:

```powershell
python scripts/hillstrom.py --csv data/hillstrom.csv
```

## 8. Start the dashboard

```powershell
python -m streamlit run app/streamlit_app.py
```

Open <http://localhost:8501> in your browser. To stop it, return to VS Code terminal and press `Ctrl+C`.

In **Analyze an experiment**: select the dataset, arm column, control group, unique user ID (if available), metrics, primary metric, guardrails, and any predeclared acceptable absolute harm margins. You must add guardrail columns into the **Metrics (per-user columns)** multiselect before they can be selected as guardrails. The text input for each margin is **blank by default**: you must choose it before examining outcomes, based on the product's acceptable risk. The new data quality threshold defaults to 1%.

In **Why peeking fails**, compare bounded Hoeffding (rigorous for independent binary outcomes) against the working-normal mSPRT (exploratory approximation). Don't confuse them.

## 9. Analyze the included CSV from the command line

This is a single line in PowerShell:

```powershell
abtrust analyze data/sample_experiment.csv --arm variant --control control --unit user_id --metric converted:pre_sessions --primary converted --metric revenue:pre_revenue --metric unsubscribed --guardrail unsubscribed --lower-is-better unsubscribed --ratio orders/sessions --out reports/my_readout.md
```

With no predeclared safety limit, the readout should caution **REVIEW REQUIRED** even if conversion improves. To pass a prespecified absolute harm tolerance, **only if the tolerance was decided independently of the outcomes**, append the appropriate argument, such as:

```powershell
--guardrail-max-harm unsubscribed=0.001
```

That number is **an example of CLI syntax**, not a recommendation for any particular business. The parameter expresses an **absolute** rate difference, not a relative percent increase. A limit of `0.001` means at most a 0.1 percentage-point absolute increase in the harm metric.

## 10. Sequential analysis in Python

For **independent per-user binary outcomes** (0 or 1) in chronological arrival order:

```python
from abtrust import sequential_test

result = sequential_test(control_binary, treatment_binary, looks=14, mode="bounded")
print(result.guarantee_note)
print(result.stop_index, result.final.p_value)
```

For normal observations with **truly known standard deviations**, equal sample counts, and a **mixing scale fixed before observing experimental data**:

```python
from abtrust import sequential_test, tau_from_design

planned_n_per_arm = 5000
prespecified_tau = tau_from_design(sd=1.0, n_per_arm=planned_n_per_arm)
result = sequential_test(control_normal, treatment_normal, looks=14,
                         mode="gaussian_known_sd", known_sd=1.0,
                         tau=prespecified_tau)
```

**Do not use the default `mode="working_normal"` as a guaranteed anytime-valid test.** It remains available to reproduce the original simulated experiments, but its estimated-variance likelihood ratio is not proven to satisfy the exact martingale conditions.

## 11. Where to find the results

| File | Purpose |
|---|---|
| `reports/case_study.md` | Simulated checkout redesign and planted traps |
| `reports/case_study_readout.md` | Detailed 17-comparison readout and new guardrail-safety section |
| `reports/validation.md` | Full Monte Carlo evidence with limitations |
| `reports/hillstrom.md` | Real public dataset analysis; regenerated by Step 7 |
| `reports/figures/*.png` | Figures for documentation and portfolio |
| `docs/methods.md` | Statistical assumptions, formulas, and what is/ isn't proven |
| `CHANGELOG-v0.2.md` | Specific changes versus v0.1.0 |

## 12. Troubleshooting

| Error or issue | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'abtrust'` | Activate `.venv` and rerun `python -m pip install -e ".[dev,app]"` from project root. |
| `Activate.ps1 cannot be loaded` | Use `Set-ExecutionPolicy -Scope Process Bypass` in that terminal, then reactivate. |
| `abtrust --version` still says `0.1.0` | You are likely using the old environment/interpreter. Check `Get-Command abtrust` and reselect `.venv`. |
| `REVIEW REQUIRED` shown | Intended: configure and justify guardrail margins, check missingness and unique users. Do not disable checks just to force a green status. |
| Hillstrom download fails | Copy `data/hillstrom.csv` from your original project if available, then `python scripts/hillstrom.py --csv data/hillstrom.csv`. |
| Dashboard port 8501 already used | Stop the old Streamlit process or run `python -m streamlit run app/streamlit_app.py --server.port 8502`. |
| VS Code Run button gives import errors | Use the integrated terminal commands and select the venv interpreter. |
| Full validation is slow | Let it run. Use `--scale 0.1 --out scratch_reports` for a quick smoke check only. |

## 13. Before publishing to GitHub

- Confirm **55 tests** pass locally and no lint errors remain.
- Run full validation on your machine and regenerate all figures; do not publish quick-scale Monte Carlo rates as full-scale results.
- Run the actual Hillstrom analysis locally (the build environment cannot access the dataset download reliably).
- Ensure README and figures explicitly distinguish the old **working-normal approximate mSPRT** from methods with stated time-uniform assumptions.
- Discuss guardrail harm limits with domain experts; a statistical screen is not an automatic deployment approval.
- Push your revised files only after reviewing `git diff` and updating the GitHub README.
