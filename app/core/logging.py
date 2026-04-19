"""Central logging configuration.

`configure_logging()` is called once at app startup (see `app.main`). All modules
get their logger via `logging.getLogger(__name__)`.
"""
from __future__ import annotations

import logging
import logging.config

from .config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    handlers: dict[str, dict] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": settings.log_level,
        },
    }
    handler_names = ["console"]

    if settings.log_to_file:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "standard",
            "level": settings.log_level,
            "filename": str(settings.log_dir / "app.log"),
            "maxBytes": 5_000_000,
            "backupCount": 3,
            "encoding": "utf-8",
        }
        handler_names.append("file")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {"format": _LOG_FORMAT, "datefmt": _DATE_FORMAT},
            },
            "handlers": handlers,
            "root": {"level": settings.log_level, "handlers": handler_names},
            "loggers": {
                "uvicorn.error": {"level": settings.log_level, "handlers": handler_names, "propagate": False},
                "uvicorn.access": {"level": settings.log_level, "handlers": handler_names, "propagate": False},
            },
        }
    )
