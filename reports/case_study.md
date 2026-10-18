# Case study: the checkout redesign that almost shipped for the wrong reason

A simulated but realistic experiment with **known ground truth**: 200,000 users randomized 50/50 to the old or redesigned checkout for two weeks. The redesign truly raises each user's per-session purchase probability by 4%, which works out to a **+3.17% lift in conversion** and **+4.00% in revenue per user**. Sessions, order values, the two guardrails and twelve engagement metrics are untouched by the change. Five traps are planted - the same ones that break real experiments. Reproduce with `python scripts/case_study.py`.

## Scorecard

| Trap | Naive analysis | abtrust workflow |
|---|---|---|
| 1. Logging bug (SRM) | not checked; reports conversion lift +4.45% [+2.59%, +6.30%] vs truth +3.17% (+40% overstated) | SRM flagged (p=1.8e-08); drill-down isolates `android_legacy`; after the fix +3.30% [+1.51%, +5.09%] vs truth +3.16% |
| 2. Heavy-tailed revenue | plain t-test on the buggy log: [+0.40%, +6.80%], p=0.025, called significant with no multiple-testing correction | CUPED on clean data: [-0.08%, +5.99%], 5% narrower than a plain t-test on the same data; inconclusive after Holm (p_adj=0.76) |
| 3. Ratio metric | per-session CI [+1.73%, +5.29%] (clean data) | delta-method CI [+1.57%, +5.45%] - the naive one is 8% too narrow |
| 4. Daily peeking | stops on day 2 of the buggy log claiming +5.31% | working-normal approximation crosses 0.05 on day 11 (lift then +3.28%); exploratory only |
| 5. 14 null metrics | 0 'significant' at p < 0.05: none | 0 after Holm correction: none |

![Forest plot](figures/case_forest.png)

## Trap 1 - the logging bug

A JavaScript error on legacy Android drops 2,975 treatment users from the exposure log (control is unaffected). The analytics table therefore holds 99,763 control and 97,262 treatment users. Those lost users buy at half the usual rate, so the treatment arm that remains looks better than it should.

**abtrust** refuses to report effects: `DO NOT DECIDE - sample ratio mismatch; investigate missing exposure records.` The per-platform drill-down (`abtrust.srm_by_segment`) points straight at the cause:

| platform | units | share_control | share_treatment | p_value | flagged |
|---|---:|---:|---:|---:|---:|
| android_legacy | 6,937 | 71.73% | 28.27% | 6.2e-287 | 1 |
| ios | 49,865 | 49.69% | 50.31% | 0.16 | 0 |
| web | 110,435 | 49.92% | 50.08% | 0.58 | 0 |
| android | 29,788 | 49.97% | 50.03% | 0.92 | 0 |

The fix used here is to drop `android_legacy` from **both** arms (the comparison stays randomized within the remaining platforms) and to report the result for that population. The ground truth for that population is a +3.16% conversion lift.

## Traps 2-3 - precision done right

Revenue per user has a standard deviation 3.5 times its mean. CUPED with each user's pre-period revenue (correlation 0.33) removes 11% of the variance of the estimate, so the interval is 5% narrower than the plain t-test on identical data - the same precision as running the experiment 12% longer, for free. Revenue remains inconclusive after correction (p = 0.053, Holm-adjusted 0.758). The naive pipeline's 'significant' revenue result (p = 0.025) was computed on the biased log and never corrected for the 17 comparisons in the readout. Being honest about uncertainty is part of the job: the true +4% revenue effect exists, but this experiment alone cannot confirm it.

Orders per session treats sessions as independent, but sessions of one user share that user's taste. The per-session interval is 8% narrower than the correct per-user delta-method interval. Users here differ only moderately in their purchase propensity; the validation report shows how quickly per-session false-positive rates grow as that heterogeneity rises.

## Trap 4 - peeking

![Daily p-values](figures/case_peeking.png)

The naive pipeline peeks at the buggy log every day and stops on **day 2**, announcing a +5.31% lift - about 1.7x the truth. On the clean data (chart above) the fixed-horizon p-value first dips below 0.05 on day 4. The effect is real, so stopping there would have been the right call - by luck: the same stopping rule declares a winner in 20% of no-effect experiments checked 10 times and 25% of those checked 20 times (validation report). The working-normal mSPRT approximation crosses 0.05 on day 11; this uses estimated variance and does NOT establish an anytime-valid stopping decision.


## Trap 5 - many metrics

Of the 14 metrics with no true effect, the naive analysis flags 0 at p < 0.05 (none). With Holm correction across all 17 comparisons, abtrust flags 0. This run happened to be lucky - with 14 independent null metrics the chance of at least one spurious 'win' is 1 - 0.95^14 = 51% per experiment (the validation report measures it).

## Estimates vs truth

Each analysis is scored against the truth for the population it describes: all users for the naive pipeline (run on the buggy log), all but `android_legacy` for abtrust (run after the SRM fix). Covering the truth in one run is weak evidence either way - the validation report measures coverage over thousands of runs.

| metric | naive | truth_naive | naive_covers | abtrust | truth_abtrust | abtrust_covers |
|---|---:|---:|---|---:|---:|---|
| conversion | +4.45% | +3.17% | yes | +3.30% | +3.16% | yes |
| revenue per user | +3.60% | +4.00% | yes | +2.96% | +4.00% | yes |
| orders per session | +5.09% | +4.00% | yes | +3.51% | +4.00% | yes |

## Full abtrust readout (after the fix)

See [`case_study_readout.md`](case_study_readout.md) - generated by `abtrust.analyze(...).to_markdown()`.

**Decision:** REVIEW REQUIRED - primary improved; guardrail harm margins missing, so safety is not established.
