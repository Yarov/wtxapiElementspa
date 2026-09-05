from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PHONE_NUMBER_ID: str
    ACCESS_TOKEN: str
    VERIFY_TOKEN: str
    APP_SECRET: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    GRAPH_API_VERSION: str = "v26.0"
    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"
    DEBUG: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
