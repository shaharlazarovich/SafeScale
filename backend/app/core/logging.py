import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.core.config import settings

_configured = False


def _setup_root_logger() -> None:
    global _configured
    if _configured:
        return

    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "module"},
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger("safescale")
    root.setLevel(settings.LOG_LEVEL.upper())
    root.addHandler(handler)
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    _setup_root_logger()
    return logging.getLogger(f"safescale.{name}")
