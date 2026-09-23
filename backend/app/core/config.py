import secrets
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, EmailStr, Field, SecretStr, model_validator
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
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "synapselms"
    jwt_audience: str = "synapselms-web"
    access_minutes: int = Field(default=15, ge=1, le=60)
    session_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool = False
    frontend_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5173")
    mail_backend: Literal["disabled", "smtp"] = "disabled"
    mail_from: EmailStr = "noreply@example.com"
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_security: Literal["none", "starttls", "ssl"] = "none"
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_timeout: int = Field(default=10, ge=1, le=30)
    verification_minutes: int = Field(default=1440, ge=5, le=1440)
    reset_minutes: int = Field(default=30, ge=5, le=60)
    database_url: str = "sqlite+aiosqlite:///./synapse.db"
    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=lambda: [AnyHttpUrl("http://localhost:5173")]
    )

    @model_validator(mode="after")
    def validate_security(self):
        production = self.env not in {"development", "test"}
        if self.jwt_secret is None or not self.jwt_secret.get_secret_value():
            if production:
                raise ValueError("SYNAPSE_JWT_SECRET is required outside development/test")
            # Development-only ephemeral key: restarting signs out existing clients.
            self.jwt_secret = SecretStr(secrets.token_urlsafe(48))
        key = self.jwt_secret.get_secret_value()
        if len(key) < 48 or len(set(key)) < 16:
            raise ValueError("JWT secret must be a random value of at least 48 characters")
        if production and (self.debug or not self.cookie_secure):
            raise ValueError("Production requires debug=false and cookie_secure=true")
        if production and any(origin.scheme != "https" for origin in self.cors_origins):
            raise ValueError("Production CORS origins must use HTTPS")
        if self.frontend_url.query or self.frontend_url.fragment or self.frontend_url.username:
            raise ValueError("Frontend URL must not contain credentials, query or fragment")
        if production and (
            self.frontend_url.scheme != "https"
            or self.mail_backend != "smtp"
            or self.smtp_security == "none"
        ):
            raise ValueError("Production requires HTTPS frontend and SMTP with TLS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
