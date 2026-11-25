"""Vnstock v6 adapter for Vietnam equities (HOSE / HNX).

Uses the open-source vnstock>=6.0 Python ecosystem when installed in the runtime
environment. Never labels historical or unverified intraday snapshots as LIVE.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from app.core.calendar import get_market_session
from app.core.models import DataStatus, OHLCVBar, OHLCVResponse, QuoteResponse
from app.core.symbology import resolve_effective_exchange
from app.data.base import BaseMarketDataProvider, ProviderCapabilities
from app.data.freshness import classify_quote_freshness, validate_ohlcv_bars


class VnstockProvider(BaseMarketDataProvider):
    capabilities = ProviderCapabilities(
        provider_id="vnstock_v6",
        display_name="Vnstock v6 (Vietnam Equities)",
        supported_mics=("XSTC", "XHAI"),
        supports_live_quotes=False,  # Live verified streaming is delegated to SSI FastConnect Data
        supports_websocket=False,
        supports_historical_ohlcv=True,
        is_educational_fallback_only=False,
        requires_api_key=False,
        requires_paid_plan_for_live=False,
        official_docs_url="https://vnstocks.com/docs/vnstock/v6",
    )

    def __init__(self, source: str = "VCI", api_key: Optional[str] = None) -> None:
        self._source = source
        self._api_key = api_key

    def _import_vnstock(self):
        try:
            import vnstock  # type: ignore
            return vnstock
        except ImportError:
            return None

    def is_configured(self) -> bool:
        return self._import_vnstock() is not None

    def get_quote(self, ticker: str, exchange_mic: str) -> QuoteResponse:
        now_utc = datetime.now(timezone.utc)
        eff_mic, _, is_suspended, migration_note = resolve_effective_exchange(
            ticker, exchange_mic, as_of=now_utc.date()
        )
        instrument_id = f"{eff_mic}:{ticker}"
        session_info = get_market_session(
            eff_mic, now_utc=now_utc, is_migration_suspended=is_suspended
        )

        if not self.is_configured():
            return QuoteResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=eff_mic,
                currency="VND",
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session_info.session,
                retrieval_timestamp=now_utc,
                unavailable_reason=(
                    "Python package 'vnstock' is not installed in this environment. "
                    "Install via 'pip install vnstock>=6.0' to enable Vietnam market retrieval."
                ),
            )

        # Fetch latest daily bar as delayed/historical quote (never LIVE)
        ohlcv = self.get_ohlcv(
            ticker=ticker,
            exchange_mic=eff_mic,
            interval="1d",
            start_date=now_utc.date() - timedelta(days=10),
            end_date=now_utc.date(),
        )
        if not ohlcv.bars:
            return QuoteResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=eff_mic,
                currency="VND",
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session_info.session,
                retrieval_timestamp=now_utc,
                unavailable_reason=ohlcv.unavailable_reason or "No recent Vietnam price bars returned.",
            )

        latest = ohlcv.bars[-1]
        prev = ohlcv.bars[-2] if len(ohlcv.bars) >= 2 else None
        change = (latest.close - prev.close) if prev else None
        change_pct = ((change / prev.close) * 100.0) if (change is not None and prev and prev.close) else None

        status, delay_min, warnings = classify_quote_freshness(
            price=latest.close,
            market_timestamp=latest.timestamp,
            retrieval_timestamp=now_utc,
            market_session=session_info.session,
            provider_entitled_live=False,
            provider_declared_delay_minutes=15,
        )
        if migration_note:
            warnings.append(migration_note)

        return QuoteResponse(
            instrument_id=instrument_id,
            ticker=ticker,
            exchange_mic=eff_mic,
            currency="VND",
            provider=self.capabilities.provider_id,
            data_status=status,
            delay_minutes=delay_min,
            market_session=session_info.session,
            market_timestamp=latest.timestamp,
            retrieval_timestamp=now_utc,
            price=latest.close,
            previous_close=prev.close if prev else None,
            change=change,
            change_percent=change_pct,
            open=latest.open,
            high=latest.high,
            low=latest.low,
            volume=latest.volume,
            warnings=warnings,
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
        eff_mic, _, _, migration_note = resolve_effective_exchange(
            ticker, exchange_mic, as_of=end_date or now_utc.date()
        )
        instrument_id = f"{eff_mic}:{ticker}"

        vnstock_mod = self._import_vnstock()
        if vnstock_mod is None:
            return OHLCVResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=eff_mic,
                currency="VND",
                interval=interval,
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                retrieval_timestamp=now_utc,
                unavailable_reason="Python package 'vnstock' is not installed in this environment.",
            )

        end_d = end_date or now_utc.date()
        start_d = start_date or (end_d - timedelta(days=180))

        try:
            stock = vnstock_mod.Vnstock().stock(symbol=ticker, source=self._source)
            df = stock.quote.history(
                start=start_d.isoformat(),
                end=end_d.isoformat(),
                interval=interval,
            )
            raw_bars: List[OHLCVBar] = []
            for _, row in df.iterrows():
                ts = datetime.fromisoformat(str(row["time"])).replace(tzinfo=timezone.utc)
                raw_bars.append(
                    OHLCVBar(
                        timestamp=ts,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        adjusted_close=float(row["close"]),
                        volume=int(row["volume"]),
                    )
                )
            bars, warnings = validate_ohlcv_bars(raw_bars)
            if migration_note:
                warnings.append(migration_note)
            if not bars:
                return OHLCVResponse(
                    instrument_id=instrument_id,
                    ticker=ticker,
                    exchange_mic=eff_mic,
                    currency="VND",
                    interval=interval,
                    provider=self.capabilities.provider_id,
                    data_status=DataStatus.DATA_UNAVAILABLE,
                    retrieval_timestamp=now_utc,
                    warnings=warnings,
                    unavailable_reason="Vnstock returned zero valid OHLCV bars.",
                )
            return OHLCVResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=eff_mic,
                currency="VND",
                interval=interval,
                provider=self.capabilities.provider_id,
                data_status=DataStatus.HISTORICAL,
                market_timestamp=bars[-1].timestamp,
                retrieval_timestamp=now_utc,
                bars=bars,
                warnings=warnings,
            )
        except Exception as exc:
            return OHLCVResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=eff_mic,
                currency="VND",
                interval=interval,
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                retrieval_timestamp=now_utc,
                unavailable_reason=f"Vnstock retrieval failed: {exc}",
            )
