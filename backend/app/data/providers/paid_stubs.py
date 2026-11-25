"""Extensible provider stubs for future paid subscriptions (EODHD, Twelve Data, Massive).

These adapters conform to BaseMarketDataProvider so upgrading from the $0 stack
requires only setting environment variables and enabling the adapter—without
rewriting core analytics, portfolio, risk, or frontend code.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from app.core.calendar import get_market_session
from app.core.models import DataStatus, OHLCVResponse, QuoteResponse
from app.data.base import BaseMarketDataProvider, ProviderCapabilities


class _PaidProviderStub(BaseMarketDataProvider):
    # The quote adapters below are placeholders that always return DATA_UNAVAILABLE.
    # Flip this to True only once get_quote() really returns exchange real-time prices;
    # the coverage table uses it so an API key alone never produces a LIVE badge.
    live_quotes_implemented: bool = False

    def __init__(self, api_key: Optional[str]) -> None:
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_quote(self, ticker: str, exchange_mic: str) -> QuoteResponse:
        now_utc = datetime.now(timezone.utc)
        session = get_market_session(exchange_mic, now_utc=now_utc)
        return QuoteResponse(
            instrument_id=f"{exchange_mic}:{ticker}",
            ticker=ticker,
            exchange_mic=exchange_mic,
            currency="USD",
            provider=self.capabilities.provider_id,
            data_status=DataStatus.DATA_UNAVAILABLE,
            market_session=session.session,
            retrieval_timestamp=now_utc,
            unavailable_reason=(
                f"{self.capabilities.display_name} requires a paid API subscription "
                f"and is not activated in the $0 Phase 1 stack."
            ),
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
                f"{self.capabilities.display_name} requires a paid subscription "
                f"and is scheduled for optional Phase 7 global expansion."
            ),
        )


class EODHDProviderStub(_PaidProviderStub):
    capabilities = ProviderCapabilities(
        provider_id="eodhd",
        display_name="EODHD (Paid Global EOD/Intraday)",
        supported_mics=("XNYS", "XNAS", "XLON", "XETR", "XPAR", "XSWX", "XTKS", "XHKG", "XSTC", "XASX"),
        supports_live_quotes=True,
        supports_websocket=True,
        supports_historical_ohlcv=True,
        requires_api_key=True,
        requires_paid_plan_for_live=True,
        official_docs_url="https://eodhd.com/pricing",
    )


class TwelveDataProviderStub(_PaidProviderStub):
    capabilities = ProviderCapabilities(
        provider_id="twelvedata",
        display_name="Twelve Data (Paid Global Multi-Asset)",
        supported_mics=("XNYS", "XNAS", "XLON", "XETR", "XPAR", "XSWX", "XTKS", "XHKG", "XASX"),
        supports_live_quotes=True,
        supports_websocket=True,
        supports_historical_ohlcv=True,
        requires_api_key=True,
        requires_paid_plan_for_live=True,
        official_docs_url="https://twelvedata.com/pricing",
    )


class MassiveProviderStub(_PaidProviderStub):
    capabilities = ProviderCapabilities(
        provider_id="massive",
        display_name="Massive (formerly Polygon.io — Paid US)",
        supported_mics=("XNYS", "XNAS"),
        supports_live_quotes=True,
        supports_websocket=True,
        supports_historical_ohlcv=True,
        requires_api_key=True,
        requires_paid_plan_for_live=True,
        official_docs_url="https://massive.com/pricing",
    )
