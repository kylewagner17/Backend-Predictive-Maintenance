import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/maintenance"

    @field_validator("database_url", mode="before")
    @classmethod
    def use_sqlite_when_testing(cls, v: str) -> str:
        if os.environ.get("TESTING") == "1":
            return os.environ.get(
                "TESTING_DATABASE_URL",
                "sqlite:///./poc_maintenance.db",
            )
        return v

    # Allen-Bradley CompactLogix (EtherNet/IP via pycomm3). Use PLC IP address.
    plc_host: str = "192.168.0.4"
    #.1.10 is previous

    plc_poll_interval_seconds: float = 10.0

    # POC synthetic ingest (used when TESTING=1)
    synthetic_poll_interval_seconds: float = 5.0
    poc_analysis_interval_seconds: float = 30.0

    # Set to True to log SQL (useful for dev; set False in production).
    db_echo: bool = False

    notifications_enabled: bool = True

    # Email (SMTP). Leave smtp_host empty to disable email sending.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""  # e.g. "alerts@yourdomain.com"


settings = Settings()