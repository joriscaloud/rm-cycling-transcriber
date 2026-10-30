"""Logging + timing helpers.

Reimplements the pattern used in GrooverAudio (stdout logger + a @timing
decorator) as clean, dependency-free stdlib code.
"""

from __future__ import annotations

import functools
import logging
import os
import time
from collections.abc import Callable
from typing import TypeVar

_T = TypeVar("_T")


def get_logger(name: str = "rmcycling") -> logging.Logger:
    """Return a configured logger. Level is driven by LOG_LEVEL (default INFO)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


log = get_logger()


def timing(func: Callable[..., _T]) -> Callable[..., _T]:
    """Log how long a function took. Mirrors GrooverAudio's @timing decorator."""

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> _T:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            log.info("%s took %.2fs", func.__name__, elapsed)

    return wrapper
