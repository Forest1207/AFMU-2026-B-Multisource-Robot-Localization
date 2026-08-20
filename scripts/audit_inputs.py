"""Audit local official attachments against the repository input manifest.

The public repository may intentionally omit binary competition attachments.
Place local copies in ``00_problem/attachments`` and run this script before a
full reproducibility run.  The audit checks file hashes, sizes, sheet names,
row counts and required columns so an accidentally replaced attachment cannot
silently change the formal results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "00_problem" / "input_manifest.json"
DEFAULT_DATA_DIR = ROOT / "00_problem" / "attachments"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_file(data_dir: Path, canonical_name: str, spec: dict) -> Path | None:
    names = [canonical_name] + list(spec.get("accepted_local_names", []))
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        candidate = data_dir / name
        if candidate.is_file():
            return candidate
    return None


def audit_file(path: Path, canonical_name: str, spec: dict) -> list[str]:
    errors: list[str] = []
    actual_hash = sha256(path)
    if actual_hash != spec["sha256"]:
        errors.append(
            f"{canonical_name}: SHA256 mismatch: {actual_hash} != {spec['sha256']}"
        )
    if "bytes" in spec and path.stat().st_size != int(spec["bytes"]):
        errors.append(
            f"{canonical_name}: byte size mismatch: {path.stat().st_size} != {spec['bytes']}"
        )

    xls = pd.ExcelFile(path)
    expected_sheets = spec.get("sheets", {})
    missing = [name for name in expected_sheets if name not in xls.sheet_names]
    if missing:
        errors.append(f"{canonical_name}: missing sheets {missing}; actual={xls.sheet_names}")
        return errors

    for sheet_name, sheet_spec in expected_sheets.items():
        frame = pd.read_excel(path, sheet_name=sheet_name)
        expected_rows = sheet_spec.get("rows")
        if expected_rows is not None and len(frame) != int(expected_rows):
            errors.append(
                f"{canonical_name}/{sheet_name}: rows {len(frame)} != {expected_rows}"
            )
        expected_data_rows = sheet_spec.get("data_rows")
        if expected_data_rows is not None and len(frame) != int(expected_data_rows):
            errors.append(
                f"{canonical_name}/{sheet_name}: data rows {len(frame)} != {expected_data_rows}"
            )
        required_columns = sheet_spec.get("columns")
        if required_columns:
            missing_columns = [column for column in required_columns if column not in frame.columns]
            if missing_columns:
                errors.append(
                    f"{canonical_name}/{sheet_name}: missing columns {missing_columns}; "
                    f"actual={list(frame.columns)}"
                )
    return errors


def run_audit(manifest_path: Path = DEFAULT_MANIFEST,
              data_dir: Path = DEFAULT_DATA_DIR,
              require_all: bool = True) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    missing: list[str] = []
    audited: dict[str, dict] = {}

    for canonical_name, spec in manifest["files"].items():
        path = _resolve_file(data_dir, canonical_name, spec)
        if path is None:
            missing.append(canonical_name)
            if require_all:
                errors.append(f"{canonical_name}: file not found in {data_dir}")
            continue
        file_errors = audit_file(path, canonical_name, spec)
        errors.extend(file_errors)
        audited[canonical_name] = {
            "path": str(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "passed": not file_errors,
        }

    return {
        "passed": not errors,
        "require_all": require_all,
        "data_dir": str(data_dir),
        "audited": audited,
        "missing": missing,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit official competition attachments.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--allow-missing", action="store_true",
        help="Audit files that exist but do not fail solely because binaries are absent from the public repo.",
    )
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON report path.")
    args = parser.parse_args()

    report = run_audit(args.manifest, args.data_dir, require_all=not args.allow_missing)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "PASS" if report["passed"] else "FAIL"
    print(f"[audit_inputs] {status} audited={len(report['audited'])} missing={len(report['missing'])}")
    for error in report["errors"]:
        print(f"  - {error}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
