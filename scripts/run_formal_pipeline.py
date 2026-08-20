"""Run the complete formal Q1--Q4 workflow from local official attachments.

This is the repository-level replacement for the reference package's
``code/main.py``.  Unlike the reference export it has no hidden DATA_FACTS /
DATA_PROFILE dependency: the required input contract is committed as
``00_problem/input_manifest.json`` and checked before numerical work starts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(command: list[str]) -> None:
    print("\n[formal]", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def resolve_template(data_dir: Path) -> Path:
    for name in ("result_template.xlsx", "result.xlsx"):
        path = data_dir / name
        if path.is_file():
            return path
    raise FileNotFoundError("result_template.xlsx/result.xlsx not found in input directory")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run formal Q1-Q4 models, figures and validation.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "00_problem" / "attachments")
    parser.add_argument("--skip-q1", action="store_true")
    parser.add_argument("--skip-q2", action="store_true")
    parser.add_argument("--skip-q3", action="store_true")
    parser.add_argument("--skip-q4", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument("--skip-audit", action="store_true")
    args = parser.parse_args()
    data = args.data_dir.resolve()

    run([PYTHON, "scripts/audit_inputs.py", "--data-dir", str(data)])
    template = resolve_template(data)

    if not args.skip_q1:
        run([
            PYTHON, "03_models/q1/run_q1.py",
            "--input", str(data / "附件1.xlsx"),
            "--output-dir", "05_results/q1",
            "--figure-dir", "06_figures/q1",
            "--method", "cubic",
            "--compare-interpolators",
        ])

    if not args.skip_q2:
        run([
            PYTHON, "03_models/q2/run_q2.py", str(data / "附件2.xlsx"),
            "--sheet1", "方式1(4Hz)", "--sheet2", "方式2(5Hz)",
            "--output", "05_results/q2/trajectory_10hz.csv",
            "--summary", "05_results/q2/parameters.json",
            "--innovations", "05_results/q2/innovations.csv",
            "--tuning", "05_results/q2/process_noise_tuning.csv",
        ])

    if not args.skip_q3:
        run([
            PYTHON, "03_models/q3/run_q3.py", str(data / "附件3.xlsx"),
            "--sheet1", "方式1(4Hz)", "--sheet2", "方式2(5Hz)",
            "--output", "05_results/q3/trajectory_10hz.csv",
            "--summary", "05_results/q3/parameters.json",
            "--innovations", "05_results/q3/innovations.csv",
            "--tuning", "05_results/q3/process_noise_tuning.csv",
        ])

    if not args.skip_q4:
        run([
            PYTHON, "03_models/q4/run_q4.py",
            "--trajectory", "05_results/q3/trajectory_10hz.csv",
            "--targets", str(data / "附件4.xlsx"),
            "--template", str(template),
            "--results", "05_results/q4",
        ])

    if not args.skip_figures:
        if not args.skip_q2:
            run([
                PYTHON, "03_models/q2/make_figures.py",
                "--input", str(data / "附件2.xlsx"),
                "--sheet1", "方式1(4Hz)", "--sheet2", "方式2(5Hz)",
                "--results", "05_results/q2", "--figures", "06_figures/q2",
            ])
        if not args.skip_q3:
            run([
                PYTHON, "03_models/q3/make_figures.py",
                "--input", str(data / "附件3.xlsx"),
                "--sheet1", "方式1(4Hz)", "--sheet2", "方式2(5Hz)",
                "--results", "05_results/q3", "--figures", "06_figures/q3",
            ])
        if not args.skip_q4:
            run([
                PYTHON, "03_models/q4/make_figures.py",
                "--trajectory", "05_results/q3/trajectory_10hz.csv",
                "--targets", str(data / "附件4.xlsx"),
                "--results", "05_results/q4", "--figures", "06_figures/q4",
            ])

    if not args.skip_q4:
        run([
            PYTHON, "03_models/q4/validation.py",
            "--trajectory", "05_results/q3/trajectory_10hz.csv",
            "--targets", str(data / "附件4.xlsx"),
            "--template", str(template),
            "--results", "05_results/q4", "--figures", "06_figures/q4",
            "--output", "05_results/q4/validation.json",
        ])

    if not args.skip_audit:
        run([PYTHON, "scripts/audit_results.py"])

    log = {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "data_dir": str(data),
        "skips": {
            "q1": args.skip_q1, "q2": args.skip_q2, "q3": args.skip_q3,
            "q4": args.skip_q4, "figures": args.skip_figures, "audit": args.skip_audit,
        },
    }
    path = ROOT / "05_results" / "formal_pipeline_run.json"
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[formal] PASS")


if __name__ == "__main__":
    main()
