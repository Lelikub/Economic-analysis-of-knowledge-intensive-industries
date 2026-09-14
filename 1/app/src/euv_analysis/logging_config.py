"""Console and UTF-8 file logging for the analysis pipeline."""

from __future__ import annotations

import logging
from pathlib import Path


class _StageFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "stage"):
            record.stage = "component"
        return True


def configure_logging(log_path: Path) -> None:
    """Configure deterministic console and file handlers."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for handler in tuple(root.handlers):
        handler.close()
        root.removeHandler(handler)
    root.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(stage)s | %(message)s"
    )
    stage_filter = _StageFilter()

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    console.addFilter(stage_filter)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(stage_filter)

    root.addHandler(console)
    root.addHandler(file_handler)
