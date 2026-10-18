"""Shared scalar checks for public numerical APIs."""

from __future__ import annotations

import math
from numbers import Integral, Real


def finite_scalar(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


def positive_scalar(value: float, name: str) -> float:
    value = finite_scalar(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def positive_integer(value: int, name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)
