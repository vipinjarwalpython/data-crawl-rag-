"""
Centralized logging configuration for CrawlRAG.

Provides:
- Console handler with color-friendly formatting
- Rotating file handler for persistent audit trail (logs/crawlrag.log)
- Per-module logger factory via get_module_logger()
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_log_formatter() -> logging.Formatter:
    """Return the shared log format used by all handlers."""
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _attach_console_handler(logger: logging.Logger, level: int) -> None:
    """Attach a stdout stream handler to *logger* if not already present."""
    if any(isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
           for h in logger.handlers):
        return

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(_build_log_formatter())
    logger.addHandler(console_handler)


def _attach_file_handler(
    logger: logging.Logger,
    log_file_path: Path,
    level: int,
    max_bytes: int,
    backup_count: int,
) -> None:
    """Attach a rotating file handler to *logger* if not already present."""
    if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        return

    try:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(_build_log_formatter())
        logger.addHandler(file_handler)
    except OSError as exc:
        # If we can't open the log file (e.g. permission error), warn on
        # the console but don't crash the entire application.
        logging.getLogger("crawlrag.logging_setup").warning(
            "Could not create rotating file handler at %s: %s",
            log_file_path,
            exc,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logger(
    name: str = "crawlrag",
    *,
    log_file_path: Path | None = None,
    max_bytes: int = 10 * 1024 * 1024,   # 10 MB per file
    backup_count: int = 5,
    debug: bool | None = None,
) -> logging.Logger:
    """Configure and return a structured logger.

    Parameters
    ----------
    name:
        Logger name (appears in the ``[name]`` field of every log line).
    log_file_path:
        Absolute path to the rotating log file.  If ``None`` the file
        handler is skipped and only console output is produced.
    max_bytes:
        Maximum size of a single log file before rotation.
    backup_count:
        Number of rotated backup files to keep.
    debug:
        Override log level.  When ``None``, reads from ``settings.DEBUG``.
    """
    # Resolve log level lazily to avoid circular imports at module load time.
    if debug is None:
        try:
            from app.core.config import settings  # noqa: PLC0415
            debug = settings.DEBUG
        except Exception:
            debug = False

    log_level = logging.DEBUG if debug else logging.INFO

    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured — just ensure the level is correct.
        logger.setLevel(log_level)
        return logger

    logger.setLevel(log_level)
    logger.propagate = False

    _attach_console_handler(logger, log_level)

    if log_file_path is not None:
        _attach_file_handler(
            logger,
            log_file_path=log_file_path,
            level=log_level,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )

    return logger


def get_module_logger(module_name: str) -> logging.Logger:
    """Return a child logger scoped to *module_name*.

    All child loggers inherit handlers and level from the root ``crawlrag``
    logger, so you never need to configure them individually.

    Usage::

        from app.core.logging import get_module_logger
        logger = get_module_logger(__name__)
    """
    return logging.getLogger(f"crawlrag.{module_name}")


# ---------------------------------------------------------------------------
# Module-level root logger — used by all modules that import `logger` directly
# ---------------------------------------------------------------------------

def _create_root_logger() -> logging.Logger:
    """Bootstrap the root CrawlRAG logger with file + console handlers."""
    try:
        from app.core.config import settings  # noqa: PLC0415

        log_file_path: Path = (
            settings.BASE_DIR / settings.LOG_DIR / "crawlrag.log"
            if not settings.LOG_DIR.is_absolute()
            else settings.LOG_DIR / "crawlrag.log"
        )
        return setup_logger(
            "crawlrag",
            log_file_path=log_file_path,
            max_bytes=settings.LOG_MAX_BYTES,
            backup_count=settings.LOG_BACKUP_COUNT,
            debug=settings.DEBUG,
        )
    except Exception:
        # Fallback: console-only logger if settings are unavailable.
        return setup_logger("crawlrag", debug=False)


logger: logging.Logger = _create_root_logger()
