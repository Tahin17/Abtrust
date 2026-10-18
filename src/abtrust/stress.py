"""Supplemental synthetic stress studies; separate from the seven core studies.

These experiments diagnose specific assumptions. Deliberately selected treatment
data demonstrate failure, rather than supplying evidence for valid inference.
"""

from __future__ import annotations

import hashlib
import inspect
import time

import numpy as np
import pandas as pd

from ._inputs import positive_integer
from .estimators import cuped, lin_adjustment, welch_ttest
from .provenance import runtime_provenance, utc_now
from .sequential import sequential_test, tau_from_design
from .validation import StudyResult


def study_fixed_stress(n_sims: int = 2000, seed: int = 101, n_control: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for scenario in ("correlated covariates", "unequal allocation", "rare conversion", "constant outcomes",
                     "selected treatment outcomes (INVALID)"):
        ratio = 4 if scenario == "unequal allocation" else 1
        n_treatment = ratio * n_control
        for alternative in (False, True):
            # Use an exactly representable binary fraction for the deterministic
            # fixture, so floating-point rounding is not mistaken for CI failure.
            effect = (0.001 if scenario == "rare conversion" else
                      0.125 if scenario == "constant outcomes" else 0.1) if alternative else 0.0
            names = ["welch"] if scenario in {"rare conversion", "constant outcomes"} else ["welch", "cuped", "lin_hc2"]
            values = {name: {"reject": 0, "cover": 0, "effect": [], "se": []} for name in names}
            used_t = []
            for _ in range(n_sims):
                xc = rng.normal(size=(n_control, 2))
                xt = rng.normal(size=(n_treatment, 2))
                for x in (xc, xt):
                    x[:, 1] = 0.8 * x[:, 0] + 0.6 * x[:, 1]
                yc = 10 + xc[:, 0] + 0.2 * (xc[:, 1]**2 - 1) + rng.normal(size=n_control)
                yt = 10 + effect + xt[:, 0] + 0.2 * (xt[:, 1]**2 - 1) + rng.normal(0, 1.5, n_treatment)
                if scenario == "rare conversion":
                    yc = rng.binomial(1, 0.002, n_control)
                    yt = rng.binomial(1, 0.002 + effect, n_treatment)
                elif scenario == "constant outcomes":
                    yc, yt = np.full(n_control, 10.0), np.full(n_treatment, 10 + effect)
                elif scenario.startswith("selected"):
                    keep = yt >= np.quantile(yt, 0.2)
                    yt, xt = yt[keep], xt[keep]
                used_t.append(len(yt))
                estimates = {"welch": welch_ttest(yc, yt)}
                if "cuped" in names:
                    estimates["cuped"] = cuped(yc, yt, xc[:, 0], xt[:, 0])
                    estimates["lin_hc2"] = lin_adjustment(np.r_[yc, yt], np.r_[np.zeros(len(yc)), np.ones(len(yt))],
                                                          np.vstack([xc, xt]))
                for name, estimate in estimates.items():
                    v = values[name]
                    v["reject"] += estimate.p_value < 0.05
                    v["cover"] += estimate.ci_low <= effect <= estimate.ci_high
                    v["effect"].append(estimate.effect)
                    v["se"].append(estimate.se)
            for name, v in values.items():
                rate, coverage = v["reject"] / n_sims, v["cover"] / n_sims
                rows.append({"scenario": scenario, "method": name, "true_effect": effect,
                             "measure": "power" if alternative else "false_positive_rate",
                             "rejection_rate": rate, "rejection_mcse": np.sqrt(rate * (1 - rate) / n_sims),
                             "coverage": coverage, "coverage_mcse": np.sqrt(coverage * (1 - coverage) / n_sims),
                             "bias": np.mean(v["effect"]) - effect, "mean_se": np.mean(v["se"]),
                             "n_control": n_control, "mean_complete_treatment": np.mean(used_t),
                             "n_sims": n_sims})
    table = pd.DataFrame(rows)
    table.attrs["design"] = {"alpha": 0.05, "baseline_conversion": 0.002,
                             "covariate_correlation": 0.8, "noise_sd_control": 1, "noise_sd_treatment": 1.5,
                             "continuous_effect": 0.1, "binary_effect": 0.001,
                             "deterministic_effect": 0.125,
                             "selection": "remove the lowest 20% of treatment outcomes in the INVALID scenario",
                             "constant_outcomes": "deterministic fixture; not evidence for rare-outcome interval validity"}
    return table


def study_gaussian_stress(n_sims: int = 2000, seed: int = 102, n_per_arm: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sd_c, sd_t = 1.0, 1.5
    tau = tau_from_design(sd_c, n_per_arm, sd_treatment=sd_t)
    rows = []
    for effect in (0.0, 0.2):
        hits = {k: 0 for k in (1, 20, 100)}
        coverage = dict.fromkeys(hits, 0)
        fractions = {k: [] for k in hits}
        for _ in range(n_sims):
            c, t = rng.normal(0, sd_c, n_per_arm), rng.normal(effect, sd_t, n_per_arm)
            for k in hits:
                result = sequential_test(c, t, looks=k, mode="gaussian_known_sd", known_sd=(sd_c, sd_t), tau=tau)
                stop = result.stop_index
                hits[k] += stop is not None
                coverage[k] += result.final.ci_low <= effect <= result.final.ci_high
                fractions[k].append(1.0 if stop is None else result.looks[stop].n_control / n_per_arm)
        for k in hits:
            rate, cov = hits[k] / n_sims, coverage[k] / n_sims
            rows.append({"mode": "gaussian_known_sd", "true_effect": effect, "looks": k,
                         "measure": "power" if effect else "false_positive_rate", "rejection_rate": rate,
                         "rejection_mcse": np.sqrt(rate * (1 - rate) / n_sims), "simultaneous_coverage": cov,
                         "coverage_mcse": np.sqrt(cov * (1 - cov) / n_sims),
                         "mean_sample_fraction": np.mean(fractions[k]), "n_per_arm": n_per_arm, "tau": tau,
                         "n_sims": n_sims})
    table = pd.DataFrame(rows)
    table.attrs["design"] = {"alpha": 0.05, "known_sd_control": sd_c, "known_sd_treatment": sd_t,
                             "tau": tau, "effects": [0, 0.2], "looks": [1, 20, 100],
                             "assumptions": "independent Gaussian arrivals; equal arm sizes; SD and tau fixed before outcomes"}
    return table


def run_stress(n_sims: int = 2000) -> dict[str, StudyResult]:
    n_sims = positive_integer(n_sims, "n_sims", minimum=50)
    runtime = runtime_provenance()
    results = {}
    for name, function, question, headline in (
        ("stress_fixed", study_fixed_stress, "How do fixed-horizon methods behave near their limits?",
         "Synthetic diagnostics only. Selected treatment outcomes deliberately violate randomization; inspect bias and coverage."),
        ("stress_gaussian", study_gaussian_stress, "How does the known-SD Gaussian procedure behave across monitoring schedules?",
         "Synthetic calibration under genuinely known Gaussian SDs and a prespecified mixture scale."),
    ):
        started = utc_now()
        timer = time.perf_counter()
        table = function(n_sims=n_sims)
        bound = inspect.signature(function).bind_partial(n_sims=n_sims)
        bound.apply_defaults()
        metadata = {"simulated_at_utc": started, "runtime": runtime, "parameters": dict(bound.arguments),
                    "implementation_sha256": hashlib.sha256(inspect.getsource(function).encode("utf-8")).hexdigest(),
                    "scenario_configuration": table.attrs["design"]}
        results[name] = StudyResult(name, question, table, headline, time.perf_counter() - timer, metadata)
    return results
