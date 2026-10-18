# Checkout redesign - readout after fixing the SRM

**Arms:** `control` n=94,787, `treatment` n=95,301 (control = `control`)

**Decision:** REVIEW REQUIRED - primary improved; guardrail harm margins missing, so safety is not established.

## 1. Sample ratio mismatch

**PASS** - no SRM: observed [49.86%, 50.14%] vs expected [50.00%, 50.00%], chi2=1.39, p=0.24

## 2. Results

Two-sided tests at alpha = 0.05, Holm correction across 17 comparison(s). Intervals are unadjusted 95% confidence intervals (Holm/BH adjusts p-values, not these intervals). Guardrail safety bounds, if configured, use Bonferroni across guardrail comparisons.

| Arm | Metric | Role | Method | Control | Treatment | Absolute effect (CI) | Relative effect (CI) | p | p adj. | Verdict |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| treatment | conversion | primary | cuped | 0.1977 | 0.2043 | +0.006518 (+0.003034, +0.01) | +3.30% (+1.51%, +5.09%) | 0.0002 | 0.0042 | significant improvement |
| treatment | revenue per user | secondary | cuped | 14.57 | 15.01 | +0.4309 (-0.004931, +0.8667) | +2.96% (-0.08%, +5.99%) | 0.0526 | 0.7582 | not significant |
| treatment | orders per session | secondary | delta_ratio | 0.06273 | 0.06493 | +0.002201 (+0.001007, +0.003396) | +3.51% (+1.57%, +5.45%) | 0.0003 | 0.0049 | significant improvement |
| treatment | unsubscribed | guardrail | welch | 0.004125 | 0.003945 | -0.0001796 (-0.0007496, +0.0003904) | -4.35% (-17.87%, +9.16%) | 0.5368 | 1.0000 | not significant |
| treatment | support_contact | guardrail | welch | 0.01264 | 0.01189 | -0.0007502 (-0.00174, +0.0002394) | -5.94% (-13.53%, +1.66%) | 0.1373 | 1.0000 | not significant |
| treatment | engagement_01 | secondary | welch | 0.3662 | 0.3603 | -0.005878 (-0.01177, +1.405e-05) | -1.61% (-3.20%, -0.01%) | 0.0505 | 0.7582 | not significant |
| treatment | engagement_02 | secondary | welch | 1.133 | 1.136 | +0.003114 (-0.008888, +0.01512) | +0.27% (-0.79%, +1.34%) | 0.6111 | 1.0000 | not significant |
| treatment | engagement_03 | secondary | welch | 1.16 | 1.162 | +0.002864 (-0.009322, +0.01505) | +0.25% (-0.81%, +1.30%) | 0.6450 | 1.0000 | not significant |
| treatment | engagement_04 | secondary | welch | 0.6657 | 0.6616 | -0.004104 (-0.01258, +0.004366) | -0.62% (-1.89%, +0.65%) | 0.3423 | 1.0000 | not significant |
| treatment | engagement_05 | secondary | welch | 0.5625 | 0.562 | -0.000547 (-0.008177, +0.007083) | -0.10% (-1.45%, +1.26%) | 0.8883 | 1.0000 | not significant |
| treatment | engagement_06 | secondary | welch | 1.503 | 1.511 | +0.0078 (-0.006855, +0.02245) | +0.52% (-0.46%, +1.50%) | 0.2969 | 1.0000 | not significant |
| treatment | engagement_07 | secondary | welch | 1.598 | 1.607 | +0.008621 (-0.006641, +0.02388) | +0.54% (-0.42%, +1.50%) | 0.2682 | 1.0000 | not significant |
| treatment | engagement_08 | secondary | welch | 0.4124 | 0.4082 | -0.004271 (-0.01062, +0.002082) | -1.04% (-2.57%, +0.50%) | 0.1877 | 1.0000 | not significant |
| treatment | engagement_09 | secondary | welch | 0.3868 | 0.3861 | -0.0007537 (-0.006858, +0.005351) | -0.19% (-1.77%, +1.38%) | 0.8088 | 1.0000 | not significant |
| treatment | engagement_10 | secondary | welch | 1.627 | 1.629 | +0.001821 (-0.01364, +0.01728) | +0.11% (-0.84%, +1.06%) | 0.8174 | 1.0000 | not significant |
| treatment | engagement_11 | secondary | welch | 1.883 | 1.885 | +0.002174 (-0.01507, +0.01942) | +0.12% (-0.80%, +1.03%) | 0.8048 | 1.0000 | not significant |
| treatment | engagement_12 | secondary | welch | 1.158 | 1.164 | +0.005959 (-0.006238, +0.01816) | +0.51% (-0.54%, +1.57%) | 0.3383 | 1.0000 | not significant |

## Guardrail safety screening

Absolute harm is positive when a lower-is-better guardrail rises or a higher-is-better guardrail falls. Missing prespecified harm margins mean **not assessed**; non-significance is not proof of safety.

| Arm | Guardrail | Prespecified max harm | Conservative upper harm bound | Screen |
|---|---|---:|---:|---|
| treatment | unsubscribed | n/a | 0.0004722 | unproven |
| treatment | support_contact | n/a | 0.0003815 | unproven |

## 3. Notes

- conversion (treatment): CUPED with `pre_sessions` (corr 0.25) cut the variance of the estimate by 6.5% (CI 3.3% narrower than unadjusted); unadjusted estimate +0.006236, p=0.0007.
- revenue per user (treatment): CUPED with `pre_revenue` (corr 0.33) cut the variance of the estimate by 10.6% (CI 5.5% narrower than unadjusted); unadjusted estimate +0.2853, p=0.2251.
- Guardrail safety uses two-sided Bonferroni-adjusted conservative bounds; harm margins must be chosen before observing outcomes. Passing is not a deployment authorization.
- Absolute-effect and relative-effect intervals use different approximations; they can straddle zero differently near the significance threshold. P-values test the absolute effect.
- Ratio metrics are analysed per randomization unit with the delta method, not per event.
