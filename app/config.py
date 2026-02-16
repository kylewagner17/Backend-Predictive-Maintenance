from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/maintenance"

    # PLC Modbus connection (override via .env in production)
    plc_host: str = "127.0.0.1"
    plc_port: int = 5020
    plc_start_register: int = 0
    plc_register_count: int = 4
    plc_device_id: int = 1

    # How often to poll the PLC (seconds). Avoid flooding the PLC and DB.
    plc_poll_interval_seconds: float = 10.0

    # Set to True to log SQL (useful for dev; set False in production).
    db_echo: bool = False

    class Config:
        env_file = ".env"


settings = Settings()