import os

from pydantic import AliasChoices, Field, field_validator, model_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # TESTING is parsed from .env here; it is not always exported to os.environ.
    testing: bool = Field(default=False, validation_alias=AliasChoices("TESTING", "testing"))

    @field_validator("scheduler_enabled", mode="before")
    @classmethod
    def coerce_scheduler_enabled(cls, v):
        if v is True or v == 1:
            return True
        if v is False or v == 0:
            return False
        if v is None or v == "":
            return True
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("0", "false", "no", "off"):
                return False
            if s in ("1", "true", "yes", "on"):
                return True
        return bool(v)

    @field_validator("testing", mode="before")
    @classmethod
    def coerce_testing(cls, v):
        if v is True or v == 1:
            return True
        if v is False or v == 0:
            return False
        if v is None or v == "":
            return False
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("0", "false", "no", "off"):
                return False
            if s in ("1", "true", "yes", "on"):
                return True
        return bool(v)

    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/maintenance",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def use_sqlite_when_testing(cls, v: str, info: ValidationInfo) -> str:
        if info.data.get("testing"):
            return os.environ.get(
                "TESTING_DATABASE_URL",
                "sqlite:///./poc_maintenance.db",
            )
        return v

    @model_validator(mode="after")
    def force_sqlite_database_url_when_testing(self):
        if self.testing:
            sqlite_url = os.environ.get(
                "TESTING_DATABASE_URL",
                "sqlite:///./poc_maintenance.db",
            )
            object.__setattr__(self, "database_url", sqlite_url)
        return self

    plc_host: str = Field(
        default="192.168.0.4",
        validation_alias=AliasChoices("PLC_HOST", "plc_host"),
    )
    plc_poll_interval_seconds: float = 10.0

    plc_status_write_enabled: bool = True
    plc_connect_timeout_seconds: float = 5.0
    plc_retry_attempts: int = 3
    plc_retry_base_delay_seconds: float = 1.0

    scheduler_enabled: bool = Field(default=True, validation_alias=AliasChoices("SCHEDULER_ENABLED", "scheduler_enabled"))
    # Supports sub-minute (e.g. 0.08333 ≈ 5 s). Used as minutes → seconds in scheduler.
    maintenance_analysis_interval_minutes: float = 15.0

    sensor_readings_retention_days: int = 90
    retention_batch_size: int = 2000
    retention_job_hour_utc: int = 2
    retention_job_minute_utc: int = 30

    synthetic_poll_interval_seconds: float = 5.0
    poc_analysis_interval_seconds: float = 30.0

    db_echo: bool = False
    log_level: str = "INFO"

    notifications_enabled: bool = True

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""  # e.g. "alerts@yourdomain.com"

    notification_alert_email: str = Field(
        default="",
        validation_alias=AliasChoices(
            "NOTIFICATION_ALERT_EMAIL",
            "notification_alert_email",
        ),
    )


settings = Settings()