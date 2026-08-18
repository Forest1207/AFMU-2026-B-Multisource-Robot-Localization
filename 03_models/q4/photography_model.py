"""Photography-task constants, margins and circular-angle distance."""

from __future__ import annotations

import numpy as np

TASK_NAME = "拍照"
PREPARATION_S = 0.5
DISTANCE_MIN_M = 10.0
DISTANCE_MAX_M = 40.0
SPEED_MAX_MPS = 1.5
ACCELERATION_MAX_MPS2 = 1.5
MIN_ANGLE_SEPARATION_DEG = 60.0


def normalized_margin(distance: np.ndarray, speed: np.ndarray,
                      acceleration: np.ndarray) -> np.ndarray:
    return np.minimum.reduce([
        (distance - DISTANCE_MIN_M) / (DISTANCE_MAX_M - DISTANCE_MIN_M),
        (DISTANCE_MAX_M - distance) / (DISTANCE_MAX_M - DISTANCE_MIN_M),
        (SPEED_MAX_MPS - speed) / SPEED_MAX_MPS,
        (ACCELERATION_MAX_MPS2 - acceleration) / ACCELERATION_MAX_MPS2,
    ])


def circular_separation_deg(angle_a: float, angle_b: float) -> float:
    raw = abs(float(angle_a) - float(angle_b)) % 360.0
    return min(raw, 360.0 - raw)
