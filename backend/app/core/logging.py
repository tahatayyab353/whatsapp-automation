import logging
import sys
from contextvars import ContextVar
from typing import Any
from app.core.config import settings

# Context variable to hold the current request ID for logging correlation
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDFilter(logging.Filter):
    """
    Injects the active request_id from contextvars into every log record.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get() or "-"  # type: ignore[attr-defined]
        return True


def setup_logging() -> logging.Logger:
    """
    Configures centralized structured logging for the FastAPI application.
    """
    log_format = "%(asctime)s | %(levelname)-8s | [%(request_id)s] | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Root logger handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
    handler.addFilter(RequestIDFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Clear existing handlers to prevent duplicate outputs
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    app_logger = logging.getLogger("ai_receptionist")
    app_logger.setLevel(log_level)
    return app_logger


logger = setup_logging()
