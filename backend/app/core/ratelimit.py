"""In-process API rate limiting for public deployments.

The API has no authentication, and several endpoints fan out to third-party services
(yfinance, Polymarket/Reddit, Gemini) or run heavy simulations. When the app is exposed
on the internet these limits keep a single client from exhausting the server or the
owner's Gemini quota.

Design notes
------------
* Sliding-window counters keyed by client IP, held in memory. This is correct for the
  single-process deployment shipped in the Dockerfile; with several workers/instances
  each one enforces its own limit (use a shared store such as Redis for that case).
* Client IP comes from ``request.client.host``. Behind a reverse proxy run uvicorn with
  ``--proxy-headers`` so this is the real client and not the proxy (the Dockerfile does).
* A limit of 0 disables that rule.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Deque, Dict, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Endpoints that call paid / rate-limited LLM APIs.
ASSISTANT_PATHS = ("/api/v1/portfolio/diverse-risk/ask",)

# CPU-heavy or external-fan-out endpoints.
HEAVY_PATHS = (
    "/api/v1/portfolio/simulate-10y-forecast",
    "/api/v1/backtesting/portfolio",
    "/api/v1/portfolio/diverse-risk",
    "/api/v1/risk/bankruptcy",
    "/api/v1/risk/tracker",
    "/api/v1/sentiment/crowd",
    "/api/v1/forecasting/run",
)

EXEMPT_PATHS = ("/api/v1/health",)


class SlidingWindowLimiter:
    """Thread-safe "at most ``limit`` hits per ``window`` seconds per key" limiter."""

    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.limit = int(limit)
        self.window = float(window_seconds)
        self._clock = clock
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()
        self._calls = 0

    def hit(self, key: str) -> Tuple[bool, float]:
        """Record a hit. Returns ``(allowed, retry_after_seconds)``."""
        if self.limit <= 0:
            return True, 0.0
        now = self._clock()
        cutoff = now - self.window
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                return False, max(0.0, q[0] + self.window - now)
            q.append(now)
            self._calls += 1
            if self._calls % 1024 == 0:
                self._evict_idle(cutoff)
            return True, 0.0

    def _evict_idle(self, cutoff: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]:
            del self._hits[k]


class DailyBudget:
    """Global (all clients) counter that resets at 00:00 UTC. Process-local, best effort."""

    def __init__(self, limit: int, today: Callable[[], str] = lambda: datetime.now(timezone.utc).date().isoformat()):
        self.limit = int(limit)
        self._today = today
        self._day = today()
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        if self.limit <= 0:
            return True
        with self._lock:
            day = self._today()
            if day != self._day:
                self._day, self._used = day, 0
            if self._used >= self.limit:
                return False
            self._used += 1
            return True


@dataclass(frozen=True)
class RateLimitConfig:
    general_per_minute: int = 240
    heavy_per_minute: int = 20
    assistant_per_minute: int = 6
    assistant_per_day: int = 200


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    return 86400 - (now.hour * 3600 + now.minute * 60 + now.second)


def _too_many(detail: str, retry_after: float) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": detail},
        headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
    )


def install_rate_limiting(app: FastAPI, cfg: RateLimitConfig, clock: Optional[Callable[[], float]] = None) -> None:
    kw = {"clock": clock} if clock else {}
    general = SlidingWindowLimiter(cfg.general_per_minute, 60, **kw)
    heavy = SlidingWindowLimiter(cfg.heavy_per_minute, 60, **kw)
    assistant = SlidingWindowLimiter(cfg.assistant_per_minute, 60, **kw)
    assistant_day = DailyBudget(cfg.assistant_per_day)
    app.state.rate_limiters = {"general": general, "heavy": heavy, "assistant": assistant, "assistant_day": assistant_day}

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        if not path.startswith("/api/") or path in EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        client = request.client.host if request.client else "unknown"

        ok, retry = general.hit(client)
        if not ok:
            return _too_many("Too many requests. Please slow down and try again shortly.", retry)

        if path in HEAVY_PATHS:
            ok, retry = heavy.hit(client)
            if not ok:
                return _too_many("This analysis is rate-limited. Please wait a moment before running it again.", retry)

        if path in ASSISTANT_PATHS:
            ok, retry = assistant.hit(client)
            if not ok:
                return _too_many("AI assistant rate limit reached. Please wait before asking again.", retry)
            if not assistant_day.consume():
                return _too_many(
                    "The AI assistant has reached its daily usage budget on this server. Please try again tomorrow.",
                    _seconds_until_utc_midnight(),
                )

        return await call_next(request)
