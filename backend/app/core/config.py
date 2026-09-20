from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SYNAPSE_",
        extra="ignore",
    )

    app_name: str = "SynapseLMS API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    env: str = "development"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./synapse.db"
    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=lambda: [AnyHttpUrl("http://localhost:5173")]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
