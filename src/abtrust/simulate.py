"""Synthetic data generators with known ground truth.

They power the Monte Carlo validation suite and the case study. Every generator
takes a ``numpy.random.Generator`` so results are reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = [
    "zero_inflated_lognormal",
    "pre_post_normal",
    "sessions_clicks",
    "EcommerceTruth",
    "ecommerce_experiment",
]


def zero_inflated_lognormal(
    rng: np.random.Generator,
    size: int | tuple[int, ...],
    p_purchase: float = 0.08,
    mu: float = 3.5,
    sigma: float = 1.2,
    multiplier: float = 1.0,
) -> np.ndarray:
    """Revenue-like metric: most users spend 0, buyers spend a heavy-tailed amount.

    ``multiplier`` scales spend among buyers (a multiplicative treatment effect).
    """
    buys = rng.random(size) < p_purchase
    return np.where(buys, multiplier * rng.lognormal(mu, sigma, size), 0.0)


def pre_post_normal(
    rng: np.random.Generator, n: int, rho: float, effect: float = 0.0, sd: float = 1.0, mean: float = 10.0
) -> tuple[np.ndarray, np.ndarray]:
    """Pre-period covariate ``x`` and outcome ``y`` with ``corr(x, y) = rho``."""
    if not -1 < rho < 1:
        raise ValueError("rho must be in (-1, 1)")
    x = rng.standard_normal(n)
    e = rng.standard_normal(n)
    y = mean + effect + sd * (rho * x + np.sqrt(1 - rho**2) * e)
    return mean + sd * x, y


def sessions_clicks(
    rng: np.random.Generator,
    n_users: int,
    ctr: float = 0.10,
    icc: float = 0.10,
    mean_sessions: float = 6.0,
    lift: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-user (clicks, sessions) where sessions of the same user are correlated.

    Each user has a personal click-through rate drawn from a Beta distribution whose
    intra-class correlation is ``icc``; heavy users (many sessions) are common. With
    ``icc = 0`` sessions are independent and per-session analysis would be valid.
    """
    if not 0 <= icc < 1:
        raise ValueError("icc must be in [0, 1)")
    sessions = 1 + rng.negative_binomial(2, 2 / (2 + mean_sessions - 1), n_users)
    p = ctr * (1 + lift)
    if icc == 0:
        user_ctr = np.full(n_users, p)
    else:
        k = 1 / icc - 1  # Beta(a, b) with a + b = k has ICC 1 / (k + 1)
        user_ctr = rng.beta(p * k, (1 - p) * k, n_users)
    clicks = rng.binomial(sessions, user_ctr)
    return clicks.astype(float), sessions.astype(float)


@dataclass
class EcommerceTruth:
    """Population-level true effects of the simulated checkout redesign."""

    conversion_ate: float
    conversion_rel: float
    revenue_ate: float
    revenue_rel: float
    orders_per_session_rel: float
    null_metrics: list[str] = field(default_factory=list)


def ecommerce_experiment(
    n_users: int = 200_000,
    seed: int = 2026,
    lift: float = 0.04,
    legacy_logging_loss: float = 0.6,
    n_null_metrics: int = 12,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, EcommerceTruth]]:
    """A two-week checkout-redesign experiment with planted analysis traps.

    Returns ``(logged, full, truth)``:

    * ``full`` - every randomized user, as the experiment really happened.
    * ``logged`` - what the analytics pipeline captured: a JavaScript error on the
      ``android_legacy`` platform drops ``legacy_logging_loss`` of *treatment*
      users from the exposure log. Those users buy less than average, so the
      logged treatment arm looks better than it is (classic SRM-induced bias).
    * ``truth`` - exact population effects computed from the latent variables, for
      all users and for the population without ``android_legacy``.

    The redesign multiplies each user's per-session purchase probability by
    ``1 + lift``; sessions, order values and ``n_null_metrics`` engagement metrics
    are unaffected.
    """
    rng = np.random.default_rng(seed)
    platform = rng.choice(["web", "ios", "android", "android_legacy"], size=n_users, p=[0.55, 0.25, 0.15, 0.05])
    variant = np.where(rng.random(n_users) < 0.5, "treatment", "control")
    treated = variant == "treatment"
    enroll_order = rng.permutation(n_users)

    activity = rng.gamma(shape=2.0, scale=2.0, size=n_users)  # expected sessions in 14 days
    buy_q = rng.beta(2.0, 30.0, size=n_users)  # per-session purchase probability
    buy_q = np.where(platform == "android_legacy", buy_q * 0.5, buy_q)
    basket = rng.lognormal(3.7, 0.8, size=n_users)  # user's typical order value

    # pre-period (28 days before launch): same user traits, no treatment
    pre_sessions = rng.poisson(activity * 2.0)
    pre_orders = rng.binomial(pre_sessions, buy_q)
    pre_revenue = pre_orders * basket * rng.lognormal(0.0, 0.3, size=n_users)

    q_eff = np.clip(buy_q * np.where(treated, 1 + lift, 1.0), 0, 1)
    sessions = rng.poisson(activity)
    orders = rng.binomial(sessions, q_eff)
    revenue = orders * basket * rng.lognormal(0.0, 0.3, size=n_users)
    converted = (orders > 0).astype(int)

    data = {
        "user_id": np.arange(n_users),
        "enroll_order": enroll_order,
        "variant": variant,
        "platform": platform,
        "pre_sessions": pre_sessions,
        "pre_revenue": np.round(pre_revenue, 2),
        "sessions": sessions,
        "orders": orders,
        "converted": converted,
        "revenue": np.round(revenue, 2),
        "unsubscribed": (rng.random(n_users) < 0.004).astype(int),
        "support_contact": (rng.random(n_users) < 0.012 + 0.002 * (sessions > 8)).astype(int),
    }
    null_names = []
    for k in range(n_null_metrics):
        name = f"engagement_{k + 1:02d}"
        rate = rng.uniform(0.05, 0.6)
        data[name] = rng.poisson(activity * rate)
        null_names.append(name)
    full = pd.DataFrame(data).sort_values("enroll_order").reset_index(drop=True)

    lost = treated & (platform == "android_legacy") & (rng.random(n_users) < legacy_logging_loss)
    logged = full[~lost[full["user_id"].to_numpy()]].reset_index(drop=True)

    # exact expected outcomes under each potential outcome (Poisson sessions)
    q0, q1 = buy_q, np.clip(buy_q * (1 + lift), 0, 1)
    conv0, conv1 = 1 - np.exp(-activity * q0), 1 - np.exp(-activity * q1)
    mean_basket = basket * np.exp(0.3**2 / 2)
    rev0, rev1 = activity * q0 * mean_basket, activity * q1 * mean_basket

    def _truth(sel: np.ndarray) -> EcommerceTruth:
        return EcommerceTruth(
            conversion_ate=float(np.mean(conv1[sel] - conv0[sel])),
            conversion_rel=float(conv1[sel].mean() / conv0[sel].mean() - 1),
            revenue_ate=float(np.mean(rev1[sel] - rev0[sel])),
            revenue_rel=float(rev1[sel].mean() / rev0[sel].mean() - 1),
            orders_per_session_rel=float(np.sum(activity[sel] * q1[sel]) / np.sum(activity[sel] * q0[sel]) - 1),
            null_metrics=null_names,
        )

    truth = {
        "all_users": _truth(np.ones(n_users, dtype=bool)),
        "excluding_android_legacy": _truth(platform != "android_legacy"),
    }
    return logged, full, truth
