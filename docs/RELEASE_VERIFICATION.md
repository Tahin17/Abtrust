# abtrust 0.3.0 — Verification results

Updated **19 October 2026 (Asia/Dhaka)**. These are observed local results; older 83/88-test notes are historical.

## Environment and reproducibility

A new `.venv_verify` installed `.[dev,app]` from this checkout using Python **3.10.11** on Windows. The exact installed versions are saved in `requirements-verified-windows.txt`: NumPy 2.2.6, SciPy 1.15.3, pandas 2.3.3, matplotlib 3.10.9, Streamlit 1.65.0, pytest 9.1.1 and Ruff 0.17.1. BLAS/OpenMP thread counts were limited to one. Real Streamlit checks needed execution outside the managed socket-restricted sandbox.

Run the complete workflow from the repository root:

```powershell
.\.venv_verify\Scripts\python.exe scripts/verify.py --integration --full
```

It regenerates the full-budget reports and records command exit codes in [execution.json](../reports/verification/execution.json). The cached Hillstrom file is used only when present. See [reproducibility instructions](REPRODUCIBILITY.md) for fresh setup, individual commands, manifests and render-only operation.

## Completed checks

| Check | Observed result |
|---|---|
| Fresh-environment full workflow | Every command exited zero; `all_checks_passed: true` |
| Final pytest including actual Streamlit AppTest | **122 passed in 35.49 seconds** |
| Default pytest behavior | 121 tests plus one intentionally opt-in Streamlit test |
| Ruff | All checks passed |
| Core Monte Carlo validation | All **seven full-budget studies** completed |
| Supplemental stress validation | Two studies, **2,000 replications per cell**, completed separately from core results |
| Synthetic checkout | 200,000 randomized users, figures, readouts and simulation provenance regenerated |
| Cached real Hillstrom experiment | 64,000 customers analyzed; explicitly labelled real data; REVIEW REQUIRED |
| CLI version/planning | v0.3.0; conversion example 57,760 per arm, 115,520 total, 5.8 days |
| Render-only operation | Core CSVs and simulation manifest remained byte-for-byte unchanged; core and stress presentations rebuilt |

[Render integrity evidence](../reports/verification/render-integrity.json) records the saved-file comparison. Simulation manifests contain actual replication counts, seeds, design parameters, file hashes and source/runtime provenance. Rendering has its own timestamp. Analysis sidecars identify generated simulation, real data or user-supplied data. A checksum detects later changes; it does not prove the statistical assumptions.

Git history now exists: baseline `2f959bd` on `main`, remote `Tahin17/Abtrust`. Execution manifests truthfully record that baseline plus a dirty working tree/source hash at run time. Remote GitHub Actions and other Python/OS combinations were **not executed locally**. The expanded CI matrix requires a later push.

## Browser acceptance

The dashboard ran at localhost port 8510. Verified interactions include:

- Built-in sample table, plot, SRM pass and conservative decision; 90% confidence label after changing alpha.
- Actual synthetic 20/80 CSV upload: SRM fails under 50/50 and passes under its predeclared 20/80 design.
- Actual duplicate-ID upload: rejected with a one-row-per-randomized-unit error.
- Actual one-column upload: readable arm/outcome schema error.
- Invalid custom allocations (40/40 total and zero percentage); invalid harm margins (`abc`, `-1`, `nan`).
- Blank guardrail margins produce REVIEW REQUIRED; zero margins do not establish safety.
- Higher-is-better direction: downloaded harm bound 0.001867 matched an independent core calculation.
- Planner rejects an impossible 108% conversion rate and recovers to a valid plan.
- Both peeking demonstration modes and their caveats; actual Markdown downloads checked.

Evidence: [browser record](../reports/verification/browser.json), [20/80 upload screenshot](../reports/verification/upload-20-80.png), [duplicate-ID screenshot](../reports/verification/upload-duplicate-id.png), [planner screenshot](../reports/verification/planner-validation.png).

**Remaining browser-only acceptance:** uploaded empty file, missing arm labels, missing/infinite outcomes, and uploaded public sample CSV. Automated tests cover these validation paths, but that does not substitute for browser acceptance. Browser file transfers took minutes despite short timeouts. The [dashboard checklist](DASHBOARD_QA.md) preserves partial checks rather than marking whole groups complete.

## Statistical findings and limits

- All Monte Carlo and checkout results are **simulations**, limited to their stated conditions. Hillstrom is real randomized experimental data.
- The rare binary stress scenario (400 per arm, baseline probability 0.002, true difference 0.001) achieved only **84.75% coverage** for a nominal 95% Welch interval over 2,000 replications. This sparse-event approximation is unreliable in that setting. Monte Carlo standard error for coverage was about 0.80 percentage points.
- Deliberately removing low treatment outcomes produces near-certain false rejection. Those rows are marked **invalid selection** and demonstrate assumption failure, not estimator performance on valid randomization.
- Correlated covariates, unequal allocation and constant fixtures completed; constants are deterministic checks, not Monte Carlo accuracy evidence.
- Known-Gaussian sequential null rejection rates were 0.15%, 1.05% and 1.30% at 1, 20 and 100 looks in the tested configuration. These simulations do not establish validity outside the stated Gaussian, known-variance assumptions.
- Working-normal mSPRT remains exploratory. It has no newly claimed anytime-valid guarantee. Bounded methods retain their explicit bounds and error-spending assumptions.
- Corrected core bounded power at twice the MDE is 78.8% at one look versus 0.23% at 100 looks. Many-look conservatism is a real limitation of that design.
- The simulated checkout still returns REVIEW REQUIRED because guardrail harm margins were not declared. Hillstrom lacks documented original unit IDs and configured safety outcomes, so also remains REVIEW REQUIRED.
- Ordinary confidence intervals remain unadjusted; Holm/BH p-value corrections and conservative guardrail bounds are separate quantities.

## Distribution verification

The isolated build produced a source archive and a platform-independent wheel. The wheel installed into a separate core-only environment. From a temporary directory outside the repository, imports resolved to that environment; bounded sequential inference, CLI version, planning, a small SRM simulation and render-only operation all completed successfully. Source archive content and artifact hashes are recorded in [distribution.json](../reports/verification/distribution.json). Git attributes preserve exact result bytes across checkout platforms. No package has been published and no remote CI result is claimed.
