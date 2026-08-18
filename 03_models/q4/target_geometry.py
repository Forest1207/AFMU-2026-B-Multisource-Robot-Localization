"""Target definitions and robot-target geometry for Q4."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from trajectory_state import TrajectoryState


@dataclass(frozen=True)
class Target:
    target_id: str
    x: float
    y: float
    task_type: str


@dataclass(frozen=True)
class TargetGeometry:
    target: Target
    distance: np.ndarray
    bearing_rad: np.ndarray
    bearing_deg: np.ndarray


def normalize_task_type(value: object) -> str:
    text = str(value).strip().lower()
    mapping = {
        "shoot": "shoot", "shooting": "shoot", "射击": "shoot",
        "photo": "photo", "photography": "photo", "拍照": "photo", "摄影": "photo",
    }
    if text not in mapping:
        raise ValueError(f"unknown task type: {value!r}")
    return mapping[text]


def read_targets(
    workbook: str | Path,
    sheet_name: str | int = 0,
    id_col: str = "目标编号",
    x_col: str = "X坐标(m)",
    y_col: str = "Y坐标(m)",
    type_col: str = "任务类型",
    default_task_type: str | None = None,
) -> list[Target]:
    """Read target points from Excel with configurable column names.

    ``default_task_type`` allows one sheet to contain only shooting or only
    photography targets without an explicit task-type column.
    """
    path = Path(workbook)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_excel(path, sheet_name=sheet_name)
    required = [id_col, x_col, y_col]
    if default_task_type is None:
        required.append(type_col)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing target columns {missing}; actual={list(df.columns)}")

    out: list[Target] = []
    fallback = normalize_task_type(default_task_type) if default_task_type else None
    for _, row in df.iterrows():
        try:
            x = float(row[x_col])
            y = float(row[y_col])
        except (TypeError, ValueError):
            continue
        if not np.isfinite(x) or not np.isfinite(y):
            continue
        task_type = fallback if fallback is not None else normalize_task_type(row[type_col])
        out.append(Target(str(row[id_col]), x, y, task_type))
    if not out:
        raise ValueError("no valid targets were loaded")
    return out


def compute_geometry(state: TrajectoryState, target: Target) -> TargetGeometry:
    dx = target.x - state.x
    dy = target.y - state.y
    distance = np.hypot(dx, dy)
    bearing = np.mod(np.arctan2(dy, dx), 2.0 * np.pi)
    return TargetGeometry(
        target=target,
        distance=distance,
        bearing_rad=bearing,
        bearing_deg=np.degrees(bearing),
    )


def compute_all_geometry(
    state: TrajectoryState, targets: list[Target]
) -> dict[str, TargetGeometry]:
    ids = [t.target_id for t in targets]
    if len(ids) != len(set(ids)):
        raise ValueError("target_id must be unique")
    return {t.target_id: compute_geometry(state, t) for t in targets}


def circular_angle_difference_deg(a: float, b: float) -> float:
    """Smallest circular angular difference in degrees, in [0, 180]."""
    delta = abs((float(a) - float(b)) % 360.0)
    return min(delta, 360.0 - delta)
