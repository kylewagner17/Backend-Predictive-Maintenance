from pydantic import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/maintenance"

    class Config:
        env_file = ".env"

settings = Settings()