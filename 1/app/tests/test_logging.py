from __future__ import annotations

import logging

from euv_analysis.logging_config import configure_logging


def test_logging_keeps_application_debug_and_suppresses_dependency_noise(tmp_path):
    """Catches third-party DEBUG output overwhelming the execution trace."""
    path = tmp_path / "execution.log"
    configure_logging(path)

    logging.getLogger("euv_analysis.probe").debug("APPLICATION_DEBUG_SIGNAL")
    logging.getLogger("matplotlib.font_manager").debug("DEPENDENCY_DEBUG_NOISE")
    for handler in logging.getLogger().handlers:
        handler.flush()

    content = path.read_text(encoding="utf-8")
    assert "APPLICATION_DEBUG_SIGNAL" in content
    assert "DEPENDENCY_DEBUG_NOISE" not in content
