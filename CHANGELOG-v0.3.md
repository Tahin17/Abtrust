# Changelog — abtrust v0.3.0

## Post-review corrections — 18 October 2026

- Bounded sequential validation now calls the actual bounded API separately for each monitoring schedule. Each schedule spends its error budget from its own first look; smaller schedules no longer inherit the 100-look weights.
- The sample-size dashboard displays an actionable error when the baseline and relative MDE imply a treatment rate of 100% or more, and the other tabs continue working.
- The dashboard confidence-level caption follows the selected analysis alpha.
- Power-calibration reports show the replication count for each design, including the smaller revenue simulation budget.
- Markdown and JSON report writers explicitly use UTF-8 on Windows; regression cases include accented text and punctuation.
- The simulated checkout readouts verify the generated original `user_id` column. Missing guardrail margins still prevent a safety-cleared decision.
- Regression tests cover the schedule mismatch, planner recovery and confidence labels; the real Streamlit smoke test exercises the changed controls.
- `.venv_v03/` is excluded from version control. Current local verification is recorded in `docs/RELEASE_VERIFICATION.md`.

## Implemented

- **Planned split in dashboard:** equal splits or custom allocation percentages per arm; strict validation (finite, positive, total 100%). The SRM check now uses the *design*, not the observed sample proportions.
- **Safer CSV ingestion:** upload size and row limits; errors for empty/malformed CSV; arm-label checks; nonnumeric and nonfinite outcome rejection; missingness and duplicate IDs are still assessed by the core readout.
- **Guardrail interface:** options for lower-is-better versus higher-is-better, predeclared absolute harm margins, clear validation errors and no silent auto-ship when safety is unknown.
- **Clearer reporting:** absolute estimates and CIs, relative estimates and CIs, per-arm effective sample sizes, adjusted p-values and explicit conservative harm bounds in the Streamlit table.
- **Hillstrom provenance:** optional recognized source `user_id`/`customer_id` checked when present; otherwise no fabricated IDs. No guarantee of messaging safety in absence of guardrail outcomes. Direct pairwise family described as exploratory and separate from the two treatment-vs-control families. Subgroup tests explicitly not interaction tests.
- **SRM safety:** validates finite observed counts, designed weights and threshold inputs.
- **Testing:** new pure-helper tests, malformed upload tests, custom allocation UI-stub tests, invalid harm-margin tests, nonfinite outcome tests, and an **optional actual-Streamlit AppTest** in a separate GitHub Actions job.
- **Packaging:** excludes local Windows virtual environments and downloaded CSV cache; refreshed guide and documentation; source and tested reports included.

## Verification

- Offline review: **83 tests passed, 1 optional Streamlit AppTest skipped** without the Streamlit dependency.
- Reproduced the simulated case study and reran the Hillstrom analysis from the original cached CSV provided by the user.
- Reran the full Monte Carlo validation after these changes.
- **Not verified here:** Ruff (not installed in this offline environment), real Streamlit AppTest or live browser interactions. Those checks are documented for the user's machine and CI.

## Remaining scientific limitations (intentional)

- Simulations are evidence under simulated assumptions, not general proofs.
- Plug-in working-normal sequential inference remains approximate, explicitly labeled as such.
- Hillstrom has neither documented source IDs nor safety guardrail outcomes; `REVIEW REQUIRED` is the correct conclusion.
- Any safety screen relies on context-specific predeclared harm tolerances; it is never deployment authorization.
