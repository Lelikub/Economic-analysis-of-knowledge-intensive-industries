"""Command-line entry point for the complete EUV analysis pipeline."""

from __future__ import annotations

from pathlib import Path
import sys


APP_DIR = Path(__file__).resolve().parent
SRC_DIR = APP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from euv_analysis.pipeline import AnalysisPipeline


def main() -> int:
    """Run the pipeline with paths anchored to this application."""
    AnalysisPipeline(data_dir=APP_DIR.parent / "data", work_dir=APP_DIR).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
