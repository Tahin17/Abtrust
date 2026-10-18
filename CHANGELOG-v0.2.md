# abtrust v0.2.0 — Change log

- **Safety-oriented decisions**: No automatic SHIP without a configured primary metric and guardrails, explicitly chosen pre-experiment absolute harm margins, conservative multiplicity-aware harm bounds, nonproblematic missingness, and verified unique randomization-unit IDs. Always label potential SHIP as requiring further review.
- **Data quality**: optional `unit_col` uniqueness check; missing-outcome rates by arm, thresholded blockers, and clearer notes. Duplicate metric names rejected.
- **Reporting**: unadjusted confidence intervals explicitly distinguished from Holm/BH-adjusted p-values; a guardrail safety table added; absolute and relative interval approximation differences documented.
- **Sequential inference**: retained original plug-in mSPRT as `working_normal` for empirical reproducibility but removed unproven exact anytime-valid claims. Added `bounded` Hoeffding confidence sequence for independent [0,1] outcomes, and `gaussian_known_sd` for independent Gaussian equal-size arms with known SD and prespecified tau.
- **Simulation study**: added bounded Hoeffding comparison to sequential-validation data and figure; the mSPRT is explicitly identified as approximate.
- **Hillstrom**: added direct men's vs women's email analysis with Holm adjustment to avoid inferring direct superiority merely from different control lifts.
- **Demo**: configurable user ID, guardrails, predeclared harm margins, missingness threshold, and explicit bounded-vs-approximate sequential demonstration; Streamlit layout calls updated away from deprecated `use_container_width`.
- **Testing**: original 48 tests plus 7 new regression/safety tests, 55 passing in the build environment.

## Deliberate limitations

- The v0.1.0 simulation figures for mSPRT demonstrated empirical behavior only; they never constituted a mathematical proof.
- New bounded Hoeffding confidence sequences are often conservative; they apply to independent bounded user-level outcomes with a stable underlying expectation, not arbitrary correlated, clustered, or drifting streams.
- Exact Gaussian-known-SD mode requires its mathematical assumptions to hold; it is *not* a convenient default for generic outcomes with sample-estimated variance.
- A missing or nonsignificant guardrail effect does not prove safety. Harm-margin screening relies on predeclared business risk tolerances; no automatic business release is authorized.
- The Hillstrom real-data report must be regenerated on the user's machine or using a locally available public CSV; the ZIP does not claim to include a newly fetched real-data result.
