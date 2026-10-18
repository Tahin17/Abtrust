# Hillstrom e-mail experiment - abtrust readout

**Arms:** `No E-Mail` n=21,306, `Mens E-Mail` n=21,307, `Womens E-Mail` n=21,387 (control = `No E-Mail`)

**Decision:** REVIEW REQUIRED - primary improved, but no guardrails configured; safety not assessed.

## 1. Sample ratio mismatch

**PASS** - no SRM: observed [33.29%, 33.29%, 33.42%] vs expected [33.33%, 33.33%, 33.33%], chi2=0.20, p=0.9

## 2. Results

Two-sided tests at alpha = 0.05, Holm correction across 8 comparison(s). Intervals are unadjusted 95% confidence intervals (Holm/BH adjusts p-values, not these intervals). Guardrail safety bounds, if configured, use Bonferroni across guardrail comparisons.

| Arm | Metric | Role | Method | Control | Treatment | Absolute effect (CI) | Relative effect (CI) | p | p adj. | Verdict |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Mens E-Mail | visit | primary | lin_hc2 | 0.1061 | 0.1828 | +0.07662 (+0.07001, +0.08323) | +72.18% (+63.92%, +80.45%) | <0.0001 | <0.0001 | significant improvement |
| Mens E-Mail | conversion | secondary | lin_hc2 | 0.005724 | 0.01252 | +0.0068 (+0.004997, +0.008603) | +118.80% (+72.15%, +165.45%) | <0.0001 | <0.0001 | significant improvement |
| Mens E-Mail | spend per customer | secondary | lin_hc2 | 0.6528 | 1.422 | +0.7691 (+0.4845, +1.054) | +117.82% (+54.34%, +181.29%) | <0.0001 | <0.0001 | significant improvement |
| Mens E-Mail | spend per visitor | secondary | delta_ratio | 6.149 | 7.784 | +1.636 (-0.2992, +3.57) | +26.60% (-9.78%, +62.98%) | 0.0976 | 0.1951 | not significant |
| Womens E-Mail | visit | primary | lin_hc2 | 0.1062 | 0.1514 | +0.04523 (+0.03892, +0.05155) | +42.61% (+35.47%, +49.75%) | <0.0001 | <0.0001 | significant improvement |
| Womens E-Mail | conversion | secondary | lin_hc2 | 0.005725 | 0.008833 | +0.003108 (+0.001497, +0.00472) | +54.30% (+19.31%, +89.28%) | 0.0002 | 0.0006 | significant improvement |
| Womens E-Mail | spend per customer | secondary | lin_hc2 | 0.6528 | 1.077 | +0.4238 (+0.1685, +0.6791) | +64.92% (+14.86%, +114.98%) | 0.0011 | 0.0034 | significant improvement |
| Womens E-Mail | spend per visitor | secondary | delta_ratio | 6.149 | 7.115 | +0.9662 (-0.9909, +2.923) | +15.71% (-18.93%, +50.36%) | 0.3332 | 0.3332 | not significant |

## 3. Notes

- No unit_col was provided: unique randomization units could not be verified.
- visit (Mens E-Mail): Regression adjustment (Lin, HC2) with `history`, `recency` cut the variance of the estimate by 0.9% (CI 0.4% narrower than unadjusted); unadjusted estimate +0.07659, p=<0.0001.
- conversion (Mens E-Mail): Regression adjustment (Lin, HC2) with `history`, `recency` made no material difference to precision - the covariates barely predict this metric; unadjusted estimate +0.006805, p=<0.0001.
- spend per customer (Mens E-Mail): Regression adjustment (Lin, HC2) with `history`, `recency` made no material difference to precision - the covariates barely predict this metric; unadjusted estimate +0.7698, p=<0.0001.
- visit (Womens E-Mail): Regression adjustment (Lin, HC2) with `history`, `recency` cut the variance of the estimate by 0.8% (CI 0.4% narrower than unadjusted); unadjusted estimate +0.04523, p=<0.0001.
- conversion (Womens E-Mail): Regression adjustment (Lin, HC2) with `history`, `recency` made no material difference to precision - the covariates barely predict this metric; unadjusted estimate +0.003111, p=0.0002.
- spend per customer (Womens E-Mail): Regression adjustment (Lin, HC2) with `history`, `recency` made no material difference to precision - the covariates barely predict this metric; unadjusted estimate +0.4244, p=0.0011.
- Absolute-effect and relative-effect intervals use different approximations; they can straddle zero differently near the significance threshold. P-values test the absolute effect.
- Ratio metrics are analysed per randomization unit with the delta method, not per event.

## Direct comparison: men's versus women's email

Randomized pairwise comparison among recipients of either message (men's minus women's). Four metrics are Holm-adjusted across this direct comparison; the direct comparison is essential before claiming one message outperformed the other. This is a separate exploratory family of four tests; Holm correction is NOT joint across the 8 control contrasts and these 4 tests. Do not interpret the two families as a single confirmatory analysis.

| metric | effect | ci_low | ci_high | p_value | p_adjusted | verdict |
|---|---:|---:|---:|---:|---:|---|
| visit | +0.03137 | +0.02433 | +0.03842 | 2.67e-18 | 1.07e-17 | significant improvement |
| conversion | +0.003693 | +0.001744 | +0.005643 | 0.000205 | 0.000614 | significant improvement |
| spend per customer | +0.3453 | +0.03253 | +0.6581 | 0.0305 | 0.061 | not significant |
| spend per visitor | +0.6693 | -1.172 | +2.511 | 0.476 | 0.476 | not significant |


## Exploratory: visit lift by customer subgroup

Subgroups are defined by pre-treatment attributes only. Holm correction is applied across the 8 subgroup tests; treat these as hypotheses for the next experiment, not conclusions.

| subgroup | arm | n | control_rate | treatment_rate | rel_lift | ci_low | ci_high | p_value | p_holm |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bought men's last year | Mens E-Mail | 23,526 | 11.45% | 19.61% | +71.2% | +60.6% | +81.9% | 3.5e-67 | 2.4e-66 |
| bought men's last year | Womens E-Mail | 23,527 | 11.45% | 13.63% | +19.0% | +10.9% | +27.1% | 4.7e-07 | 4.7e-07 |
| bought women's last year | Mens E-Mail | 23,417 | 11.14% | 19.40% | +74.1% | +63.1% | +85.1% | 1.6e-69 | 1.3e-68 |
| bought women's last year | Womens E-Mail | 23,433 | 11.14% | 18.45% | +65.6% | +55.1% | +76.2% | 2.8e-56 | 1.4e-55 |
| new customers | Mens E-Mail | 21,381 | 7.88% | 15.41% | +95.5% | +80.2% | +110.9% | 2e-66 | 1.2e-65 |
| new customers | Womens E-Mail | 21,458 | 7.88% | 12.92% | +64.0% | +50.6% | +77.3% | 8.4e-34 | 2.5e-33 |
| returning customers | Mens E-Mail | 21,232 | 13.37% | 21.16% | +58.2% | +48.6% | +67.8% | 3.9e-51 | 1.5e-50 |
| returning customers | Womens E-Mail | 21,235 | 13.37% | 17.39% | +30.0% | +21.7% | +38.3% | 5.1e-16 | 1e-15 |

## Caveat: spend per visitor

Spend per visitor divides by a post-treatment quantity: the e-mail changes *who* visits. If it brings in less-committed visitors, spend per visitor can fall even though spend per customer rises. That makes it a useful diagnostic but not a causal effect on any fixed group of people; decisions should rest on the per-customer metrics, whose denominator (everyone randomized) the treatment cannot change.

## Data provenance and deployment-safety limitations

The publicly distributed Hillstrom dataset does not document a stable original customer ID. By default the script therefore cannot verify that every row represents a distinct randomized person. If an input file supplies a `customer_id` or `user_id` column, the analysis verifies its uniqueness; an artificially generated row number is NOT a substitute for a source identifier.

The public dataset contains no prespecified unsubscribe, complaint, delivery or adverse-experience guardrail outcomes. A significant visit or conversion improvement is NOT evidence that deployment is safe or beneficial after messaging costs. The decision remains REVIEW REQUIRED and requires a business and safety review.

Exploratory subgroup contrasts are not treatment-by-subgroup interaction tests: a significant change in one subgroup and a nonsignificant change in another do not establish that effects differ. Use a prespecified interaction test in a future experiment.

## How this was produced

`python scripts/hillstrom.py` - visit, conversion and spend use Lin regression adjustment on last year's spend (`history`) and `recency` with HC2 robust standard errors; spend per visitor is a ratio metric (delta method); Holm correction across all arm x metric comparisons; SRM check against the designed 1/3 split.
