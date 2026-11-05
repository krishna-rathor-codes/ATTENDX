from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AttendX API"
    environment: str = "development"
    secret_key: str = "dev-only-change-me"
    database_url: str = "sqlite:///./attendx.db"
    frontend_origin: str = "http://localhost:5173"
    access_token_expire_minutes: int = 480
    qr_session_minutes: int = 5

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
