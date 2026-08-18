"""Shooting-task constants and normalized feasibility margin."""

from __future__ import annotations

import numpy as np

TASK_NAME = "射击"
PREPARATION_S = 1.5
DISTANCE_MIN_M = 5.0
DISTANCE_MAX_M = 30.0
SPEED_MAX_MPS = 2.0
ACCELERATION_MAX_MPS2 = 1.5
HIT_PROBABILITY = 0.85


def normalized_margin(distance: np.ndarray, speed: np.ndarray,
                      acceleration: np.ndarray) -> np.ndarray:
    return np.minimum.reduce([
        (distance - DISTANCE_MIN_M) / (DISTANCE_MAX_M - DISTANCE_MIN_M),
        (DISTANCE_MAX_M - distance) / (DISTANCE_MAX_M - DISTANCE_MIN_M),
        (SPEED_MAX_MPS - speed) / SPEED_MAX_MPS,
        (ACCELERATION_MAX_MPS2 - acceleration) / ACCELERATION_MAX_MPS2,
    ])
