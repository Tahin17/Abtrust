# Supplemental stress validation (synthetic)

This report measures selected methods empirically under the listed simulations. Simulations cannot prove a general statistical guarantee. In particular the original mSPRT inserts estimated variances into a known-variance likelihood ratio: its displayed sequential results are a WORKING-NORMAL APPROXIMATION, not an exact anytime-valid test. For exact assumptions see docs/methods.md. Columns ending in `mcse` are Monte Carlo standard errors of simulated rates.

Simulation results saved 2026-10-18 19:00 UTC with Python 3.10.11, numpy 2.2.6. Reproduce with `abtrust stress --simulations 2000`. These are supplemental studies, separate from the seven core studies.

## Summary

- **How do fixed-horizon methods behave near their limits?** Synthetic diagnostics only. Selected treatment outcomes deliberately violate randomization; inspect bias and coverage.
- **How does the known-SD Gaussian procedure behave across monitoring schedules?** Synthetic calibration under genuinely known Gaussian SDs and a prespecified mixture scale.

## Details

### How do fixed-horizon methods behave near their limits?

**Result:** Synthetic diagnostics only. Selected treatment outcomes deliberately violate randomization; inspect bias and coverage.

| scenario | method | true_effect | measure | rejection_rate | rejection_mcse | coverage | coverage_mcse | bias | mean_se | n_control | mean_complete_treatment | n_sims |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| correlated covariates | welch | 0 | false_positive_rate | 0.0545 | 0.005076 | 0.9455 | 0.005076 | -0.004245 | 0.1162 | 400 | 400 | 2,000 |
| correlated covariates | cuped | 0 | false_positive_rate | 0.0585 | 0.005248 | 0.9415 | 0.005248 | -0.00334 | 0.09226 | 400 | 400 | 2,000 |
| correlated covariates | lin_hc2 | 0 | false_positive_rate | 0.0585 | 0.005248 | 0.9415 | 0.005248 | -0.003444 | 0.09243 | 400 | 400 | 2,000 |
| correlated covariates | welch | 0.1 | power | 0.128 | 0.00747 | 0.956 | 0.004586 | -0.0009771 | 0.1162 | 400 | 400 | 2,000 |
| correlated covariates | cuped | 0.1 | power | 0.189 | 0.008754 | 0.9565 | 0.004561 | 0.001721 | 0.09218 | 400 | 400 | 2,000 |
| correlated covariates | lin_hc2 | 0.1 | power | 0.1915 | 0.008799 | 0.959 | 0.004434 | 0.001822 | 0.09235 | 400 | 400 | 2,000 |
| unequal allocation | welch | 0 | false_positive_rate | 0.047 | 0.004732 | 0.953 | 0.004732 | -0.002886 | 0.08524 | 400 | 1600 | 2,000 |
| unequal allocation | cuped | 0 | false_positive_rate | 0.048 | 0.00478 | 0.952 | 0.00478 | -0.0008946 | 0.06443 | 400 | 1600 | 2,000 |
| unequal allocation | lin_hc2 | 0 | false_positive_rate | 0.048 | 0.00478 | 0.952 | 0.00478 | 4.945e-05 | 0.06453 | 400 | 1600 | 2,000 |
| unequal allocation | welch | 0.1 | power | 0.219 | 0.009248 | 0.954 | 0.004684 | 0.0005776 | 0.08526 | 400 | 1600 | 2,000 |
| unequal allocation | cuped | 0.1 | power | 0.3405 | 0.0106 | 0.955 | 0.004635 | -0.0004902 | 0.06448 | 400 | 1600 | 2,000 |
| unequal allocation | lin_hc2 | 0.1 | power | 0.3425 | 0.01061 | 0.956 | 0.004586 | 0.00041 | 0.06458 | 400 | 1600 | 2,000 |
| rare conversion | welch | 0 | false_positive_rate | 0.0045 | 0.001497 | 0.9955 | 0.001497 | 3.125e-05 | 0.002656 | 400 | 400 | 2,000 |
| rare conversion | welch | 0.001 | power | 0.0135 | 0.00258 | 0.8475 | 0.008039 | 5.375e-05 | 0.003162 | 400 | 400 | 2,000 |
| constant outcomes | welch | 0 | false_positive_rate | 0 | 0 | 1 | 0 | 0 | 0 | 400 | 400 | 2,000 |
| constant outcomes | welch | 0.125 | power | 1 | 0 | 1 | 0 | 0 | 0 | 400 | 400 | 2,000 |
| selected treatment outcomes (INVALID) | welch | 0 | false_positive_rate | 1 | 0 | 0 | 0 | 0.6226 | 0.1075 | 400 | 320 | 2,000 |
| selected treatment outcomes (INVALID) | cuped | 0 | false_positive_rate | 0.9985 | 0.0008654 | 0.0015 | 0.0008654 | 0.4654 | 0.08773 | 400 | 320 | 2,000 |
| selected treatment outcomes (INVALID) | lin_hc2 | 0 | false_positive_rate | 0.999 | 0.0007068 | 0.001 | 0.0007068 | 0.4764 | 0.08624 | 400 | 320 | 2,000 |
| selected treatment outcomes (INVALID) | welch | 0.1 | power | 1 | 0 | 0.0005 | 0.0004999 | 0.6204 | 0.1076 | 400 | 320 | 2,000 |
| selected treatment outcomes (INVALID) | cuped | 0.1 | power | 1 | 0 | 0.0025 | 0.001117 | 0.4635 | 0.08777 | 400 | 320 | 2,000 |
| selected treatment outcomes (INVALID) | lin_hc2 | 0.1 | power | 1 | 0 | 0.001 | 0.0007068 | 0.4756 | 0.08631 | 400 | 320 | 2,000 |

Results are synthetic diagnostics under the assumptions recorded in the manifest. The INVALID selection scenario intentionally violates the analysis assumptions; constant outcomes are a deterministic fixture, not a guarantee for rare-event inference.

<sub>2,000 simulated experiments per cell · 28s</sub>

### How does the known-SD Gaussian procedure behave across monitoring schedules?

**Result:** Synthetic calibration under genuinely known Gaussian SDs and a prespecified mixture scale.

| mode | true_effect | looks | measure | rejection_rate | rejection_mcse | simultaneous_coverage | coverage_mcse | mean_sample_fraction | n_per_arm | tau | n_sims |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gaussian_known_sd | 0 | 1 | false_positive_rate | 0.0015 | 0.0008654 | 0.9985 | 0.0008654 | 1 | 500 | 0.231 | 2,000 |
| gaussian_known_sd | 0 | 20 | false_positive_rate | 0.0105 | 0.002279 | 0.9895 | 0.002279 | 0.9956 | 500 | 0.231 | 2,000 |
| gaussian_known_sd | 0 | 100 | false_positive_rate | 0.013 | 0.002533 | 0.987 | 0.002533 | 0.9936 | 500 | 0.231 | 2,000 |
| gaussian_known_sd | 0.2 | 1 | power | 0.302 | 0.01027 | 0.997 | 0.001223 | 1 | 500 | 0.231 | 2,000 |
| gaussian_known_sd | 0.2 | 20 | power | 0.3795 | 0.01085 | 0.9895 | 0.002279 | 0.8579 | 500 | 0.231 | 2,000 |
| gaussian_known_sd | 0.2 | 100 | power | 0.4085 | 0.01099 | 0.985 | 0.002718 | 0.8328 | 500 | 0.231 | 2,000 |

Results are synthetic diagnostics under the assumptions recorded in the manifest. The INVALID selection scenario intentionally violates the analysis assumptions; constant outcomes are a deterministic fixture, not a guarantee for rare-event inference.

<sub>2,000 simulated experiments per cell · 12s</sub>
