# Validation report

This report measures selected methods empirically under the listed simulations. Simulations cannot prove a general statistical guarantee. In particular the original mSPRT inserts estimated variances into a known-variance likelihood ratio: its displayed sequential results are a WORKING-NORMAL APPROXIMATION, not an exact anytime-valid test. For exact assumptions see docs/methods.md. Columns ending in `mcse` are Monte Carlo standard errors of simulated rates.

Simulation results saved 2026-10-18 18:59 UTC with Python 3.10.11, numpy 2.2.6. Reproduce the full core suite with `abtrust validate`; use a separate `--out` directory for reduced-budget runs.

## Summary

- **Does the Welch test hold its 5% error rate and 95% coverage, even on heavy-tailed revenue?** Welch false-positive rate 3.9%-5.1% and 95% CI coverage 94.4%-95.9% across metrics and sizes.
- **How does naive peeking compare with a working-normal mSPRT approximation?** Peeking 100 times inflates false positives to 38.1%; working-normal mSPRT has 1.6% empirically (not a formal guarantee).
- **Does CUPED reduce variance as much as theory says, without inflating false positives?** At rho=0.7 CUPED shrinks the SE to 0.73x (theory 0.71x) and lifts power from 50% to 79% with false-positive rate 5.3%.
- **What happens if a ratio metric is analysed per event instead of per user?** At ICC=0.10, per-session analysis has a 14.5% false-positive rate; the delta method has 5.1%.
- **How sensitive is the SRM check, and how often does it false-alarm?** SRM check false-alarm rate 0.10% at threshold 0.001; detects a 50.5/49.5 split at n=100k 45% of the time.
- **Do 80%-power designs actually deliver 80% power?** Planned 80% power -> empirical 79.4%, 80.2%, 79.8%.
- **How often does a many-metric readout produce a false win?** With 14 null metrics, P(at least one false win) is 52% uncorrected, 5.7% with Holm, 5.8% with Benjamini-Hochberg.

## Details

### Does the Welch test hold its 5% error rate and 95% coverage, even on heavy-tailed revenue?

**Result:** Welch false-positive rate 3.9%-5.1% and 95% CI coverage 94.4%-95.9% across metrics and sizes.

| metric | n_per_arm | false_positive_rate | fpr_mcse | ci_coverage | coverage_mcse |
|---|---:|---:|---:|---:|---:|
| conversion | 500 | 5.12% | 0.35% | 95.90% | 0.31% |
| conversion | 2,000 | 4.98% | 0.34% | 94.40% | 0.36% |
| conversion | 10,000 | 5.03% | 0.35% | 94.95% | 0.35% |
| revenue | 500 | 3.90% | 0.31% | 95.90% | 0.31% |
| revenue | 2,000 | 4.67% | 0.33% | 95.80% | 0.32% |
| revenue | 10,000 | 4.95% | 0.34% | 94.92% | 0.35% |

Target: false-positive rate 5%, coverage 95%. The revenue metric is zero-inflated lognormal (8% buyers, heavy right tail), the hardest case for a t-test.

<sub>4,000 simulated experiments per cell · 15s</sub>

### How does naive peeking compare with a working-normal mSPRT approximation?

**Result:** Peeking 100 times inflates false positives to 38.1%; working-normal mSPRT has 1.6% empirically (not a formal guarantee).

![Peeking](figures/peeking.png)

Rejection rate by number of looks (A/A = false-positive rate; other scenarios = power):
Each bounded procedure uses its own monitoring schedule and error budget, starting at look 1.

| scenario | looks | Hoeffding CS (bounded, valid) | mSPRT (working-normal approximate) | naive t-test (peeking) |
|---|---:|---:|---:|---:|
| A/A (no effect) | 1 | 0.0% | 0.1% | 4.8% |
| A/A (no effect) | 2 | 0.0% | 0.4% | 8.9% |
| A/A (no effect) | 5 | 0.0% | 0.7% | 14.7% |
| A/A (no effect) | 10 | 0.0% | 1.0% | 19.6% |
| A/A (no effect) | 20 | 0.0% | 1.3% | 25.4% |
| A/A (no effect) | 50 | 0.0% | 1.5% | 33.1% |
| A/A (no effect) | 100 | 0.0% | 1.6% | 38.1% |
| effect = 2 x MDE | 1 | 78.8% | 98.7% | 100.0% |
| effect = 2 x MDE | 2 | 53.3% | 98.8% | 100.0% |
| effect = 2 x MDE | 5 | 25.3% | 99.0% | 100.0% |
| effect = 2 x MDE | 10 | 11.5% | 99.1% | 100.0% |
| effect = 2 x MDE | 20 | 4.2% | 99.2% | 100.0% |
| effect = 2 x MDE | 50 | 1.1% | 99.2% | 100.0% |
| effect = 2 x MDE | 100 | 0.2% | 99.3% | 100.0% |
| effect = MDE | 1 | 2.1% | 36.6% | 78.1% |
| effect = MDE | 2 | 0.5% | 38.7% | 80.4% |
| effect = MDE | 5 | 0.0% | 41.9% | 83.9% |
| effect = MDE | 10 | 0.0% | 43.5% | 86.0% |
| effect = MDE | 20 | 0.0% | 45.5% | 87.4% |
| effect = MDE | 50 | 0.0% | 47.5% | 89.2% |
| effect = MDE | 100 | 0.0% | 48.4% | 90.2% |

Cost and benefit of each sequential procedure (100 looks):

| scenario | method | mean_sample_fraction | simultaneous_coverage | naive_simultaneous_coverage |
|---|---|---:|---:|---:|
| A/A (no effect) | mSPRT (working-normal approximate) | 99% | 98.4% | 61.9% |
| A/A (no effect) | Hoeffding CS (bounded, valid) | 100% | 100.0% | 61.9% |
| effect = MDE | mSPRT (working-normal approximate) | 80% | 98.6% | 62.0% |
| effect = MDE | Hoeffding CS (bounded, valid) | 100% | 100.0% | 62.0% |
| effect = 2 x MDE | mSPRT (working-normal approximate) | 36% | 99.0% | 62.0% |
| effect = 2 x MDE | Hoeffding CS (bounded, valid) | 100% | 100.0% | 62.0% |

`mean_sample_fraction` is the average fraction of planned observations used before the named procedure first rejects. `simultaneous_coverage` is the fraction of simulations whose intervals cover the true effect at every look. The **working-normal** mSPRT is empirical ONLY and does not inherit a formal anytime-valid guarantee from these rates. The bounded Hoeffding result does have a time-uniform guarantee under its independent [0,1], stable-mean assumptions, but may be extremely conservative. `gaussian_known_sd` requires independent Gaussian outcomes with genuinely known SDs, equal arm sizes and prespecified tau.

<sub>3,000 simulated experiments per cell · 98s</sub>

### Does CUPED reduce variance as much as theory says, without inflating false positives?

**Result:** At rho=0.7 CUPED shrinks the SE to 0.73x (theory 0.71x) and lifts power from 50% to 79% with false-positive rate 5.3%.

![CUPED](figures/cuped.png)

| rho | method | se_ratio | theory_se_ratio | reported_se_over_empirical_sd | false_positive_rate | power |
|---:|---|---:|---:|---:|---:|---:|
| 0.0 | welch | 1.000 | 1.000 | 0.998 | 4.80% | 53.1% |
| 0.0 | cuped | 1.000 | 1.000 | 0.998 | 4.73% | 53.1% |
| 0.0 | lin_hc2 | 1.000 | 1.000 | 0.998 | 4.77% | 53.1% |
| 0.3 | welch | 1.000 | 1.000 | 0.993 | 5.10% | 52.2% |
| 0.3 | cuped | 0.946 | 0.954 | 1.001 | 4.87% | 56.7% |
| 0.3 | lin_hc2 | 0.946 | 0.954 | 1.001 | 4.90% | 56.7% |
| 0.5 | welch | 1.000 | 1.000 | 0.987 | 5.00% | 53.1% |
| 0.5 | cuped | 0.864 | 0.866 | 0.990 | 4.83% | 64.0% |
| 0.5 | lin_hc2 | 0.864 | 0.866 | 0.990 | 4.83% | 64.0% |
| 0.7 | welch | 1.000 | 1.000 | 1.000 | 5.40% | 49.6% |
| 0.7 | cuped | 0.728 | 0.714 | 0.981 | 5.27% | 79.4% |
| 0.7 | lin_hc2 | 0.728 | 0.714 | 0.981 | 5.27% | 79.4% |
| 0.9 | welch | 1.000 | 1.000 | 1.003 | 5.13% | 51.7% |
| 0.9 | cuped | 0.440 | 0.436 | 0.992 | 5.73% | 99.6% |
| 0.9 | lin_hc2 | 0.440 | 0.436 | 0.993 | 5.73% | 99.6% |

`lin_hc2` is regression adjustment with treatment interactions and HC2 robust SEs (Lin, 2013). `reported_se_over_empirical_sd` close to 1 means each method's reported SE is honest.

<sub>3,000 simulated experiments per cell · 58s</sub>

### What happens if a ratio metric is analysed per event instead of per user?

**Result:** At ICC=0.10, per-session analysis has a 14.5% false-positive rate; the delta method has 5.1%.

![Ratio metrics](figures/ratio_metrics.png)

| icc | method | false_positive_rate | ci_coverage | naive_se_over_delta_se |
|---:|---|---:|---:|---:|
| 0.00 | naive per-session | 4.83% | 95.63% | 1.000 |
| 0.00 | delta method | 4.80% | 95.67% | 1.000 |
| 0.02 | naive per-session | 6.73% | 93.23% | 0.929 |
| 0.02 | delta method | 5.40% | 95.33% | 0.929 |
| 0.05 | naive per-session | 10.07% | 89.90% | 0.847 |
| 0.05 | delta method | 4.93% | 94.83% | 0.847 |
| 0.10 | naive per-session | 14.50% | 85.53% | 0.747 |
| 0.10 | delta method | 5.13% | 94.93% | 0.747 |
| 0.20 | naive per-session | 21.80% | 77.97% | 0.623 |
| 0.20 | delta method | 5.13% | 94.73% | 0.623 |

<sub>3,000 simulated experiments per cell · 44s</sub>

### How sensitive is the SRM check, and how often does it false-alarm?

**Result:** SRM check false-alarm rate 0.10% at threshold 0.001; detects a 50.5/49.5 split at n=100k 45% of the time.

![SRM](figures/srm.png)

| treatment_share | n=10,000 | n=100,000 | n=1,000,000 |
|---:|---:|---:|---:|
| 50.00% | 0.1% | 0.1% | 0.1% |
| 50.10% | 0.2% | 0.1% | 8.9% |
| 50.25% | 0.2% | 4.8% | 95.2% |
| 50.50% | 0.9% | 44.5% | 100.0% |
| 51.00% | 10.2% | 100.0% | 100.0% |

The first row (true 50/50 split) is the false-alarm rate; the target is the 0.1% threshold.

<sub>2,000 simulated experiments per cell · 9s</sub>

### Do 80%-power designs actually deliver 80% power?

**Result:** Planned 80% power -> empirical 79.4%, 80.2%, 79.8%.

| design | method | n_per_arm | planned_power | empirical_power | mcse | n_sims |
|---|---|---:|---:|---:|---:|---:|
| conversion 10% -> 11% | welch | 14,749 | 80% | 79.4% | 0.9% | 2,000 |
| revenue (zero-inflated lognormal) +20% | welch | 24,782 | 80% | 80.2% | 1.8% | 500 |
| CUPED-planned, rho=0.6 (n 1,570 -> 1,005) | cuped | 1,005 | 80% | 79.8% | 0.9% | 2,000 |

<sub>500–2,000 simulated experiments per cell; exact counts shown in n_sims · 3s</sub>

### How often does a many-metric readout produce a false win?

**Result:** With 14 null metrics, P(at least one false win) is 52% uncorrected, 5.7% with Holm, 5.8% with Benjamini-Hochberg.

| metrics | scenario | correction | fwer | fdr | power |
|---:|---|---|---:|---:|---:|
| 1 | all null | none | 5.6% | 5.6% |  |
| 1 | all null | holm | 5.6% | 5.6% |  |
| 1 | all null | bh | 5.6% | 5.6% |  |
| 1 | 20% real effects | none | 0.0% | 0.0% | 86.2% |
| 1 | 20% real effects | holm | 0.0% | 0.0% | 86.2% |
| 1 | 20% real effects | bh | 0.0% | 0.0% | 86.2% |
| 5 | all null | none | 23.5% | 23.5% |  |
| 5 | all null | holm | 5.5% | 5.5% |  |
| 5 | all null | bh | 5.7% | 5.7% |  |
| 5 | 20% real effects | none | 18.6% | 10.9% | 85.4% |
| 5 | 20% real effects | holm | 4.3% | 2.7% | 66.2% |
| 5 | 20% real effects | bh | 6.8% | 3.9% | 66.8% |
| 14 | all null | none | 52.1% | 52.1% |  |
| 14 | all null | holm | 5.7% | 5.7% |  |
| 14 | all null | bh | 5.8% | 5.8% |  |
| 14 | 20% real effects | none | 46.0% | 19.9% | 85.7% |
| 14 | 20% real effects | holm | 4.7% | 2.6% | 54.2% |
| 14 | 20% real effects | bh | 10.1% | 4.5% | 59.9% |
| 50 | all null | none | 91.0% | 91.0% |  |
| 50 | all null | holm | 5.4% | 5.4% |  |
| 50 | all null | bh | 5.5% | 5.5% |  |
| 50 | 20% real effects | none | 86.4% | 17.8% | 84.8% |
| 50 | 20% real effects | holm | 3.4% | 0.7% | 39.6% |
| 50 | 20% real effects | bh | 25.4% | 4.1% | 61.5% |

`fwer` = probability of at least one false positive; `fdr` = average share of false positives among rejections; `power` = share of real effects detected. Holm controls FWER, while BH controls FDR under its standard dependence assumptions; in this ALL-NULL scenario FDR = FWER. For this simulation; values slightly above 5% sit within about 1.5 Monte Carlo standard errors (roughly 0.5 points at 2,000 simulations) - note the single-metric row, where no correction is applied at all, shows the same excess, so it comes from the simulation draw.

<sub>2,000 simulated experiments per cell · 64s</sub>
