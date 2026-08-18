"""Independent invariants and provenance helpers for the official Q1 run."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import Counter
from hashlib import sha256
from pathlib import Path
import platform

import matplotlib
import numpy as np
import pandas as pd
import scipy

from interpolation_10hz import MergeDiagnostics
from data_loader import TrajectorySamples
from time_alignment import AlignmentResult


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    output_step_max_error_s: float
    output_finite: bool
    aligned_rmse_threshold_m: float
    common_timestamp_groups: int
    common_timestamp_max_disagreement_m: float
    optimum_boundary_distance_s: float
    independent_exact_match_count: int
    independent_offset_s: float
    independent_offset_error_s: float

    def to_dict(self) -> dict:
        return asdict(self)


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "matplotlib": matplotlib.__version__,
    }


def validate_official_output(
    stream1: TrajectorySamples,
    stream2: TrajectorySamples,
    result: AlignmentResult,
    merge: MergeDiagnostics,
    trajectory: pd.DataFrame,
    *,
    expected_hz: float = 10.0,
    rmse_threshold_m: float = 1e-6,
) -> ValidationReport:
    values = trajectory[["time", "x", "y"]].to_numpy(dtype=float)
    finite = bool(np.isfinite(values).all())
    step_error = float(
        np.max(np.abs(np.diff(trajectory["time"].to_numpy()) - 1.0 / expected_hz))
    )

    # Independent baseline: coordinates recorded at the same true instant are
    # exactly equal in this noiseless attachment.  Their raw clock differences
    # recover the offset without interpolation or numerical optimization.
    time_by_coordinate = {
        (float(x), float(y)): float(t)
        for t, (x, y) in zip(stream1.time, stream1.xy, strict=True)
    }
    exact_offsets = [
        round(time_by_coordinate[(float(x), float(y))] - float(t), 10)
        for t, (x, y) in zip(stream2.time, stream2.xy, strict=True)
        if (float(x), float(y)) in time_by_coordinate
    ]
    if not exact_offsets:
        raise AssertionError("Q1 independent validation found no exact coordinate matches.")
    offset_counts = Counter(exact_offsets)
    independent_offset, independent_count = offset_counts.most_common(1)[0]
    independent_error = abs(float(independent_offset) - result.time_offset_s)

    checks = {
        "finite output": finite,
        "strictly increasing 10 Hz time": step_error <= 2e-10,
        "noiseless alignment RMSE": result.loss.rmse <= rmse_threshold_m,
        "interior optimum": result.boundary_distance_s > 1.0,
        "common timestamps found": merge.duplicate_groups > 0,
        "common coordinates agree": merge.max_duplicate_disagreement_m <= 1e-8,
        "no unsupported time gap": merge.max_time_gap_s <= 0.25 + 1e-8,
        "independent exact matches": independent_count >= 10,
        "independent offset agreement": independent_error <= 1e-7,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError("Q1 validation failed: " + ", ".join(failed))

    return ValidationReport(
        passed=True,
        output_step_max_error_s=step_error,
        output_finite=finite,
        aligned_rmse_threshold_m=rmse_threshold_m,
        common_timestamp_groups=merge.duplicate_groups,
        common_timestamp_max_disagreement_m=merge.max_duplicate_disagreement_m,
        optimum_boundary_distance_s=result.boundary_distance_s,
        independent_exact_match_count=int(independent_count),
        independent_offset_s=float(independent_offset),
        independent_offset_error_s=float(independent_error),
    )
