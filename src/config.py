from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    antares_server: str = "127.0.0.1"
    antares_port: int = 3306
    antares_database: str = "datosipspymr"
    antares_user: str = "agenda"
    antares_password: str = "AntaresDB_2024!"

    agenda_system_url: str = "http://agenda-system-api-1:8000"
    sync_api_key: str = "changeme-sync-api-key"

    sync_interval_seconds: int = 300
    sync_lookback_hours: int = 24

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @field_validator("*", mode="before")
    @classmethod
    def _empty_env_to_default(cls, value, info):
        if isinstance(value, str) and not value.strip():
            return cls.model_fields[info.field_name].default
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
