import logging
import os
import time


class KVFormatter(logging.Formatter):
    """Simple key=value formatter for grep-friendly structured logs."""

    converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ")
        base = (
            f"ts={ts} level={record.levelname} "
            f"logger={record.name} msg={record.getMessage()}"
        )
        return base


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper().strip()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()

    # Avoid duplicate handlers during reload.
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(KVFormatter())
    root.addHandler(handler)
    root.setLevel(level)

    # Keep noisy libs manageable unless explicitly in debug.
    if level > logging.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
