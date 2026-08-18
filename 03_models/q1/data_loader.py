"""Data loading and validation for Q1 (附件1.xlsx)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


TIME_COL = "时间(s)"
X_COL = "X坐标(m)"
Y_COL = "Y坐标(m)"
SHEET1 = "方式1(4Hz)"
SHEET2 = "方式2(5Hz)"


@dataclass(frozen=True)
class TrajectorySamples:
    """One positioning stream sampled on its own device clock."""

    name: str
    time: np.ndarray
    xy: np.ndarray
    nominal_rate_hz: float

    @property
    def start(self) -> float:
        return float(self.time[0])

    @property
    def end(self) -> float:
        return float(self.time[-1])

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def n(self) -> int:
        return int(self.time.size)

    def validate(self) -> None:
        if self.time.ndim != 1:
            raise ValueError(f"{self.name}: time must be 1-D.")
        if self.xy.shape != (self.time.size, 2):
            raise ValueError(f"{self.name}: xy must have shape (n, 2).")
        if self.time.size < 4:
            raise ValueError(f"{self.name}: too few samples.")
        if not np.all(np.isfinite(self.time)) or not np.all(np.isfinite(self.xy)):
            raise ValueError(f"{self.name}: non-finite values found.")
        dt = np.diff(self.time)
        if not np.all(dt > 0):
            raise ValueError(f"{self.name}: timestamps must be strictly increasing.")

        nominal_dt = 1.0 / self.nominal_rate_hz
        max_clock_error = float(np.max(np.abs(dt - nominal_dt)))
        if max_clock_error > 1e-6:
            raise ValueError(
                f"{self.name}: sampling interval is not {nominal_dt:g}s; "
                f"max deviation={max_clock_error:.3e}s."
            )


def _read_stream(
    path: str | Path,
    sheet_name: str,
    nominal_rate_hz: float,
) -> TrajectorySamples:
    df = pd.read_excel(path, sheet_name=sheet_name)
    missing = [c for c in (TIME_COL, X_COL, Y_COL) if c not in df.columns]
    if missing:
        raise ValueError(
            f"{sheet_name}: missing columns {missing}; actual columns={list(df.columns)}"
        )

    df = df[[TIME_COL, X_COL, Y_COL]].copy()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df.isna().any().any():
        bad_rows = df.index[df.isna().any(axis=1)].tolist()[:10]
        raise ValueError(f"{sheet_name}: invalid numeric rows, examples={bad_rows}")

    df = df.sort_values(TIME_COL, kind="mergesort").reset_index(drop=True)
    samples = TrajectorySamples(
        name=sheet_name,
        time=df[TIME_COL].to_numpy(dtype=float),
        xy=df[[X_COL, Y_COL]].to_numpy(dtype=float),
        nominal_rate_hz=nominal_rate_hz,
    )
    samples.validate()
    return samples


def load_attachment1(path: str | Path) -> tuple[TrajectorySamples, TrajectorySamples]:
    """Load the two Q1 streams from the exact workbook schema used by 附件1.xlsx."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    stream1 = _read_stream(path, SHEET1, nominal_rate_hz=4.0)
    stream2 = _read_stream(path, SHEET2, nominal_rate_hz=5.0)
    return stream1, stream2
