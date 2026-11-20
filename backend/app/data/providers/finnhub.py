"""Finnhub market data provider adapter (US equities free tier).

Official documentation verified (finnhub.io/docs/api):
  - Free tier: 60 calls/min (30/s burst), /quote, /search, /stock/symbol,
    /stock/market-status, and WebSocket wss://ws.finnhub.io (1 connection/key)
    for real-time US stock trades.
  - Historical /stock/candle OHLCV is NOT included on the free tier and returns
    DATA_UNAVAILABLE here rather than fabricating or silently substituting data.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Callable, List, Optional

import httpx

from app.core.calendar import get_market_session
from app.core.models import (
    AssetType,
    DataStatus,
    Instrument,
    OHLCVResponse,
    QuoteResponse,
)
from app.data.base import BaseMarketDataProvider, ProviderCapabilities, SlidingWindowRateLimiter
from app.data.freshness import classify_quote_freshness

logger = logging.getLogger("quantai.finnhub")
FINNHUB_REST_BASE = "https://finnhub.io/api/v1"
FINNHUB_WS_URL = "wss://ws.finnhub.io"


class FinnhubProvider(BaseMarketDataProvider):
    capabilities = ProviderCapabilities(
        provider_id="finnhub",
        display_name="Finnhub (Free US Tier)",
        supported_mics=("XNYS", "XNAS"),
        supports_live_quotes=True,
        supports_websocket=True,
        supports_historical_ohlcv=False,  # /stock/candle requires paid Finnhub plan
        is_educational_fallback_only=False,
        requires_api_key=True,
        requires_paid_plan_for_live=False,
        rate_limit_per_minute=60,
        official_docs_url="https://finnhub.io/docs/api",
    )

    def __init__(
        self,
        api_key: Optional[str],
        timeout: float = 10.0,
        http_get: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._http_get = http_get or httpx.get
        self._limiter = SlidingWindowRateLimiter(max_calls=55, period_seconds=60.0)

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_websocket_url(self) -> Optional[str]:
        if not self._api_key:
            return None
        return f"{FINNHUB_WS_URL}?token={self._api_key}"

    def get_quote(self, ticker: str, exchange_mic: str) -> QuoteResponse:
        now_utc = datetime.now(timezone.utc)
        instrument_id = f"{exchange_mic}:{ticker}"
        session_info = get_market_session(exchange_mic, now_utc=now_utc)

        if exchange_mic not in self.capabilities.supported_mics:
            return QuoteResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=exchange_mic,
                currency="USD",
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session_info.session,
                retrieval_timestamp=now_utc,
                unavailable_reason=f"Finnhub free tier supports US equities (XNYS/XNAS), not {exchange_mic}.",
            )

        if not self.is_configured():
            return QuoteResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=exchange_mic,
                currency="USD",
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session_info.session,
                retrieval_timestamp=now_utc,
                unavailable_reason="FINNHUB_API_KEY environment variable is not configured.",
            )

        if not self._limiter.allow():
            return QuoteResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=exchange_mic,
                currency="USD",
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session_info.session,
                retrieval_timestamp=now_utc,
                unavailable_reason="Finnhub free-tier rate limit (60 calls/min) temporarily reached.",
            )

        try:
            resp = self._http_get(
                f"{FINNHUB_REST_BASE}/quote",
                params={"symbol": ticker, "token": self._api_key},
                timeout=self._timeout,
            )
            if getattr(resp, "status_code", 200) != 200:
                return QuoteResponse(
                    instrument_id=instrument_id,
                    ticker=ticker,
                    exchange_mic=exchange_mic,
                    currency="USD",
                    provider=self.capabilities.provider_id,
                    data_status=DataStatus.DATA_UNAVAILABLE,
                    market_session=session_info.session,
                    retrieval_timestamp=now_utc,
                    unavailable_reason=f"Finnhub HTTP {resp.status_code} error.",
                )
            payload = resp.json()
        except Exception as exc:
            return QuoteResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=exchange_mic,
                currency="USD",
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session_info.session,
                retrieval_timestamp=now_utc,
                unavailable_reason=f"Finnhub connection error: {exc}",
            )

        price = payload.get("c")
        ts_unix = payload.get("t")
        market_ts = (
            datetime.fromtimestamp(ts_unix, tz=timezone.utc)
            if isinstance(ts_unix, (int, float)) and ts_unix > 0
            else None
        )

        status, delay_min, warnings = classify_quote_freshness(
            price=price,
            market_timestamp=market_ts,
            retrieval_timestamp=now_utc,
            market_session=session_info.session,
            provider_entitled_live=True,
            max_live_age_seconds=300,
        )

        return QuoteResponse(
            instrument_id=instrument_id,
            ticker=ticker,
            exchange_mic=exchange_mic,
            currency="USD",
            provider=self.capabilities.provider_id,
            data_status=status,
            delay_minutes=delay_min,
            market_session=session_info.session,
            market_timestamp=market_ts,
            retrieval_timestamp=now_utc,
            price=price if status != DataStatus.DATA_UNAVAILABLE else None,
            previous_close=payload.get("pc"),
            change=payload.get("d"),
            change_percent=payload.get("dp"),
            open=payload.get("o"),
            high=payload.get("h"),
            low=payload.get("l"),
            warnings=warnings,
            unavailable_reason="Invalid or zero price returned by Finnhub." if status == DataStatus.DATA_UNAVAILABLE else None,
        )

    def get_ohlcv(
        self,
        ticker: str,
        exchange_mic: str,
        interval: str = "1d",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> OHLCVResponse:
        now_utc = datetime.now(timezone.utc)
        return OHLCVResponse(
            instrument_id=f"{exchange_mic}:{ticker}",
            ticker=ticker,
            exchange_mic=exchange_mic,
            currency="USD",
            interval=interval,
            provider=self.capabilities.provider_id,
            data_status=DataStatus.DATA_UNAVAILABLE,
            retrieval_timestamp=now_utc,
            unavailable_reason=(
                "Finnhub historical /stock/candle endpoint requires a paid subscription. "
                "Use an authorized historical provider or explicitly enable yfinance educational fallback."
            ),
        )

    def search_instruments(self, query: str) -> List[Instrument]:
        if not self.is_configured() or not query.strip() or not self._limiter.allow():
            return []
        try:
            resp = self._http_get(
                f"{FINNHUB_REST_BASE}/search",
                params={"q": query.strip(), "token": self._api_key},
                timeout=self._timeout,
            )
            if getattr(resp, "status_code", 200) != 200:
                return []
            items = resp.json().get("result", [])
        except Exception:
            return []

        results: List[Instrument] = []
        for item in items[:15]:
            sym = str(item.get("symbol", "")).strip().upper()
            if not sym or "." in sym or ":" in sym:
                continue  # Free-tier scope: US primary symbols only
            results.append(
                Instrument(
                    instrument_id=f"XNAS:{sym}",
                    ticker=sym,
                    exchange_mic="XNAS",
                    exchange_acronym="US",
                    company_name=str(item.get("description") or sym),
                    country="United States",
                    currency="USD",
                    asset_type=AssetType.EQUITY,
                    timezone="America/New_York",
                )
            )
        return results
