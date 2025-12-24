from __future__ import annotations

from pydantic import AnyHttpUrl, Field
from pydantic.aliases import AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, case_sensitive=False)

    database_url: str = Field(validation_alias=AliasChoices("DATABASE_URL", "database_url"))
    osrs_base_url: AnyHttpUrl = Field(
        default="https://prices.runescape.wiki/api/v1/osrs",
        validation_alias=AliasChoices("OSRS_BASE_URL", "osrs_base_url"),
    )
    osrs_user_agent: str = Field(validation_alias=AliasChoices("OSRS_USER_AGENT", "osrs_user_agent"))

    cors_allowed_origins: str | None = Field(
        default=None, validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS", "cors_allowed_origins")
    )

    def sqlalchemy_database_url(self) -> str:
        """
        Railway Postgres commonly provides DATABASE_URL like:
        - postgresql://...
        - postgres://...

        SQLAlchemy 2 defaults `postgresql://` to psycopg2. We use psycopg3, so
        normalize to `postgresql+psycopg://` unless a driver is already specified.
        """
        url = self.database_url
        if "://" not in url:
            return url
        scheme, rest = url.split("://", 1)
        if "+" in scheme:
            return url
        if scheme in ("postgres", "postgresql"):
            return f"postgresql+psycopg://{rest}"
        return url


settings = Settings()


