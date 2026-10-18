# abtrust 0.3.0 — Verification results

Updated **18 October 2026 (Asia/Dhaka)** after the repository review and corrections. This supersedes the earlier offline-release verification notes.

## Environment

Windows, Python **3.10.11**, existing `.venv_v03`, with imports resolving to this checkout's `src/abtrust`.

| Dependency | Version |
|---|---|
| numpy | 2.2.6 |
| scipy | 1.15.3 |
| pandas | 2.3.3 |
| matplotlib | 3.10.9 |
| streamlit | 1.65.0 |
| pytest | 9.1.1 |
| Ruff | 0.17.1 |

The successful full verification used `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, and `MKL_NUM_THREADS=1` to limit memory use. The managed sandbox hung while Python created a local event-loop socket, before Streamlit executed the app; actual Streamlit checks succeeded outside that sandbox.

## Completed checks

| Check | Observed result |
|---|---|
| Full pytest with `ABTRUST_RUN_STREAMLIT_INTEGRATION=1` | **88 passed in 23.64 seconds** in the final run, including the real Streamlit test |
| `ruff check . --no-cache` | **All checks passed** |
| `python -m abtrust.cli validate` | All **seven full-budget studies** completed; Markdown, seven CSVs, metadata and four validation figures regenerated |
| `python scripts/case_study.py` | Completed; simulated checkout reports, two figures and 40,000-user sample regenerated; original generated unit IDs verified |
| `python scripts/hillstrom.py --csv data/hillstrom.csv` | Completed using the existing real-data cache; report regenerated; **REVIEW REQUIRED** |
| CLI version and planning examples | v0.3.0; conversion example returns **57,760 per arm**, 115,520 total, 5.8 days; continuous/CUPED planning example completed |
| CLI sample CSV analysis | Five comparisons, Holm correction, Markdown output and missing-guardrail-margin decision checked |

The four new regression tests were first run against the previous implementation and failed on the intended bugs, then passed after the corrections. The real Streamlit test now also changes analysis alpha, exercises invalid planner inputs, and verifies recovery to a valid plan. Without the opt-in environment variable, expect **87 passed, 1 skipped**.

Additional Unicode cases reproduced the Windows legacy-encoding problem in the CLI and validation report. Report writers now explicitly use UTF-8, and the saved validation report was rendered again from the completed full-budget CSVs without rerunning or reducing the simulations.

## Browser acceptance

The actual dashboard ran at `http://127.0.0.1:8510` in the in-app browser. Verified through browser interactions:

- Sample table, equal-allocation SRM pass, conservative decision, result table, and plot rendered.
- Analysis alpha 0.10 displayed **90%** confidence intervals in the caption.
- Custom 40/40 allocation was rejected with an 80%-total error.
- A nonnumeric guardrail harm margin was rejected.
- Baseline 0.90 and relative MDE 0.20 displayed the implied **108%** rate as a readable error; restoring 0.10/0.05 restored the 57,760-per-arm plan.
- Both peeking modes ran for 400 simulated experiments at 20 looks. Naive false positives were 26.5%; bounded 0.0%; working-normal 1.0%, with the approximation warning visible. These are demonstration simulations, distinct from the full validation suite.
- The Markdown download completed; its actual downloaded contents included the decision, SRM result, five-comparison results and guardrail notes.

Screenshot: [planner validation](../reports/verification/planner-validation.png).

**Still unverified through the browser:** CSV file uploads and upload-dependent cases. The browser automation's file chooser timed out, including a retry through the actual file input. Automated helper and UI-stub tests passed for valid CSVs, malformed files, custom 20/80 allocation, missing arm labels, duplicate unit IDs, and invalid numerical outcomes. These tests do not substitute for a completed browser file selection. The remaining manual cases are listed in [DASHBOARD_QA.md](DASHBOARD_QA.md).

Remote GitHub Actions and Python versions other than the local 3.10.11 were not executed in this session. This extracted folder has no `.git` directory; commit history was not reconstructed.

## Corrected simulation interpretation

Each bounded monitoring schedule now calls `sequential_test(..., looks=k, mode="bounded")`, spending its error budget from that schedule's own first look. Previous rows for fewer than 100 looks incorrectly inherited the 100-look weights.

At twice the MDE, the corrected bounded procedure detected the effect in **78.8%** of simulations with one look, versus **0.23%** with 100 looks. The many-look procedure remains conservative in this scenario. The existing 100-look headline results, including 38.1% naive and 1.6% working-normal false positives, were reproduced. The power-calibration report now shows the actual **500** revenue replications alongside the two **2,000**-replication designs.

## Scientific qualifications

- All Monte Carlo and checkout results are **simulations**, with conclusions limited to their tested conditions.
- The working-normal mSPRT remains exploratory, not proved anytime-valid; the other modes retain their stated assumptions.
- The simulated checkout still returns `REVIEW REQUIRED` because guardrail harm margins are missing.
- Hillstrom is real randomized experimental data, but lacks documented original unit IDs and configured safety outcomes; it remains `REVIEW REQUIRED`.
- Ordinary intervals remain unadjusted; p-value corrections and conservative guardrail bounds remain separate.
