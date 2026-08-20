"""Create an audited competition submission package and SHA256 manifest.

The package intentionally separates formal deliverables from repository history.
It includes the compiled paper, unrestricted Q4 result workbook, source code,
LaTeX source, formal result summaries/parameters, and audit reports.  Official
binary inputs are optional because some competitions restrict redistribution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "08_submission"
PYTHON = sys.executable


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_path(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build final audited submission ZIP.")
    parser.add_argument("--include-inputs", action="store_true", help="Include official xlsx inputs from 00_problem/attachments.")
    parser.add_argument("--skip-paper-build", action="store_true")
    args = parser.parse_args()

    subprocess.run([PYTHON, "scripts/audit_results.py"], cwd=ROOT, check=True)
    if not args.skip_paper_build:
        subprocess.run([PYTHON, "scripts/build_paper.py"], cwd=ROOT, check=True)

    paper = SUBMISSION / "B题-多源融合机器人定位及任务优化.pdf"
    result = ROOT / "05_results" / "q4" / "result.xlsx"
    if not paper.is_file():
        raise FileNotFoundError(paper)
    if not result.is_file():
        raise FileNotFoundError(result)

    staging = SUBMISSION / "package"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    copy_path(paper, staging / "paper" / paper.name)
    copy_path(result, staging / "result.xlsx")
    copy_path(ROOT / "requirements.txt", staging / "code" / "requirements.txt")
    copy_path(ROOT / "03_models", staging / "code" / "03_models")
    copy_path(ROOT / "scripts", staging / "code" / "scripts")
    copy_path(ROOT / "07_paper" / "latex", staging / "paper" / "latex")
    copy_path(ROOT / "00_problem" / "input_manifest.json", staging / "reproducibility" / "input_manifest.json")
    copy_path(ROOT / "05_results" / "reporting_conventions.json", staging / "reproducibility" / "reporting_conventions.json")
    copy_path(SUBMISSION / "audit", staging / "audit")

    for problem in range(1, 5):
        source = ROOT / "05_results" / f"q{problem}"
        dest = staging / "formal_results" / f"q{problem}"
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("parameters.json", "summary.md", "validation.json", "figure_manifest.json"):
            path = source / name
            if path.is_file():
                copy_path(path, dest / name)
        if problem == 4:
            copy_path(source / "optimized_schedule.csv", dest / "optimized_schedule.csv")

    if args.include_inputs:
        copy_path(ROOT / "00_problem" / "attachments", staging / "inputs")

    readme = """# B题参赛提交包\n\n本目录由 `scripts/package_submission.py` 自动生成。\n\n- `paper/`：论文 PDF 与 LaTeX 源码；\n- `result.xlsx`：问题四全部优化任务，A:E 可向下扩展，红色说明区域保持不变；\n- `code/`：Q1--Q4 正式代码与复现/审计/打包脚本；\n- `formal_results/`：各问关键参数、摘要、验证和图件来源清单；\n- `audit/`：机器审计报告；\n- `reproducibility/`：输入文件清单与统一报告口径。\n\n问题四不含人为的 9 项容量约束，也不含题面未给出的跨任务准备时间互斥。\n"""
    (staging / "README.md").write_text(readme, encoding="utf-8")

    manifest = []
    for path in sorted(p for p in staging.rglob("*") if p.is_file()):
        manifest.append({
            "path": str(path.relative_to(staging)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    manifest_doc = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(manifest),
        "include_inputs": args.include_inputs,
        "files": manifest,
    }
    (staging / "DELIVERABLES.json").write_text(json.dumps(manifest_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    zip_path = SUBMISSION / "AFMU-2026-B-submission.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in staging.rglob("*") if p.is_file()):
            archive.write(path, path.relative_to(staging))

    zip_meta = {
        "zip": str(zip_path),
        "bytes": zip_path.stat().st_size,
        "sha256": sha256(zip_path),
        "file_count": len(manifest) + 1,
    }
    (SUBMISSION / "package_build.json").write_text(json.dumps(zip_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[package] PASS -> {zip_path}")


if __name__ == "__main__":
    main()
