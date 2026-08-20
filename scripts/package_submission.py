"""Create an audited, reproducible competition submission package.

The ZIP contains the two top-level deliverables (paper PDF and result.xlsx) and
an exact-layout ``reproducible_source`` snapshot.  The latter preserves the
repository-relative paths expected by the formal pipeline, LaTeX source and
audit scripts.  Official binary inputs are optional because redistribution may
be restricted by the competition.
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

BUILD_IGNORES = (
    "__pycache__", "*.pyc", ".DS_Store",
    "*.aux", "*.log", "*.out", "*.toc", "*.fls", "*.fdb_latexmk",
    "main.pdf",
)


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
        shutil.copytree(
            source, destination, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*BUILD_IGNORES),
        )
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def build_manifest(staging: Path, include_inputs: bool) -> dict:
    files = []
    for path in sorted(p for p in staging.rglob("*") if p.is_file() and p.name != "DELIVERABLES.json"):
        files.append({
            "path": str(path.relative_to(staging)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_count_excluding_manifest": len(files),
        "include_inputs": include_inputs,
        "files": files,
    }


def verify_zip(zip_path: Path, staging: Path) -> dict:
    expected = sorted(str(p.relative_to(staging)).replace("\\", "/")
                      for p in staging.rglob("*") if p.is_file())
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        actual = sorted(name.rstrip("/") for name in archive.namelist() if not name.endswith("/"))
    return {
        "crc_ok": bad is None,
        "bad_member": bad,
        "member_set_equal": actual == expected,
        "expected_members": len(expected),
        "actual_members": len(actual),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build final audited submission ZIP.")
    parser.add_argument(
        "--include-inputs", action="store_true",
        help="Include official xlsx inputs under reproducible_source/00_problem/attachments.",
    )
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

    # Human-facing top-level deliverables.
    copy_path(paper, staging / paper.name)
    copy_path(result, staging / "result.xlsx")
    copy_path(SUBMISSION / "audit", staging / "audit")

    # Repository-layout source snapshot.  From this directory all existing
    # ROOT-relative scripts and LaTeX figure links retain their semantics.
    source_root = staging / "reproducible_source"
    copy_path(ROOT / "requirements.txt", source_root / "requirements.txt")
    copy_path(ROOT / "README.md", source_root / "README.md")
    copy_path(ROOT / "00_problem" / "input_manifest.json", source_root / "00_problem" / "input_manifest.json")
    copy_path(ROOT / "01_ideas" / "time_offset_convention.md", source_root / "01_ideas" / "time_offset_convention.md")
    copy_path(ROOT / "03_models", source_root / "03_models")
    copy_path(ROOT / "05_results", source_root / "05_results")
    copy_path(ROOT / "06_figures", source_root / "06_figures")
    copy_path(ROOT / "07_paper" / "latex", source_root / "07_paper" / "latex")
    copy_path(ROOT / "scripts", source_root / "scripts")

    if args.include_inputs:
        copy_path(ROOT / "00_problem" / "attachments", source_root / "00_problem" / "attachments")
    else:
        attachments = source_root / "00_problem" / "attachments"
        attachments.mkdir(parents=True, exist_ok=True)
        (attachments / "README.md").write_text(
            "Official binary inputs are intentionally omitted. Place 附件1.xlsx--附件4.xlsx "
            "and result_template.xlsx here, then run `python scripts/audit_inputs.py`.\n",
            encoding="utf-8",
        )

    readme = """# B题参赛提交包

本目录由 `scripts/package_submission.py` 自动生成。

## 顶层交付

- `B题-多源融合机器人定位及任务优化.pdf`：正式论文；
- `result.xlsx`：问题四全部优化任务；
- `audit/`：机器审计报告；
- `DELIVERABLES.json`：交付文件 SHA256 清单；
- `reproducible_source/`：保持原仓库相对目录的可复现源码快照。

## 问题四口径

- 不含人为的 9 项容量约束；
- 不含题面未给出的跨任务准备时间互斥；
- A:E 可按任务数向下扩展；
- H:L 红色说明/范例保持不变；
- 最终时刻经过 0.01 s 完整准备窗口复核。

## 复现

进入 `reproducible_source/` 后，若官方附件未打包，请先放入
`00_problem/attachments/`，然后运行：

```bash
python scripts/audit_inputs.py
python scripts/run_formal_pipeline.py
python scripts/audit_results.py
python scripts/build_paper.py
```
"""
    (staging / "README.md").write_text(readme, encoding="utf-8")

    manifest_doc = build_manifest(staging, args.include_inputs)
    (staging / "DELIVERABLES.json").write_text(
        json.dumps(manifest_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    zip_path = SUBMISSION / "AFMU-2026-B-submission.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in staging.rglob("*") if p.is_file()):
            archive.write(path, path.relative_to(staging))

    verification = verify_zip(zip_path, staging)
    if not verification["crc_ok"] or not verification["member_set_equal"]:
        raise RuntimeError(f"ZIP verification failed: {verification}")

    zip_meta = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "zip": str(zip_path),
        "bytes": zip_path.stat().st_size,
        "sha256": sha256(zip_path),
        "verification": verification,
    }
    (SUBMISSION / "package_build.json").write_text(
        json.dumps(zip_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[package] PASS -> {zip_path}")


if __name__ == "__main__":
    main()
