import os

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/maintenance"

    @field_validator("database_url", mode="before")
    @classmethod
    def use_sqlite_when_testing(cls, v: str) -> str:
        if os.environ.get("TESTING") == "1":
            return "sqlite:///:memory:"
        return v

    # Allen-Bradley CompactLogix (EtherNet/IP via pycomm3). Use PLC IP address.
    plc_host: str = "192.168.1.10"

    plc_poll_interval_seconds: float = 10.0

    # Set to True to log SQL (useful for dev; set False in production).
    db_echo: bool = False

    notifications_enabled: bool = True

    # Email (SMTP). Leave smtp_host empty to disable email sending.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""  # e.g. "alerts@yourdomain.com"

    class Config:
        env_file = ".env"


settings = Settings()