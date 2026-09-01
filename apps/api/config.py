from __future__ import annotations

import os
from functools import lru_cache


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def sqlalchemy_url(url: str) -> str:
    if "+psycopg" in url or "+asyncpg" in url or "+pg8000" in url:
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Settings:
    def __init__(self) -> None:
        url = os.environ.get(
            "DATABASE_URL",
            "postgresql://app:app@127.0.0.1:55434/inkworks",
        )
        self.database_url = sqlalchemy_url(url)
        self.port = int(os.environ.get("PORT", "3108"))
        self.jwt_secret = os.environ.get("JWT_ACCESS_SECRET", "inkworks-demo-access-secret-change-me")
        self.jwt_access_ttl_seconds = int(os.environ.get("JWT_ACCESS_TTL_SECONDS", "900"))
        self.refresh_ttl_seconds = int(os.environ.get("JWT_REFRESH_TTL_SECONDS", str(7 * 24 * 3600)))
        self.bcrypt_rounds = int(os.environ.get("BCRYPT_ROUNDS", "10"))
        self.demo_expose_tokens = _bool("DEMO_EXPOSE_TOKENS", True)
        self.verify_ttl_seconds = int(os.environ.get("VERIFY_TTL_SECONDS", str(24 * 3600)))
        self.reset_ttl_seconds = int(os.environ.get("RESET_TTL_SECONDS", str(3600)))
        self.delay_max_ms = float(os.environ.get("DELAY_MAX_MS", "5000"))
        self.openai_api_key = os.environ.get("OPENAI_API_KEY") or ""
        self.static_dir = os.environ.get("STATIC_DIR")
        self.demo_email = os.environ.get("DEMO_EMAIL", "demo@inkworks.app")
        self.demo_password = os.environ.get("DEMO_PASSWORD", "InkDemo123!")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
