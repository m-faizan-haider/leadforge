import os
from dataclasses import dataclass

from dotenv import load_dotenv
from loguru import logger

load_dotenv()


class ConfigError(RuntimeError):
    pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required. Add it to .env or your deployment environment.")
    return value


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    auth_secret: str
    allowed_origins: list[str]
    scraper_mode: str
    serpapi_key: str
    require_serpapi: bool


def load_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    database_url = require_env("DATABASE_URL")
    if database_url.startswith("sqlite") and app_env == "production":
        raise ConfigError("SQLite is not allowed in production. Set DATABASE_URL to hosted PostgreSQL.")
    auth_secret = require_env("AUTH_SECRET")
    allowed_origins_raw = require_env("ALLOWED_ORIGINS")
    allowed_origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
    if not allowed_origins:
        raise ConfigError("ALLOWED_ORIGINS must include at least one frontend origin.")

    scraper_mode = os.getenv("SCRAPER_MODE", "serpapi").strip().lower()
    if scraper_mode not in {"serpapi", "playwright"}:
        raise ConfigError("SCRAPER_MODE must be either 'serpapi' or 'playwright'.")

    serpapi_key = os.getenv("SERPAPI_KEY", "").strip()
    require_serpapi = env_bool("REQUIRE_SERPAPI", app_env == "production")
    if scraper_mode == "serpapi" and require_serpapi and not serpapi_key:
        raise ConfigError("SERPAPI_KEY is required when SCRAPER_MODE=serpapi in production.")

    if app_env == "production" and auth_secret in {"dev-only-change-me", "replace_with_a_long_random_secret"}:
        raise ConfigError("AUTH_SECRET must be changed for production.")

    return Settings(
        app_env=app_env,
        database_url=database_url,
        auth_secret=auth_secret,
        allowed_origins=allowed_origins,
        scraper_mode=scraper_mode,
        serpapi_key=serpapi_key,
        require_serpapi=require_serpapi,
    )


try:
    settings = load_settings()
except ConfigError as exc:
    logger.critical(str(exc))
    raise
