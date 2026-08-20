"""Generate result-driven TeX assets and compile the competition paper.

The build is intentionally gated by ``audit_results.py``.  If Q4 still carries
legacy nine-capacity outputs, or a formal figure is missing, the paper build
stops instead of silently producing a mixed-version PDF.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "07_paper" / "latex"
SUBMISSION = ROOT / "08_submission"
PYTHON = sys.executable


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("[paper]", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def find_engine(requested: str | None) -> list[str]:
    if requested:
        path = shutil.which(requested)
        if not path:
            raise RuntimeError(f"Requested TeX engine not found: {requested}")
        return [path]
    latexmk = shutil.which("latexmk")
    if latexmk:
        return [latexmk, "-xelatex", "-interaction=nonstopmode", "-halt-on-error"]
    xelatex = shutil.which("xelatex")
    if xelatex:
        return [xelatex, "-interaction=nonstopmode", "-halt-on-error"]
    raise RuntimeError("Neither latexmk nor xelatex is available. Install TeX Live/MiKTeX with XeLaTeX.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit, generate and compile the formal paper.")
    parser.add_argument("--engine", default=None, help="Optional latexmk/xelatex executable name.")
    parser.add_argument("--skip-audit", action="store_true")
    args = parser.parse_args()

    if not args.skip_audit:
        run([PYTHON, "scripts/audit_results.py"])
    run([PYTHON, "scripts/generate_latex_assets.py"])

    engine = find_engine(args.engine)
    main_tex = "main.tex"
    if Path(engine[0]).name.lower().startswith("latexmk"):
        run(engine + [main_tex], cwd=PAPER)
    else:
        run(engine + [main_tex], cwd=PAPER)
        run(engine + [main_tex], cwd=PAPER)

    pdf = PAPER / "main.pdf"
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise RuntimeError("LaTeX build completed without a non-empty main.pdf")

    SUBMISSION.mkdir(parents=True, exist_ok=True)
    output = SUBMISSION / "B题-多源融合机器人定位及任务优化.pdf"
    shutil.copy2(pdf, output)
    metadata = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(PAPER / "main.tex"),
        "pdf": str(output),
        "pdf_sha256": sha256(output),
        "engine": engine,
    }
    (SUBMISSION / "paper_build.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[paper] PASS -> {output}")


if __name__ == "__main__":
    main()
