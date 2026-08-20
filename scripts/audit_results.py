"""Machine-audit the formal Q1--Q4 result chain and paper assets.

This script intentionally audits *produced artifacts* instead of recomputing the
models.  It is the submission gate used after numerical runs and before LaTeX
packaging.  A separate ``audit_inputs.py`` checks the raw official attachments.
"""

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
    time_col = find_time_column(frame)
    time = pd.to_numeric(frame[time_col], errors="coerce").to_numpy(float)
    if np.any(~np.isfinite(time)):
        errors.append(f"{path}: invalid time values")
        return errors
    if np.any(np.diff(time) <= 0):
        errors.append(f"{path}: time is not strictly increasing")
    if len(time) > 1:
        dt = float(np.median(np.diff(time)))
        if abs(dt - expected_dt) > 1e-8:
            errors.append(f"{path}: median dt={dt} != {expected_dt}")
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
        actual = float(conventions[key]["delta_s"])
        if not math.isclose(actual, value, rel_tol=0.0, abs_tol=1e-10):
            errors.append(f"reporting convention {key}: delta_s={actual} != {value}")
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
            formats = set(item.get("formats", []))
            if "pdf" not in formats:
                errors.append(f"Q{problem}/{stem}: PDF not declared in manifest")
                continue
            pdf = FIGURES / f"q{problem}" / f"{stem}.pdf"
            if not pdf.is_file() or pdf.stat().st_size == 0:
                errors.append(f"Q{problem}/{stem}: missing non-empty PDF figure")
    return errors


def audit_q4() -> list[str]:
    errors: list[str] = []
    params = load_json(RESULTS / "q4" / "parameters.json")
    schedule_path = RESULTS / "q4" / "optimized_schedule.csv"
    if not schedule_path.is_file():
        return ["Q4: optimized_schedule.csv missing"]
    schedule = pd.read_csv(schedule_path)
    selected_count = int(params["selected_task_count"])
    if len(schedule) != selected_count:
        errors.append(f"Q4: schedule rows {len(schedule)} != selected_task_count {selected_count}")
    if len(schedule) > 9:
        errors.append(f"Q4: schedule has {len(schedule)} rows > result template capacity 9")
    if int(params["maximum_task_count"]) != 9:
        errors.append(f"Q4: maximum_task_count={params['maximum_task_count']} expected 9")
    if int(params["shooting_count"]) + int(params["photography_count"]) != selected_count:
        errors.append("Q4: shooting_count + photography_count mismatch")
    milp = params.get("milp", {})
    for stage in (1, 2, 3):
        gap = milp.get(f"stage{stage}_gap")
        if gap is not None and abs(float(gap)) > 1e-12:
            errors.append(f"Q4: stage{stage} MIP gap={gap}")
    workbook = params.get("result_workbook", {})
    if workbook.get("writable_cells") != "B2:E10":
        errors.append("Q4: workbook writable range is not B2:E10")
    if workbook.get("untouched_snapshot_equal") is not True:
        errors.append("Q4: template-preservation audit did not pass")
    if not (RESULTS / "q4" / "result.xlsx").is_file():
        errors.append("Q4: result.xlsx missing")
    return errors


def run_audit() -> dict:
    errors: list[str] = []
    trajectory_names = {
        1: "trajectory_10hz.csv",
        2: "trajectory_10hz.csv",
        3: "trajectory_10hz.csv",
    }
    for problem, filename in trajectory_names.items():
        errors.extend(audit_trajectory(RESULTS / f"q{problem}" / filename))
    errors.extend(audit_reporting_convention())
    errors.extend(audit_figures())
    errors.extend(audit_q4())

    checks = {
        "formal_result_directories": all((RESULTS / f"q{i}").is_dir() for i in range(1, 5)),
        "reporting_convention_present": (RESULTS / "reporting_conventions.json").is_file(),
        "q4_result_workbook_present": (RESULTS / "q4" / "result.xlsx").is_file(),
        "paper_source_present": (ROOT / "07_paper" / "latex" / "main.tex").is_file(),
    }
    for label, passed in checks.items():
        if not passed:
            errors.append(f"missing required artifact: {label}")

    return {
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "checks": checks,
    }


def write_report(report: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "audit_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Submission Audit Report",
        "",
        f"- status: **{'PASS' if report['passed'] else 'FAIL'}**",
        f"- error count: **{report['error_count']}**",
        "",
        "## Checks",
        "",
    ]
    for label, passed in report["checks"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} `{label}`")
    lines += ["", "## Errors", ""]
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- None")
    (output_dir / "audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit formal results and figure assets.")
    parser.add_argument(
        "--output-dir", type=Path, default=SUBMISSION / "audit",
        help="Directory for JSON/Markdown audit reports.",
    )
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
