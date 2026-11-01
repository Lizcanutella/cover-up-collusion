"""Logging setup for ledgerly.

Logging is configured exactly once, here. Call :func:`configure_logging` from an
entry point (CLI, job runner) to pick the level and output format, and use
:func:`get_logger` everywhere else. If nobody configured logging yet,
``get_logger`` falls back to the defaults so library use and tests still work.
"""

from __future__ import annotations

import logging
import sys

import structlog

_CONFIGURED = False


class _StderrLogger:
    """Minimal structlog logger that writes rendered lines to the *current* stderr.

    Looking up ``sys.stderr`` on every call (instead of binding it at configure time)
    keeps this working when stderr is swapped out, e.g. by a test runner.
    """

    def msg(self, message: str) -> None:
        sys.stderr.write(message + "\n")

    log = debug = info = warn = warning = fatal = failure = err = error = critical = msg
    exception = msg


def configure_logging(level: str = "INFO", json: bool = False) -> None:
    """Configure structlog. Safe to call more than once; the last call wins."""
    global _CONFIGURED
    level_no = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    renderer = (
        structlog.processors.JSONRenderer()
        if json
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_no),
        logger_factory=lambda *args: _StderrLogger(),
        cache_logger_on_first_use=False,
    )
    _CONFIGURED = True


def get_logger(name: str | None = None):
    """Return a structlog bound logger, configuring defaults on first use."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name) if name else structlog.get_logger()
