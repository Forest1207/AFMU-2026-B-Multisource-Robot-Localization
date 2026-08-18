"""Configurable Excel loader for Q2 positioning streams."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TrajectorySamples:
    name: str
    time: np.ndarray
    xy: np.ndarray

    def validate(self) -> None:
        if self.time.ndim != 1:
            raise ValueError(f"{self.name}: time must be 1-D.")
        if self.xy.shape != (self.time.size, 2):
            raise ValueError(f"{self.name}: xy must have shape (n, 2).")
        if self.time.size < 4:
            raise ValueError(f"{self.name}: at least four samples are required.")
        if np.any(~np.isfinite(self.time)) or np.any(~np.isfinite(self.xy)):
            raise ValueError(f"{self.name}: non-finite values found.")
        if np.any(np.diff(self.time) <= 0):
            raise ValueError(f"{self.name}: timestamps must be strictly increasing.")


def read_stream(
    workbook: str | Path,
    sheet_name: str,
    time_col: str = "时间(s)",
    x_col: str = "X坐标(m)",
    y_col: str = "Y坐标(m)",
) -> TrajectorySamples:
    """Read one trajectory stream from an Excel sheet.

    Column names are configurable because Q2 should not depend on one fixed
    attachment schema. Duplicate timestamps are averaged after numeric
    conversion.
    """
    path = Path(workbook)
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_excel(path, sheet_name=sheet_name)
    required = [time_col, x_col, y_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{sheet_name}: missing columns {missing}; actual={list(df.columns)}"
        )

    df = df[required].copy()
    for c in required:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna().sort_values(time_col, kind="mergesort")
    if df.empty:
        raise ValueError(f"{sheet_name}: no valid numeric rows remain.")

    # Average duplicate timestamps rather than silently keeping an arbitrary row.
    df = df.groupby(time_col, as_index=False)[[x_col, y_col]].mean()
    samples = TrajectorySamples(
        name=sheet_name,
        time=df[time_col].to_numpy(dtype=float),
        xy=df[[x_col, y_col]].to_numpy(dtype=float),
    )
    samples.validate()
    return samples


def load_two_streams(
    workbook: str | Path,
    sheet1: str,
    sheet2: str,
    time_col: str = "时间(s)",
    x_col: str = "X坐标(m)",
    y_col: str = "Y坐标(m)",
) -> tuple[TrajectorySamples, TrajectorySamples]:
    """Read the two positioning streams used by Q2."""
    s1 = read_stream(workbook, sheet1, time_col, x_col, y_col)
    s2 = read_stream(workbook, sheet2, time_col, x_col, y_col)
    return s1, s2
