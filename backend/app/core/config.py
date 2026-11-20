"""Environment-based configuration for QuantAI v1.5.0.

Loads .env reliably from repository root or current working directory with
override=True so non-empty values appended to .env always take effect.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _load_env_files() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    candidates = [
        Path(__file__).resolve().parents[3] / ".env",
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
    ]
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=True)


_load_env_files()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "QuantAI"
    app_version: str = "1.5.0"
    environment: str = field(default_factory=lambda: os.getenv("QUANTAI_ENV", "development"))
    database_path: str = field(
        default_factory=lambda: os.getenv(
            "QUANTAI_DB_PATH",
            str(Path(__file__).resolve().parents[2] / "quantai.db"),
        )
    )
    cors_origins: str = field(
        default_factory=lambda: os.getenv("QUANTAI_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    )

    finnhub_api_key: Optional[str] = field(default_factory=lambda: (os.getenv("FINNHUB_API_KEY") or "").strip() or None)
    ssi_api_key: Optional[str] = field(default_factory=lambda: (os.getenv("SSI_API_KEY") or "").strip() or None)
    ssi_api_secret: Optional[str] = field(default_factory=lambda: (os.getenv("SSI_API_SECRET") or "").strip() or None)
    vnstock_api_key: Optional[str] = field(default_factory=lambda: (os.getenv("VNSTOCK_API_KEY") or "").strip() or None)
    vnstock_source: str = field(default_factory=lambda: os.getenv("VNSTOCK_SOURCE", "VCI"))

    frankfurter_base_url: str = field(
        default_factory=lambda: os.getenv("FRANKFURTER_BASE_URL", "https://api.frankfurter.dev/v2")
    )
    enable_yfinance_fallback: bool = field(
        default_factory=lambda: _env_bool("QUANTAI_ENABLE_YFINANCE_FALLBACK", True)
    )

    gemini_api_key: Optional[str] = field(default_factory=lambda: (os.getenv("GEMINI_API_KEY") or "").strip() or None)
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))

    eodhd_api_key: Optional[str] = field(default_factory=lambda: (os.getenv("EODHD_API_KEY") or "").strip() or None)
    twelvedata_api_key: Optional[str] = field(default_factory=lambda: (os.getenv("TWELVEDATA_API_KEY") or "").strip() or None)
    massive_api_key: Optional[str] = field(default_factory=lambda: (os.getenv("MASSIVE_API_KEY") or "").strip() or None)

    http_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("QUANTAI_HTTP_TIMEOUT", "20.0"))
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    _load_env_files()
    return Settings()
