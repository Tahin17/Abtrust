# Learning walkthrough and portfolio demonstration

abtrust estimates experiment effects and helps determine whether a readout is trustworthy enough to inform a decision. Its methods are established statistical techniques. The engineering contribution is implementing them together, checking assumptions, exposing uncertainty and generating reproducible evidence.

## Start with the simulated checkout

Read `reports/case_study.md` beside `reports/case_study_readout.md`. All checkout customers, events and known effects are generated. The original simulation randomizes 200,000 users; a planted logging defect drops treatment users on legacy Android. The observed conversion lift is about 4.45%, while the simulated population truth is about 3.17%. The SRM diagnostic detects the allocation mismatch.

The example excludes legacy Android from both arms. This produces an analysis of the remaining platforms, not a repaired estimate for every original customer. The restricted-population conversion estimate is about 3.30% relative lift, compared with its own known truth of about 3.16%. A single interval covering the truth is not validation by itself; repeated Monte Carlo experiments assess coverage.

### Read one row carefully

The adjusted conversion difference is approximately 0.006518. Multiply by 100 to obtain **0.6518 percentage points**. Dividing that difference by its control baseline gives approximately **3.30% relative lift**. These describe the same effect on different scales.

The confidence interval describes uncertainty under the method's assumptions. The p-value does not give the probability that the null is true. Holm correction accounts for the declared comparison family; it does not convert the adjacent ordinary intervals into simultaneous intervals. CUPED uses pre-experiment information to remove predictable noise. It does not increase the underlying treatment effect or train a boosting ensemble.

The primary conversion result improves, but the readout remains **REVIEW REQUIRED**: acceptable guardrail harm margins were not declared. A guardrail that is not significantly worse may still have a practically important harmful effect within its uncertainty range. Do not choose a harm margin after inspecting outcomes to obtain a favorable verdict.

## Compare with real experimental data

`reports/hillstrom.md` analyzes the historical 64,000-customer randomized email dataset. Its real-data status is distinct from the synthetic checkout and the schema stand-in used by unit tests. Both campaigns show visit improvements, but the file lacks documented original participant IDs and configured messaging-safety outcomes. The readout appropriately remains **REVIEW REQUIRED**.

Spending per randomized customer targets the assigned customer population. Spending per visitor conditions on a population the email itself can change, so it is a diagnostic rather than a straightforward effect on a fixed set of customers. The direct men's-versus-women's comparisons are a separate exploratory testing family; differences between subgroup significance labels are not interaction tests.

## Learn from the stress report

`reports/stress/validation.md` includes failure cases as well as calibrated cases. At a 0.2% baseline with only 400 users per arm, most groups contain very few events. In the alternative scenario, the nominal 95% Welch intervals covered the known effect in **84.75%** of 2,000 simulations. That is a concrete limitation of this approximation in this setting, not a reason to suppress the result or claim general validity from larger-sample studies.

Removing the lowest 20% of treatment outcomes creates strong bias and nearly universal false rejection under the null in the deliberately INVALID scenario. More elaborate adjustment does not repair outcome-dependent selection. The data-quality and experimental-design checks remain essential.

The known-SD Gaussian study genuinely generates independent Gaussian observations with SDs fixed at 1 and 1.5 and a prespecified mixture scale. At 100 looks under the null it observed 1.3% false rejections in 2,000 simulations. That result is conditional evidence under that model; it does not license estimated-SD use or certify the exploratory working-normal mode.

## A three-minute demonstration

| Time | Show | Explain |
|---|---|---|
| 0:00–0:30 | README and sample dashboard | Question, control/treatment, one row per randomized user |
| 0:30–1:15 | Checkout SRM table | The logging defect and why the initial lift is misleading |
| 1:15–2:00 | Corrected conversion row and forest plot | Restricted population, absolute/relative effect, uncertainty and correction |
| 2:00–2:30 | Guardrail section | Why improvement alone does not establish safety |
| 2:30–3:00 | Core/stress reports and Hillstrom caveats | Simulations versus real data, reproducibility and limitations |

Use `python scripts/verify.py --integration --full` for the recorded local verification workflow. For a short live presentation, open the saved reports and run the dashboard instead of waiting for full simulations. Clearly call the 40,000-user dashboard sample simulated.

## Self-check before presenting

Explain why sessions from the same user are not independent users; why repeated fixed-horizon testing changes false-positive behavior; what CUPED needs from pre-treatment covariates; what Holm and BH control; why the SRM pass does not prove perfect logging; and why a statistically significant gain can still produce REVIEW REQUIRED.

A defensible portfolio description is: “Built a Python A/B experimentation toolkit integrating effect estimation, variance reduction, allocation diagnostics, multiple-testing correction, explicit sequential assumptions, and reproducible synthetic validation with a real-data case study.” Avoid describing the project as a new statistical invention or deployment certification.
