from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    antares_server: str = "host.docker.internal"
    antares_port: int = 3307
    antares_database: str = "datosipspymr"
    antares_user: str = "root"
    antares_password: str = "AntaresDB_2024!"

    agenda_system_url: str = "http://agenda-system-api-1:8000"
    sync_api_key: str = "changeme-sync-api-key"

    sync_interval_seconds: int = 300
    sync_lookback_hours: int = 24

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
