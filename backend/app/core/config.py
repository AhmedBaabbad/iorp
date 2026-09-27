from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="IORP Backend", alias="APP_NAME")
    app_env: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        alias="APP_ENV",
    )
    debug: bool = Field(default=False, alias="DEBUG")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    database_url: str = Field(
        default="postgresql+psycopg://iorp:iorp@localhost:5432/iorp",
        alias="DATABASE_URL",
    )
    secret_key: str = Field(default="change-me-in-local-env", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_issuer: str = Field(default="iorp-api", min_length=3, alias="JWT_ISSUER")
    jwt_audience: str = Field(default="iorp-web", min_length=3, alias="JWT_AUDIENCE")
    tenant_access_token_minutes: int = Field(default=15, ge=1, le=60, alias="TENANT_ACCESS_TOKEN_MINUTES")
    platform_access_token_minutes: int = Field(default=10, ge=1, le=30, alias="PLATFORM_ACCESS_TOKEN_MINUTES")
    tenant_refresh_token_days: int = Field(default=7, ge=1, le=30, alias="TENANT_REFRESH_TOKEN_DAYS")
    platform_refresh_token_hours: int = Field(default=24, ge=1, le=168, alias="PLATFORM_REFRESH_TOKEN_HOURS")
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=120, alias="JWT_CLOCK_SKEW_SECONDS")
    refresh_cookie_name: str = Field(default="iorp_refresh", min_length=3, alias="REFRESH_COOKIE_NAME")
    refresh_cookie_secure: bool = Field(default=False, alias="REFRESH_COOKIE_SECURE")
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = Field(default="lax", alias="REFRESH_COOKIE_SAMESITE")
    refresh_rate_limit: int = Field(default=30, ge=1, le=120, alias="IORP_REFRESH_RATE_LIMIT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    bootstrap_token: str | None = Field(default=None, alias="IORP_BOOTSTRAP_TOKEN")
    uploads_dir: str = Field(default="uploads", alias="UPLOADS_DIR")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )
    login_max_attempts: int = Field(default=5, alias="IORP_LOGIN_MAX_ATTEMPTS")
    login_lockout_minutes: int = Field(default=15, alias="IORP_LOGIN_LOCKOUT_MINUTES")
    login_rate_limit: int = Field(default=10, alias="IORP_LOGIN_RATE_LIMIT")
    platform_login_max_attempts: int = Field(default=3, alias="IORP_PLATFORM_LOGIN_MAX_ATTEMPTS")
    platform_login_lockout_minutes: int = Field(default=30, alias="IORP_PLATFORM_LOGIN_LOCKOUT_MINUTES")
    platform_login_rate_limit: int = Field(default=5, alias="IORP_PLATFORM_LOGIN_RATE_LIMIT")
    trusted_proxy_ips: str = Field(default="127.0.0.1,::1", alias="IORP_TRUSTED_PROXY_IPS")
    email_mode: Literal["console", "smtp"] = Field(default="console", alias="EMAIL_MODE")
    email_from: str = Field(default="noreply@iorp.local", alias="EMAIL_FROM")
    smtp_host: str = Field(default="localhost", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, ge=1, le=65535, alias="SMTP_PORT")
    smtp_tls: bool = Field(default=True, alias="SMTP_TLS")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    password_reset_expiry_minutes: int = Field(default=30, ge=5, le=1440, alias="PASSWORD_RESET_EXPIRY_MINUTES")
    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")
    platform_frontend_url: str = Field(default="http://localhost:3000", alias="PLATFORM_FRONTEND_URL")

    @model_validator(mode="after")
    def validate_security_configuration(self):
        if self.refresh_cookie_samesite == "none" and not self.refresh_cookie_secure:
            raise ValueError("SameSite=None refresh cookies must be Secure")
        if self.app_env == "production":
            if not self.refresh_cookie_secure:
                raise ValueError("Production refresh cookies must be Secure")
            if self.secret_key == "change-me-in-local-env" or len(self.secret_key) < 32:
                raise ValueError("Production SECRET_KEY must be a strong runtime secret")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
