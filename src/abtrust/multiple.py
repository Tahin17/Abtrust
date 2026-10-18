"""Multiple-testing corrections for readouts with many metrics or arms.

With 20 independent null metrics tested at alpha = 0.05, the chance that at least
one looks "significant" is 1 - 0.95**20 = 64%. Holm controls the family-wise error
rate (probability of any false positive); Benjamini-Hochberg controls the false
discovery rate (expected share of false positives among discoveries).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

__all__ = ["holm", "benjamini_hochberg", "adjust"]


def _pvals(p: ArrayLike) -> np.ndarray:
    arr = np.asarray(p, dtype=float).ravel()
    if np.any((arr < 0) | (arr > 1)) or not np.all(np.isfinite(arr)):
        raise ValueError("p-values must be finite numbers in [0, 1]")
    return arr


def holm(p_values: ArrayLike) -> np.ndarray:
    """Holm step-down adjusted p-values (controls family-wise error rate)."""
    p = _pvals(p_values)
    m = p.size
    if m == 0:
        return p
    order = np.argsort(p)
    scaled = (m - np.arange(m)) * p[order]
    adjusted_sorted = np.minimum(np.maximum.accumulate(scaled), 1.0)
    out = np.empty(m)
    out[order] = adjusted_sorted
    return out


def benjamini_hochberg(p_values: ArrayLike) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (controls false discovery rate)."""
    p = _pvals(p_values)
    m = p.size
    if m == 0:
        return p
    order = np.argsort(p)
    scaled = p[order] * m / np.arange(1, m + 1)
    adjusted_sorted = np.minimum(np.minimum.accumulate(scaled[::-1])[::-1], 1.0)
    out = np.empty(m)
    out[order] = adjusted_sorted
    return out


def adjust(p_values: ArrayLike, method: str = "holm") -> np.ndarray:
    """Dispatch by name: ``"holm"``, ``"bh"`` or ``"none"``."""
    method = method.lower()
    if method == "holm":
        return holm(p_values)
    if method in {"bh", "fdr", "benjamini-hochberg"}:
        return benjamini_hochberg(p_values)
    if method == "none":
        return _pvals(p_values).copy()
    raise ValueError(f"unknown correction method {method!r}; use 'holm', 'bh' or 'none'")
