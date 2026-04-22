"""Background jobs: periodic analysis and daily retention."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.analysis.predict import run_predictions_all_devices
from app.config import settings
from app.database import SessionLocal
from app.jobs import retention

logger = logging.getLogger(__name__)

# Smallest allowed analysis period (avoids tight spin / zero).
_MIN_ANALYSIS_INTERVAL_SECONDS = 1.0


def _scheduled_analysis_job() -> None:
    db = SessionLocal()
    try:
        logger.info("Scheduled predictive maintenance analysis starting")
        run_predictions_all_devices(db)
    except Exception:
        logger.exception("Scheduled analysis job failed")
    finally:
        db.close()


def _scheduled_retention_job() -> None:
    try:
        n = 1
        batches = 0
        # Cap batches so one cron tick cannot run unbounded if the backlog is huge.
        while n > 0 and batches < 50:
            n = retention.run_sensor_readings_retention()
            batches += 1
    except Exception:
        logger.exception("Scheduled retention job failed")


def start_scheduler() -> BackgroundScheduler | None:
    if not settings.scheduler_enabled or settings.testing:
        logger.info("Background scheduler disabled (scheduler_enabled=%s testing=%s)", settings.scheduler_enabled, settings.testing)
        return None

    sched = BackgroundScheduler()
    interval_minutes = float(settings.maintenance_analysis_interval_minutes)
    interval_sec = max(
        _MIN_ANALYSIS_INTERVAL_SECONDS,
        interval_minutes * 60.0,
    )
    sched.add_job(
        _scheduled_analysis_job,
        IntervalTrigger(seconds=interval_sec),
        id="maintenance_analysis",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        _scheduled_retention_job,
        CronTrigger(
            hour=settings.retention_job_hour_utc,
            minute=settings.retention_job_minute_utc,
        ),
        id="sensor_readings_retention",
        replace_existing=True,
    )
    sched.start()
    logger.info(
        "Scheduler started: analysis every %s s (%.6g min); retention daily at %02d:%02d UTC",
        interval_sec,
        interval_sec / 60.0,
        settings.retention_job_hour_utc,
        settings.retention_job_minute_utc,
    )
    return sched
