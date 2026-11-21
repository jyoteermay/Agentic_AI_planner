"""
Central logging setup for the AI Trip Planner.

Usage:
    from logger.logging import get_logger
    logger = get_logger(__name__)
    logger.info("something happened")

Features:
- Console output (coloured by level) + a rotating log file in ./logs/trip_planner.log
- Every line carries a request id, so all logs for one /query call can be grepped together
- Level controlled by the LOG_LEVEL env var (DEBUG, INFO, WARNING, ERROR); default INFO
- `log_duration` context manager to time any block of code
"""
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.getenv("LOG_DIR", os.path.join(PROJECT_ROOT, "logs"))
LOG_FILE = os.path.join(LOG_DIR, "trip_planner.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

ROOT_LOGGER_NAME = "trip_planner"

# Request id shared by every log line emitted while handling one request
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def new_request_id() -> str:
    """Create a short request id and attach it to all following log lines in this context."""
    rid = uuid.uuid4().hex[:8]
    _request_id.set(rid)
    return rid


def get_request_id() -> str:
    return _request_id.get()


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class _ColourFormatter(logging.Formatter):
    COLOURS = {
        logging.DEBUG: "\033[36m",     # cyan
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[41m",  # red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        colour = self.COLOURS.get(record.levelno)
        return f"{colour}{message}{self.RESET}" if colour else message


_FORMAT = "%(asctime)s | %(levelname)-8s | req=%(request_id)s | %(name)s:%(lineno)d | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _configure_root() -> logging.Logger:
    root = logging.getLogger(ROOT_LOGGER_NAME)
    if root.handlers:  # already configured (e.g. uvicorn --reload re-import)
        return root

    root.setLevel(LOG_LEVEL)
    root.propagate = False
    request_filter = _RequestIdFilter()

    console = logging.StreamHandler(sys.stdout)
    use_colour = sys.stdout.isatty() and os.getenv("NO_COLOR") is None
    console.setFormatter(
        _ColourFormatter(_FORMAT, _DATE_FORMAT) if use_colour else logging.Formatter(_FORMAT, _DATE_FORMAT)
    )
    console.addFilter(request_filter)
    root.addHandler(console)

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_FORMAT, _DATE_FORMAT))
        file_handler.addFilter(request_filter)
        root.addHandler(file_handler)
    except OSError as e:  # read-only disk etc. – keep console logging working
        root.warning("File logging disabled: %s", e)

    # Quieten chatty third-party libraries
    for noisy in ("httpx", "httpcore", "urllib3", "google_genai", "groq"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return root


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the project's root logger, e.g. trip_planner.agent.agentic_workflow."""
    _configure_root()
    if name in ("__main__", ROOT_LOGGER_NAME):
        return logging.getLogger(ROOT_LOGGER_NAME)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


@contextmanager
def log_duration(logger: logging.Logger, label: str, level: int = logging.INFO):
    """Log how long a block takes; logs an error with the duration if the block raises."""
    start = time.perf_counter()
    try:
        yield
    except Exception:
        logger.error("%s failed after %.2fs", label, time.perf_counter() - start)
        raise
    else:
        logger.log(level, "%s took %.2fs", label, time.perf_counter() - start)
