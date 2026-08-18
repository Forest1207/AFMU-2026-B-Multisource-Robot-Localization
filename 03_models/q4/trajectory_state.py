"""Load and continuously evaluate the fixed Q3 trajectory for Q4."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


REQUIRED_COLUMNS = ["time_s", "x", "y", "vx", "vy", "ax", "ay"]


@dataclass(frozen=True)
class TrajectoryState:
    frame: pd.DataFrame

    @classmethod
    def load(cls, path: str | Path) -> "TrajectoryState":
        frame = pd.read_csv(path)
        missing = [column for column in REQUIRED_COLUMNS if column not in frame]
        if missing:
            raise ValueError(f"Trajectory is missing columns: {missing}")
        values = frame[REQUIRED_COLUMNS].to_numpy(dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError("Trajectory contains non-finite state values.")
        time = values[:, 0]
        if time.size < 2 or not np.all(np.diff(time) > 0):
            raise ValueError("Trajectory time must be strictly increasing.")
        if np.max(np.abs(np.diff(time) - 0.1)) > 1e-8:
            raise ValueError("Q4 requires the official 10 Hz Q3 trajectory.")
        return cls(frame=frame.copy())

    @property
    def time(self) -> np.ndarray:
        return self.frame["time_s"].to_numpy(dtype=float)

    def evaluate(self, query_time: np.ndarray) -> dict[str, np.ndarray]:
        query = np.asarray(query_time, dtype=float)
        if np.any(query < self.time[0] - 1e-10) or np.any(query > self.time[-1] + 1e-10):
            raise ValueError("Continuous trajectory query would extrapolate.")
        result: dict[str, np.ndarray] = {}
        for column in ("x", "y", "vx", "vy", "ax", "ay"):
            interpolator = PchipInterpolator(
                self.time, self.frame[column].to_numpy(dtype=float), extrapolate=False
            )
            result[column] = np.asarray(interpolator(query), dtype=float)
        result["speed"] = np.hypot(result["vx"], result["vy"])
        result["acceleration"] = np.hypot(result["ax"], result["ay"])
        return result
