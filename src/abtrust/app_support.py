"""Pure, easily testable helpers for the Streamlit UI.

Keeping CSV and design validation outside the UI makes failure modes testable
without launching a real browser. None of these helpers mutates source data.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_UPLOAD_ROWS = 1_000_000


def load_uploaded_csv(data: bytes, *, max_bytes: int = MAX_UPLOAD_BYTES) -> pd.DataFrame:
    """Parse a user CSV or raise a readable error, instead of crashing the page."""
    if not data:
        raise ValueError("CSV is empty. Upload a file with a header and data rows.")
    if len(data) > max_bytes:
        raise ValueError(f"CSV exceeds the {max_bytes // 1024 // 1024} MB upload limit.")
    try:
        # pandas silently renames duplicate CSV headers (e.g. revenue -> revenue.1).
        # Catch the original problem before pandas changes the schema.
        reader = csv.reader(io.TextIOWrapper(io.BytesIO(data), encoding="utf-8-sig"))
        headers = next(reader)
        if len(headers) != len(set(headers)):
            raise ValueError("CSV has duplicate header names; rename them before analysis.")
        if any(not header.strip() for header in headers):
            raise ValueError("CSV has a blank header name.")
        frame = pd.read_csv(io.BytesIO(data), nrows=MAX_UPLOAD_ROWS + 1, encoding="utf-8-sig")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError, ValueError, StopIteration, csv.Error) as exc:
        raise ValueError(f"Unable to read CSV: {exc}") from exc
    if len(frame) > MAX_UPLOAD_ROWS:
        raise ValueError(f"CSV has more than {MAX_UPLOAD_ROWS:,} rows. Use the CLI for larger datasets.")
    validate_table(frame)
    return frame


def validate_table(df: pd.DataFrame) -> None:
    """Basic shape/schema checks; ``analyze()`` checks units and outcomes further."""
    if df.empty:
        raise ValueError("CSV contains no data rows.")
    if len(df.columns) < 2:
        raise ValueError("CSV needs an arm column and at least one outcome column.")
    if df.columns.duplicated().any():
        raise ValueError("CSV has duplicate column names; rename them before analyzing.")
    if any(not str(col).strip() for col in df.columns):
        raise ValueError("CSV has a blank column name.")
    if not any(pd.api.types.is_numeric_dtype(df[c]) for c in df.columns):
        raise ValueError("CSV needs at least one numeric outcome column.")


def arm_labels(df: pd.DataFrame, column: str) -> list[str]:
    """Return supported arm labels or raise an actionable message."""
    if df[column].isna().any():
        raise ValueError(f"Arm column {column!r} has missing labels.")
    labels = sorted(df[column].astype(str).unique().tolist())
    if len(labels) < 2:
        raise ValueError(f"Arm column {column!r} needs at least two distinct groups.")
    if len(labels) > 20:
        raise ValueError("Too many arm labels for the dashboard; use the Python API for large multi-arm studies.")
    return labels


def expected_split_from_percentages(arms: Sequence[str], percentages: Mapping[str, float]) -> dict[str, float]:
    """Validate *design-time* percentages; never infer them from observed counts.

    A strict 100% requirement avoids silently renormalizing mistyped allocations.
    """
    if set(arms) != set(percentages) or len(arms) < 2:
        raise ValueError("Provide a designed allocation for every arm.")
    vals = np.asarray([percentages[a] for a in arms], dtype=float)
    if not np.isfinite(vals).all() or (vals <= 0).any() or (vals > 100).any():
        raise ValueError("All allocation percentages must be finite and greater than zero.")
    if not np.isclose(vals.sum(), 100, rtol=0, atol=0.01):
        raise ValueError(f"Designed allocation totals {vals.sum():.2f}%, but must total 100%.")
    return {a: float(v / 100) for a, v in zip(arms, vals, strict=True)}


def parse_harm_margin(value: str, metric: str) -> float | None:
    """A blank means safety not assessed, never zero permissible harm."""
    if not value.strip():
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"{metric}: provide a numeric absolute harm margin, for example 0.001.") from exc
    if not np.isfinite(number) or number < 0:
        raise ValueError(f"{metric}: harm margin must be finite and nonnegative.")
    return number
