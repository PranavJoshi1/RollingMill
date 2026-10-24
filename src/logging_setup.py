"""App-wide logging: console + optional file under logs/."""

from __future__ import annotations

import logging
import os
from pathlib import Path

_CONFIGURED = False
_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"


def setup_logging(name: str = "monoegde") -> logging.Logger:
    """Configure root logger once; return a named logger."""
    global _CONFIGURED
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if not _CONFIGURED:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        root = logging.getLogger()
        root.setLevel(level)

        # Avoid duplicate handlers on Streamlit reruns
        if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
            sh = logging.StreamHandler()
            sh.setFormatter(fmt)
            sh.setLevel(level)
            root.addHandler(sh)

        log_path = _LOG_DIR / "monoegde.log"
        if not any(
            isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", "") == str(log_path)
            for h in root.handlers
        ):
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setFormatter(fmt)
            fh.setLevel(level)
            root.addHandler(fh)

        # Quieter third-party noise
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

        _CONFIGURED = True
        logging.getLogger("monoegde").info(
            "Logging ready (level=%s, file=%s)", level_name, log_path
        )

    return logging.getLogger(name)
