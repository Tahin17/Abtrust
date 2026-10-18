# Reproducing abtrust results

Git attributes preserve CSV and JSON result bytes across Windows and Linux checkouts, so automatic line-ending conversion does not invalidate saved checksums.

All commands below run from the repository root after installing `.[dev,app]`. The library/CLI wheel can run without a checkout, but the dashboard, sample CSV, scripts and this documentation require the checkout or source archive.

## Run the local checks

```powershell
.\.venv_verify\Scripts\python.exe scripts/verify.py --integration --full
```

This runs Ruff, all tests with real Streamlit AppTest enabled, the version/planning CLI examples, all seven full-budget core studies, two supplemental stress studies, the simulated checkout, and the real Hillstrom analysis if its cached CSV exists. It saves command exit codes and UTC timestamps to `reports/verification/execution.json`. It uses one numerical-library thread to limit memory use. A missing real-data cache is recorded as `real_data_run: false`; it is not silently replaced with synthetic data.

Without `--full`, quick simulation output goes to ignored `scratch_reports/`, leaving the authoritative full-budget reports alone. The `--integration` option requires the app dependencies and functioning local sockets.

## Core versus supplemental simulations

```powershell
abtrust validate
abtrust stress --simulations 2000
```

The seven original studies write to `reports/`. The two supplemental studies write to `reports/stress/`. Both are synthetic Monte Carlo evidence. The supplemental selection scenario deliberately removes low treatment outcomes; its high rejection rate demonstrates violated assumptions, not a successful estimator. The deterministic fixture uses an exactly representable effect of 0.125 to separate floating-point rounding from statistical behavior.

For a development run:

```powershell
abtrust validate --scale 0.05 --out scratch_reports/core --no-figures
abtrust stress --simulations 50 --out scratch_reports/stress
```

Do not present these smaller simulation budgets as the published full-budget evidence.

## Provenance and immutable rendering

Each study's `validation/summary.json` records the seed, actual replication budget, function parameters, scenario configuration, Python/dependency versions, Git commit/dirty status, Python-source hash, implementation hash, and CSV checksum. UTC run timestamps are stored per study. A dirty working tree is explicitly identified; the source hash identifies the actual Python files at that point rather than claiming an uncommitted run used a clean release.

```powershell
abtrust render --out reports
abtrust render --out reports/stress --no-figures
```

Rendering verifies saved CSV checksums, updates Markdown/figures and `validation/rendering.json`, and leaves CSV bytes and `validation/summary.json` unchanged. The rendering record has its own timestamp, runtime information and simulation-manifest hash. A checksum mismatch stops rendering so altered raw results cannot be silently treated as the original run.

`abtrust analyze ... --out readout.md` also writes `readout.manifest.json`. The CLI labels arbitrary inputs `user_supplied`: it cannot infer that a CSV contains real randomized observations. The Hillstrom script explicitly labels its cached dataset `real_data`; the checkout script labels its generated data `simulation`. Dataset manifests contain a filename and checksum rather than a private absolute path. Neither a checksum nor a unique-ID check proves the source experiment was correctly randomized or logged.

## Browser fixtures

```powershell
python scripts/dashboard_fixtures.py
```

The ignored `scratch_qa/` directory contains a synthetic 20/80 fixture and deliberate errors: duplicate IDs, missing arm labels, excessive missing outcomes, infinity, an empty file and a one-column file. The valid fixture is designed 20/80; enter those planned percentages in the dashboard. These files are software acceptance fixtures, not a new business experiment. See `docs/DASHBOARD_QA.md` for observed browser checks.

## Distribution checks

Build with `python -m build` in the verification environment. `MANIFEST.in` includes the dashboard, scripts, documentation, public simulated sample and saved reports in the source archive. It excludes virtual environments and does not include cached `data/hillstrom.csv`. The wheel contains the Python library and CLI, not a self-contained dashboard deployment.

The package retains version 0.3.0 during this local development work. Publishing, version tags, remote CI execution and any future statistical feature require a separate release step. The Windows/Linux CI matrix is configured, but configuration is not evidence that an unpushed revision passed GitHub Actions.
