"""Exponential backoff for retriable I/O (e.g. PLC round-trips)."""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_sec: float = 1.0,
    operation_name: str = "operation",
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            logger.warning(
                "%s failed (attempt %s/%s): %s",
                operation_name,
                attempt,
                attempts,
                e,
            )
            if attempt < attempts:
                time.sleep(base_delay_sec * (2 ** (attempt - 1)))
    assert last_exc is not None
    logger.error("%s exhausted all retries", operation_name)
    raise last_exc
