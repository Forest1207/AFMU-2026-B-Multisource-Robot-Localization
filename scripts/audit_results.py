"""Machine-audit the formal Q1--Q4 result chain and paper assets."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "05_results"
FIGURES = ROOT / "06_figures"
SUBMISSION = ROOT / "08_submission"


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def find_time_column(frame: pd.DataFrame) -> str:
    for name in ("time_s", "时间(s)", "time", "t"):
        if name in frame.columns:
            return name
    raise KeyError(f"No supported time column in {list(frame.columns)}")


def audit_trajectory(path: Path, expected_dt: float = 0.1) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing trajectory: {path}"]
    frame = pd.read_csv(path)
    if frame.empty:
        return [f"empty trajectory: {path}"]
    numeric = frame.select_dtypes(include=[np.number])
    if numeric.empty or not np.all(np.isfinite(numeric.to_numpy(float))):
        errors.append(f"{path}: non-finite numeric values")
    time = pd.to_numeric(frame[find_time_column(frame)], errors="coerce").to_numpy(float)
    if np.any(~np.isfinite(time)):
        return errors + [f"{path}: invalid time values"]
    if np.any(np.diff(time) <= 0):
        errors.append(f"{path}: time is not strictly increasing")
    if len(time) > 1 and abs(float(np.median(np.diff(time))) - expected_dt) > 1e-8:
        errors.append(f"{path}: median dt is not {expected_dt}")
    return errors


def audit_reporting_convention() -> list[str]:
    errors: list[str] = []
    conventions = load_json(RESULTS / "reporting_conventions.json")["time_offset"]
    p1 = load_json(RESULTS / "q1" / "parameters.json")
    p2 = load_json(RESULTS / "q2" / "parameters.json")
    p3 = load_json(RESULTS / "q3" / "parameters.json")
    expected = {
        "q1": float(p1["time_offset_s"]),
        "q2": -float(p2["time_offset_s"]),
        "q3": -float(p3["time_offset_s"]),
    }
    for key, value in expected.items():
        if not math.isclose(float(conventions[key]["delta_s"]), value, rel_tol=0.0, abs_tol=1e-10):
            errors.append(f"reporting convention {key}: delta conversion mismatch")
    if conventions.get("paper_definition") != "t2_aligned = t2 + delta":
        errors.append("reporting convention: unexpected paper definition")
    return errors


def audit_figures() -> list[str]:
    errors: list[str] = []
    for problem in range(1, 5):
        manifest_path = RESULTS / f"q{problem}" / "figure_manifest.json"
        if not manifest_path.is_file():
            errors.append(f"Q{problem}: missing figure_manifest.json")
            continue
        manifest = load_json(manifest_path)
        for item in manifest.get("figures", []):
            stem = item["stem"]
            if "pdf" not in set(item.get("formats", [])):
                errors.append(f"Q{problem}/{stem}: PDF not declared")
                continue
            pdf = FIGURES / f"q{problem}" / f"{stem}.pdf"
            if not pdf.is_file() or pdf.stat().st_size == 0:
                errors.append(f"Q{problem}/{stem}: missing non-empty PDF")
    return errors


def audit_q4() -> list[str]:
    errors: list[str] = []
    params = load_json(RESULTS / "q4" / "parameters.json")
    required = {
        "coverage_count", "selected_task_count", "shooting_count", "photography_count",
        "greedy_coverage_count", "greedy_photography_count", "candidate_generation",
        "continuous_refinement", "total_normalized_margin",
    }
    missing = required - set(params)
    if missing:
        return ["Q4: stale formal result schema; re-run latest Q4. Missing: " + ", ".join(sorted(missing))]

    generation = params.get("candidate_generation", {})
    if not math.isclose(float(generation.get("photo_angle_bin_deg", -1)), 5.0, abs_tol=1e-12):
        errors.append("Q4: formal candidates were not generated with 5-degree photo bearing bins")
    if not math.isclose(float(generation.get("continuous_recheck_step_s", -1)), 0.01, abs_tol=1e-12):
        errors.append("Q4: candidate continuous recheck step is not 0.01 s")

    refinement = params.get("continuous_refinement", {})
    if not math.isclose(float(refinement.get("half_width_s", -1)), 0.1, abs_tol=1e-12):
        errors.append("Q4: continuous refinement half-width is not +/-0.1 s")
    if not math.isclose(float(refinement.get("evaluation_step_s", -1)), 0.01, abs_tol=1e-12):
        errors.append("Q4: continuous refinement evaluation step is not 0.01 s")

    schedule = pd.read_csv(RESULTS / "q4" / "optimized_schedule.csv")
    if len(schedule) != int(params["selected_task_count"]):
        errors.append("Q4: schedule row count mismatch")
    if int(params["shooting_count"]) + int(params["photography_count"]) != len(schedule):
        errors.append("Q4: task-type counts mismatch")
    if not (0 < int(params["coverage_count"]) <= 36):
        errors.append("Q4: coverage_count outside [1,36]")
    if int(params["coverage_count"]) < int(params["greedy_coverage_count"]):
        errors.append("Q4: MILP coverage below greedy baseline")
    if int(params["photography_count"]) < int(params["greedy_photography_count"]):
        errors.append("Q4: MILP photo count below greedy baseline")

    milp = params.get("milp", {})
    if milp.get("artificial_capacity", "legacy") is not None:
        errors.append("Q4: artificial capacity still enabled")
    if milp.get("cross_task_time_mutex", "legacy") is not False:
        errors.append("Q4: cross-task time mutex still enabled")
    for stage in (1, 2, 3):
        gap = milp.get(f"stage{stage}_gap")
        if gap is not None and abs(float(gap)) > 1e-12:
            errors.append(f"Q4: stage{stage} MIP gap={gap}")

    workbook = params.get("result_workbook", {})
    if workbook.get("protected_snapshot_equal") is not True:
        errors.append("Q4: protected template cells changed")
    if workbook.get("filled_rows") != len(schedule):
        errors.append("Q4: workbook did not receive all optimized tasks")
    if not (RESULTS / "q4" / "result.xlsx").is_file():
        errors.append("Q4: result.xlsx missing")
    return errors


def run_audit() -> dict:
    errors: list[str] = []
    for problem in (1, 2, 3):
        errors.extend(audit_trajectory(RESULTS / f"q{problem}" / "trajectory_10hz.csv"))
    errors.extend(audit_reporting_convention())
    errors.extend(audit_figures())
    errors.extend(audit_q4())
    checks = {
        "formal_result_directories": all((RESULTS / f"q{i}").is_dir() for i in range(1, 5)),
        "reporting_convention_present": (RESULTS / "reporting_conventions.json").is_file(),
        "q4_result_workbook_present": (RESULTS / "q4" / "result.xlsx").is_file(),
        "paper_source_present": (ROOT / "07_paper" / "latex" / "main.tex").is_file(),
    }
    errors.extend(f"missing required artifact: {label}" for label, passed in checks.items() if not passed)
    return {"passed": not errors, "error_count": len(errors), "errors": errors, "checks": checks}


def write_report(report: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "audit_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Submission Audit Report", "",
        f"- status: **{'PASS' if report['passed'] else 'FAIL'}**",
        f"- error count: **{report['error_count']}**", "", "## Checks", "",
    ]
    lines += [f"- {'PASS' if passed else 'FAIL'} `{label}`" for label, passed in report["checks"].items()]
    lines += ["", "## Errors", ""] + ([f"- {e}" for e in report["errors"]] if report["errors"] else ["- None"])
    (output_dir / "audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=SUBMISSION / "audit")
    args = parser.parse_args()
    report = run_audit()
    write_report(report, args.output_dir)
    print(f"[audit_results] {'PASS' if report['passed'] else 'FAIL'} errors={report['error_count']}")
    for error in report["errors"][:20]:
        print(f"  - {error}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
