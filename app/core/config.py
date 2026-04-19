"""Application settings — all env-dependent values flow through `settings`."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseModel):
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = "claude-sonnet-4-6"
    database_url: str = "sqlite:///./structural_engineer.db"
    log_level: LogLevel = "INFO"
    log_dir: Path = Path("logs")
    log_to_file: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000


def _load_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./structural_engineer.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),  # type: ignore[arg-type]
        log_dir=Path(os.getenv("LOG_DIR", "logs")),
        log_to_file=os.getenv("LOG_TO_FILE", "true").lower() in {"1", "true", "yes"},
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=int(os.getenv("APP_PORT", "8000")),
    )


settings = _load_settings()
