"""LogixDriver factory: some pycomm3 versions omit ``timeout`` on the constructor."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from pycomm3 import LogixDriver

from app.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def logix_driver_session() -> Generator[LogixDriver, None, None]:
    host = settings.plc_host
    t = settings.plc_connect_timeout_seconds
    logger.debug("LogixDriver connecting to host=%r timeout=%s", host, t)
    driver: LogixDriver
    if t and t > 0:
        try:
            driver = LogixDriver(host, timeout=t)
        except TypeError:
            logger.debug("LogixDriver does not accept timeout=; using default")
            driver = LogixDriver(host)
    else:
        driver = LogixDriver(host)
    with driver as plc:
        yield plc
