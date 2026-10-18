# Methods

The statistics behind each function, with the assumptions that matter in practice. Notation: control arm
$c$, treatment arm $t$, $n_c, n_t$ randomization units, $\bar y$ sample means, $s^2$ sample variances.

## 1. Difference in means - `welch_ttest`

$$\hat\Delta = \bar y_t - \bar y_c, \qquad \widehat{\mathrm{SE}} = \sqrt{s_t^2/n_t + s_c^2/n_c}$$

with Welch-Satterthwaite degrees of freedom. No equal-variance assumption, and the same formula handles 0/1
conversion metrics. By the central limit theorem it is valid for heavy-tailed metrics once $n$ is moderate -
the validation report checks this down to 500 users per arm on zero-inflated lognormal revenue.

**Relative effect.** $\hat r = \bar y_t / \bar y_c - 1$ with a delta-method variance
$\mathrm{Var}(\hat r) \approx \frac{\mathrm{Var}(\bar y_t)}{\bar y_c^2} + \frac{\bar y_t^2\,\mathrm{Var}(\bar y_c)}{\bar y_c^4}$,
which accounts for the noise in the control mean (dividing the absolute CI by $\bar y_c$ does not).

## 2. Ratio metrics - `ratio_delta`

Metrics like clicks per session are ratios of two per-user sums, $R = \sum_i X_i / \sum_i Y_i = \bar X / \bar Y$,
where $i$ indexes **users** (the randomization unit), not sessions. Sessions of one user are correlated, so
treating each session as an independent trial understates the variance. A first-order Taylor expansion of
$f(\bar X, \bar Y) = \bar X / \bar Y$ gives

$$\mathrm{Var}(\hat R) \approx \frac{1}{n}\left(\frac{\sigma_X^2}{\mu_Y^2} - \frac{2\mu_X\sigma_{XY}}{\mu_Y^3} + \frac{\mu_X^2\sigma_Y^2}{\mu_Y^4}\right).$$

Deng, Knoblich & Lu (2018), *Applying the Delta Method in Metric Analytics*.

## 3. CUPED - `cuped`

Given a pre-experiment covariate $X$ (e.g. the same metric in the weeks before launch), analyse

$$Y^{\mathrm{cv}} = Y - \theta\,(X - \bar X), \qquad \theta = \mathrm{Cov}(X, Y)/\mathrm{Var}(X)$$

with $\theta$ estimated on both arms pooled. Because $X$ is fixed before randomization,
$\mathbb E[\bar X_t - \bar X_c] = 0$ and the estimator stays unbiased; its variance falls to
$\mathrm{Var}(Y)(1-\rho^2)$ where $\rho = \mathrm{corr}(X, Y)$. A correlation of 0.7 halves the variance -
the same as doubling the sample. Deng, Xu, Kohavi & Walker (2013).

**Requirement:** $X$ must not be affected by the treatment. Use pre-period data only.

## 4. Regression adjustment - `lin_adjustment`

Fit $Y = \alpha + \tau T + \beta^\top \tilde X + \gamma^\top (T\cdot\tilde X) + \varepsilon$ with covariates
centred, $\tilde X = X - \bar X$. The coefficient $\hat\tau$ is the average treatment effect. Lin (2013) showed
that with the interaction terms and heteroskedasticity-robust (HC2) standard errors this estimator is
consistent and never asymptotically less precise than the unadjusted difference in means - even when the
linear model is wrong. With no covariate information, the HC2 standard error equals the Welch/Neyman standard
error exactly (a unit test checks this). Plugging an ML prediction of $Y$ from pre-period features in as $X$
gives CUPAC (Tang et al., 2020).

## 5. Sequential analysis - `sequential_test`

Naively checking a fixed-horizon p-value repeatedly inflates false positives. There are
**three distinct sequential modes**. Their guarantees must not be confused:

1. `mode="working_normal"` (legacy default for reproducibility). Plugging an estimated
   standard error into a known-variance normal-mixture SPRT often performs well in the
   simulations, but its likelihood ratio is **not proven to be a nonnegative martingale**.
   Consequently, its p-values and confidence sequences are **exploratory**. The legacy
   validation figures show empirical performance, **not** a general error guarantee.
   Choosing `tau=None` from the full replayed dataset further prevents prospective use.
2. `mode="bounded"` for independent unit-level observations in **[0,1]** (including
   binary conversion). At the kth preplanned monitoring look, spend
   $\alpha_k=\alpha 6/(\pi^2 k^2)$ and form a two-sided Hoeffding interval
   $\hat\Delta_k\pm\sqrt{(1/n_{ck}+1/n_{tk})\log(2/\alpha_k)/2}$.
   Since $\sum_{k\ge1}\alpha_k=\alpha$, the intersection of the intervals
   covers the true stationary difference of expectations **simultaneously across
   monitored looks** with probability at least $1-\alpha$. The running minimum of
   Hoeffding p-values divided by the spending weights is anytime-valid at these
   monitoring looks. This can be conservative.
3. `mode="gaussian_known_sd"` for independently observed Gaussian outcomes,
   **equal numbers of control and treatment users at every look**, actually known
   arm standard deviations, and `tau` fixed before examining outcomes. With
   $\hat\Delta_n\sim N(\theta,s_n^2)$ and
   $s_n^2=\sigma_c^2/n+\sigma_t^2/n$, the normal mixture likelihood ratio is
   $\Lambda_n=\sqrt{s_n^2/(s_n^2+\tau^2)}\exp(\tau^2\hat\Delta_n^2/[2s_n^2(s_n^2+\tau^2)])$.
   With those assumptions and a truly prespecified `tau`, the process is a
   likelihood-ratio martingale, so Ville's inequality provides an anytime-valid
   test. Sample-estimated variance **does not** meet the known-SD assumption.

```python
from abtrust import sequential_test, tau_from_design

# Exact, conservative guarantee for bounded independent binary outcomes:
seq = sequential_test(control_binary, treatment_binary, looks=14, mode="bounded")
print(seq.is_anytime_valid, seq.guarantee_note)

# Exact Gaussian-known-variance setting, with SD and tau fixed BEFORE outcomes:
seq2 = sequential_test(control_normal, treatment_normal, looks=14,
                       mode="gaussian_known_sd", known_sd=1.0,
                       tau=tau_from_design(1.0, planned_n_per_arm))
```

**Assumptions:** each arm contains independent observations in arrival order,
interim looks are fixed or predictable from sample counts, and the mean effect
being tested is stable over time. A full historical replay is descriptive, not
proof that a production monitoring system meets these assumptions.

Johari et al. (2017/2022); Howard et al. (2021).

## 6. Sample ratio mismatch - `srm_test`, `srm_by_segment`

A chi-square goodness-of-fit test of observed arm counts against the designed split. Threshold
$p<0.001$ because the check runs on every experiment and false alarms are costly. An SRM means the arms
are no longer exchangeable, so every effect estimate is suspect; the per-segment drill-down usually points at
the cause (a platform, browser or country where one arm loses units). Fabijan et al. (2019),
*Diagnosing Sample Ratio Mismatch in Online Controlled Experiments*.

## 7. Multiple testing - `holm`, `benjamini_hochberg`

* **Holm** controls the family-wise error rate (probability of *any* false positive) under any dependence.
  Use it when one false "win" is costly - e.g. the set of metrics that drives a ship decision.
* **Benjamini-Hochberg** controls the false discovery rate (expected share of false positives among
  discoveries). More power when many metrics have real effects; use it for exploratory metric scans.

## 8. Power analysis - `sample_size_*`, `mde_mean`, `power_mean`

$$n_c = \frac{(z_{1-\alpha/2} + z_{1-\beta})^2\,(1-\rho^2)\,(\sigma_c^2 + \sigma_t^2/k)}{\delta^2}, \qquad n_t = k\,n_c$$

where $k$ is the allocation ratio and $(1-\rho^2)$ plans for CUPED. The validation report confirms that
80%-power designs deliver 79-80% empirical power, including a heavy-tailed revenue metric and a
CUPED-planned design.

## References

- Deng, Xu, Kohavi, Walker (2013). Improving the sensitivity of online controlled experiments by utilizing pre-experiment data. *WSDM*.
- Deng, Knoblich, Lu (2018). Applying the delta method in metric analytics. *KDD*.
- Lin (2013). Agnostic notes on regression adjustments to experimental data. *Annals of Applied Statistics*.
- Johari, Koomen, Pekelis, Walsh (2017). Peeking at A/B tests. *KDD*; (2022) Always valid inference. *Operations Research*.
- Howard, Ramdas, McAuliffe, Sekhon (2021). Time-uniform, nonparametric, nonasymptotic confidence sequences. *Annals of Statistics*.
- Fabijan et al. (2019). Diagnosing sample ratio mismatch in online controlled experiments. *KDD*.
- Kohavi, Tang, Xu (2020). *Trustworthy Online Controlled Experiments*. Cambridge University Press.
- Tang et al. (2020). Control using predictions as covariates (CUPAC). DoorDash engineering.
- Holm (1979); Benjamini, Hochberg (1995).
