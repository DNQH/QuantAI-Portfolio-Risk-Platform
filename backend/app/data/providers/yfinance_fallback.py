"""Yahoo Finance (yfinance) educational historical fallback adapter.

STRICT POLICY:
  - Educational and historical research fallback ONLY.
  - NEVER labeled LIVE (maximum status is HISTORICAL for daily OHLCV or DELAYED for quotes).
  - NEVER silently substituted when a caller requests LIVE real-time data.
  - Unofficial endpoints: not licensed for commercial redistribution.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from app.core.calendar import get_market_session
from app.core.models import DataStatus, OHLCVBar, OHLCVResponse, QuoteResponse
from app.core.symbology import to_yfinance_symbol
from app.data.base import BaseMarketDataProvider, ProviderCapabilities
from app.data.freshness import classify_quote_freshness, validate_ohlcv_bars

EDUCATIONAL_WARNING = (
    "Source is Yahoo Finance (yfinance) unofficial educational/historical fallback. "
    "Not verified real-time and not licensed for commercial redistribution."
)


class YFinanceFallbackProvider(BaseMarketDataProvider):
    capabilities = ProviderCapabilities(
        provider_id="yfinance_fallback",
        display_name="Yahoo Finance (Educational Historical Fallback)",
        supported_mics=("XNYS", "XNAS", "XSTC", "XHAI"),
        supports_live_quotes=False,
        supports_websocket=False,
        supports_historical_ohlcv=True,
        is_educational_fallback_only=True,
        requires_api_key=False,
        requires_paid_plan_for_live=True,
        official_docs_url="https://github.com/ranaroussi/yfinance",
    )

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    def _import_yf(self):
        try:
            import yfinance as yf  # type: ignore
            return yf
        except ImportError:
            return None

    def is_configured(self) -> bool:
        return self._enabled and self._import_yf() is not None

    def get_quote(self, ticker: str, exchange_mic: str) -> QuoteResponse:
        now_utc = datetime.now(timezone.utc)
        instrument_id = f"{exchange_mic}:{ticker}"
        currency = "VND" if exchange_mic in {"XSTC", "XHAI"} else "USD"
        session_info = get_market_session(exchange_mic, now_utc=now_utc)

        if not self.is_configured():
            return QuoteResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=exchange_mic,
                currency=currency,
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session_info.session,
                retrieval_timestamp=now_utc,
                unavailable_reason="yfinance fallback is disabled or package 'yfinance' is not installed.",
            )

        ohlcv = self.get_ohlcv(
            ticker=ticker,
            exchange_mic=exchange_mic,
            interval="1d",
            start_date=now_utc.date() - timedelta(days=10),
            end_date=now_utc.date(),
        )
        if not ohlcv.bars:
            return QuoteResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=exchange_mic,
                currency=currency,
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session_info.session,
                retrieval_timestamp=now_utc,
                unavailable_reason=ohlcv.unavailable_reason or "No fallback quote available.",
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
        warnings.append(EDUCATIONAL_WARNING)

        return QuoteResponse(
            instrument_id=instrument_id,
            ticker=ticker,
            exchange_mic=exchange_mic,
            currency=currency,
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
        instrument_id = f"{exchange_mic}:{ticker}"
        currency = "VND" if exchange_mic in {"XSTC", "XHAI"} else "USD"
        yf = self._import_yf()

        if not self._enabled or yf is None:
            return OHLCVResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=exchange_mic,
                currency=currency,
                interval=interval,
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                retrieval_timestamp=now_utc,
                unavailable_reason="yfinance educational fallback is disabled or not installed.",
            )

        end_d = end_date or now_utc.date()
        start_d = start_date or (end_d - timedelta(days=180))
        yf_sym = to_yfinance_symbol(ticker, exchange_mic)

        try:
            df = yf.Ticker(yf_sym).history(
                start=start_d.isoformat(),
                end=(end_d + timedelta(days=1)).isoformat(),
                interval=interval,
                auto_adjust=False,
            )
            raw_bars: List[OHLCVBar] = []
            for idx, row in df.iterrows():
                ts = idx.to_pydatetime()
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                else:
                    ts = ts.astimezone(timezone.utc)
                raw_bars.append(
                    OHLCVBar(
                        timestamp=ts,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        adjusted_close=float(row.get("Adj Close", row["Close"])),
                        volume=int(row["Volume"]),
                    )
                )
            bars, warnings = validate_ohlcv_bars(raw_bars)
            warnings.append(EDUCATIONAL_WARNING)
            if not bars:
                return OHLCVResponse(
                    instrument_id=instrument_id,
                    ticker=ticker,
                    exchange_mic=exchange_mic,
                    currency=currency,
                    interval=interval,
                    provider=self.capabilities.provider_id,
                    data_status=DataStatus.DATA_UNAVAILABLE,
                    retrieval_timestamp=now_utc,
                    warnings=warnings,
                    unavailable_reason=f"yfinance returned no valid bars for {yf_sym}.",
                )
            return OHLCVResponse(
                instrument_id=instrument_id,
                ticker=ticker,
                exchange_mic=exchange_mic,
                currency=currency,
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
                exchange_mic=exchange_mic,
                currency=currency,
                interval=interval,
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                retrieval_timestamp=now_utc,
                unavailable_reason=f"yfinance retrieval error: {exc}",
            )
