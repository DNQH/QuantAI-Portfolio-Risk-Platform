"""Abstract market data provider interface, TTL cache, and rate limiter.

Designed so paid providers (EODHD, Twelve Data, Massive) can be plugged in
later without modifying core application logic, analytics, or frontend contracts.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import date
from typing import Deque, Dict, Generic, List, Optional, Tuple, TypeVar

from app.core.models import Instrument, OHLCVResponse, QuoteResponse

T = TypeVar("T")


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    display_name: str
    supported_mics: Tuple[str, ...]
    supports_live_quotes: bool
    supports_websocket: bool
    supports_historical_ohlcv: bool
    is_educational_fallback_only: bool = False
    requires_api_key: bool = True
    requires_paid_plan_for_live: bool = False
    rate_limit_per_minute: Optional[int] = None
    official_docs_url: str = ""


class SlidingWindowRateLimiter:
    """Thread-safe sliding window rate limiter to respect provider quotas."""

    def __init__(self, max_calls: int, period_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self._timestamps: Deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            while self._timestamps and (now - self._timestamps[0]) >= self.period_seconds:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.max_calls:
                return False
            self._timestamps.append(now)
            return True


class TTLCache(Generic[T]):
    """Simple thread-safe in-memory TTL cache for market/FX responses."""

    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Tuple[float, T]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[T]:
        now = time.monotonic()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if now >= expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self.ttl_seconds, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class BaseMarketDataProvider(ABC):
    """Contract implemented by every equity market data provider."""

    capabilities: ProviderCapabilities

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required credentials/dependencies are available."""

    @abstractmethod
    def get_quote(self, ticker: str, exchange_mic: str) -> QuoteResponse:
        """Retrieve latest quote with strict freshness metadata."""

    @abstractmethod
    def get_ohlcv(
        self,
        ticker: str,
        exchange_mic: str,
        interval: str = "1d",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> OHLCVResponse:
        """Retrieve historical OHLCV bars with strict provenance metadata."""

    def search_instruments(self, query: str) -> List[Instrument]:
        """Optional provider-backed symbol search."""
        return []
