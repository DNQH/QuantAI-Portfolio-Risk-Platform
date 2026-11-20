"""Multi-provider market data router and Market Data Coverage registry (v1.2.0).

Enforces strict provenance and zero-silent-fallback guarantees:
  - Never silently substitutes yfinance, historical, or synthetic data for LIVE requests.
  - Supports all 17 global exchanges for explicitly opted-in educational historical/delayed data.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from app.core.calendar import get_market_session
from app.core.config import Settings
from app.core.models import (
    CoverageStatus,
    DataStatus,
    ExchangeCoverageEntry,
    Instrument,
    OHLCVResponse,
    QuoteResponse,
)
from app.core.symbology import (
    YFINANCE_SUFFIX_BY_MIC,
    parse_instrument_id,
    resolve_effective_exchange,
    search_seed_instruments,
)
from app.data.providers.finnhub import FinnhubProvider
from app.data.providers.paid_stubs import (
    EODHDProviderStub,
    MassiveProviderStub,
    TwelveDataProviderStub,
)
from app.data.providers.ssi_fastconnect import SSIFastConnectProvider
from app.data.providers.vnstock_vn import VnstockProvider
from app.data.providers.yfinance_fallback import CURRENCY_BY_MIC, YFinanceFallbackProvider
from app.fx.frankfurter import FrankfurterFXProvider

ALL_SUPPORTED_MICS = frozenset(YFINANCE_SUFFIX_BY_MIC.keys())


class MarketDataRegistry:
    def __init__(
        self,
        settings: Settings,
        finnhub: Optional[FinnhubProvider] = None,
        vnstock: Optional[VnstockProvider] = None,
        ssi: Optional[SSIFastConnectProvider] = None,
        yfinance_fallback: Optional[YFinanceFallbackProvider] = None,
        frankfurter: Optional[FrankfurterFXProvider] = None,
    ) -> None:
        self.settings = settings
        self.finnhub = finnhub or FinnhubProvider(
            api_key=settings.finnhub_api_key, timeout=settings.http_timeout_seconds
        )
        self.vnstock = vnstock or VnstockProvider(
            source=settings.vnstock_source, api_key=settings.vnstock_api_key
        )
        self.ssi = ssi or SSIFastConnectProvider(
            api_key=settings.ssi_api_key,
            api_secret=settings.ssi_api_secret,
            timeout=settings.http_timeout_seconds,
        )
        self.yfinance_fallback = yfinance_fallback or YFinanceFallbackProvider(
            enabled=settings.enable_yfinance_fallback
        )
        self.frankfurter = frankfurter or FrankfurterFXProvider(
            base_url=settings.frankfurter_base_url,
            timeout=settings.http_timeout_seconds,
        )
        self.eodhd = EODHDProviderStub(settings.eodhd_api_key)
        self.twelvedata = TwelveDataProviderStub(settings.twelvedata_api_key)
        self.massive = MassiveProviderStub(settings.massive_api_key)

    def configured_provider_map(self) -> Dict[str, bool]:
        return {
            "finnhub": self.finnhub.is_configured(),
            "vnstock_v6": self.vnstock.is_configured(),
            "ssi_fastconnect_v3": self.ssi.is_configured(),
            "frankfurter_v2": True,
            "yfinance_fallback": self.yfinance_fallback.is_configured(),
            "eodhd_paid_hook": self.eodhd.is_configured(),
            "twelvedata_paid_hook": self.twelvedata.is_configured(),
            "massive_paid_hook": self.massive.is_configured(),
        }

    def search_instruments(
        self,
        query: str = "",
        exchange: Optional[str] = None,
        country: Optional[str] = None,
        sector: Optional[str] = None,
        as_of: Optional[date] = None,
    ) -> List[Instrument]:
        results = search_seed_instruments(
            query=query, exchange=exchange, country=country, sector=sector, as_of=as_of
        )
        if query.strip() and self.finnhub.is_configured() and (not country or "united states" in country.lower()):
            existing_ids = {i.instrument_id for i in results}
            for item in self.finnhub.search_instruments(query):
                if item.instrument_id not in existing_ids:
                    results.append(item)
                    existing_ids.add(item.instrument_id)
        return results

    def get_quote(
        self,
        instrument_id: str,
        require_live: bool = False,
        allow_educational_fallback: bool = False,
        as_of: Optional[date] = None,
    ) -> QuoteResponse:
        now_utc = datetime.now(timezone.utc)
        mic, ticker = parse_instrument_id(instrument_id)
        eff_mic, _, is_suspended, migration_note = resolve_effective_exchange(
            ticker, mic, as_of=as_of or now_utc.date()
        )
        canonical_id = f"{eff_mic}:{ticker}"
        currency = CURRENCY_BY_MIC.get(eff_mic, "USD")
        session = get_market_session(
            eff_mic, now_utc=now_utc, is_migration_suspended=is_suspended
        )

        if eff_mic not in ALL_SUPPORTED_MICS:
            return QuoteResponse(
                instrument_id=canonical_id,
                ticker=ticker,
                exchange_mic=eff_mic,
                currency=currency,
                provider="none",
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session.session,
                retrieval_timestamp=now_utc,
                unavailable_reason=f"Exchange {eff_mic} is not yet integrated.",
            )

        # US Equities (NYSE / NASDAQ)
        if eff_mic in {"XNYS", "XNAS"}:
            quote = self.finnhub.get_quote(ticker, eff_mic)
            if quote.data_status != DataStatus.DATA_UNAVAILABLE:
                if require_live and quote.data_status != DataStatus.LIVE:
                    return quote.copy(
                        update={
                            "data_status": DataStatus.DATA_UNAVAILABLE,
                            "price": None,
                            "unavailable_reason": f"Strict LIVE requested, but Finnhub returned {quote.data_status.value}.",
                        }
                    )
                return quote
            if require_live or not allow_educational_fallback:
                return quote
            return self.yfinance_fallback.get_quote(ticker, eff_mic)

        # Vietnam Equities (HOSE / HNX)
        if eff_mic in {"XSTC", "XHAI"}:
            if self.ssi.is_configured():
                quote = self.ssi.get_quote(ticker, eff_mic)
                if quote.data_status != DataStatus.DATA_UNAVAILABLE:
                    if require_live and quote.data_status != DataStatus.LIVE:
                        return quote.copy(
                            update={
                                "data_status": DataStatus.DATA_UNAVAILABLE,
                                "price": None,
                                "unavailable_reason": f"Strict LIVE requested, but SSI returned {quote.data_status.value}.",
                            }
                        )
                    return quote
            if require_live:
                return QuoteResponse(
                    instrument_id=canonical_id,
                    ticker=ticker,
                    exchange_mic=eff_mic,
                    currency="VND",
                    provider="ssi_fastconnect_v3",
                    data_status=DataStatus.DATA_UNAVAILABLE,
                    market_session=session.session,
                    retrieval_timestamp=now_utc,
                    warnings=[migration_note] if migration_note else [],
                    unavailable_reason="Strict LIVE Vietnam quote requires SSI FastConnect V3 credentials.",
                )
            if self.vnstock.is_configured():
                quote = self.vnstock.get_quote(ticker, eff_mic)
                if quote.data_status != DataStatus.DATA_UNAVAILABLE:
                    return quote
            if allow_educational_fallback:
                return self.yfinance_fallback.get_quote(ticker, eff_mic)
            return QuoteResponse(
                instrument_id=canonical_id,
                ticker=ticker,
                exchange_mic=eff_mic,
                currency="VND",
                provider="vnstock_v6",
                data_status=DataStatus.DATA_UNAVAILABLE,
                market_session=session.session,
                retrieval_timestamp=now_utc,
                warnings=[migration_note] if migration_note else [],
                unavailable_reason="Neither SSI FastConnect V3 credentials nor vnstock package are available.",
            )

        # Phase 7 Global Exchanges (Europe, Asia, ASEAN, Oceania)
        if not require_live and allow_educational_fallback:
            return self.yfinance_fallback.get_quote(ticker, eff_mic)

        return QuoteResponse(
            instrument_id=canonical_id,
            ticker=ticker,
            exchange_mic=eff_mic,
            currency=currency,
            provider="none",
            data_status=DataStatus.DATA_UNAVAILABLE,
            market_session=session.session,
            retrieval_timestamp=now_utc,
            unavailable_reason=f"Live quote for {eff_mic} requires a paid provider (EODHD / Twelve Data); enable educational fallback for delayed/historical quotes.",
        )

    def get_ohlcv(
        self,
        instrument_id: str,
        interval: str = "1d",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        period: Optional[str] = None,
        allow_educational_fallback: bool = True,
    ) -> OHLCVResponse:
        now_utc = datetime.now(timezone.utc)
        mic, ticker = parse_instrument_id(instrument_id)
        eff_mic, _, _, _ = resolve_effective_exchange(
            ticker, mic, as_of=end_date or now_utc.date()
        )
        canonical_id = f"{eff_mic}:{ticker}"
        currency = CURRENCY_BY_MIC.get(eff_mic, "USD")

        if eff_mic not in ALL_SUPPORTED_MICS:
            return OHLCVResponse(
                instrument_id=canonical_id,
                ticker=ticker,
                exchange_mic=eff_mic,
                currency=currency,
                interval=interval,
                provider="none",
                data_status=DataStatus.DATA_UNAVAILABLE,
                retrieval_timestamp=now_utc,
                unavailable_reason=f"Exchange {eff_mic} is not yet integrated.",
            )

        if eff_mic in {"XSTC", "XHAI"} and self.vnstock.is_configured() and period != "max":
            resp = self.vnstock.get_ohlcv(ticker, eff_mic, interval, start_date, end_date)
            if resp.data_status != DataStatus.DATA_UNAVAILABLE:
                return resp

        if allow_educational_fallback:
            return self.yfinance_fallback.get_ohlcv(
                ticker=ticker,
                exchange_mic=eff_mic,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                period=period,
            )

        return OHLCVResponse(
            instrument_id=canonical_id,
            ticker=ticker,
            exchange_mic=eff_mic,
            currency=currency,
            interval=interval,
            provider="none",
            data_status=DataStatus.DATA_UNAVAILABLE,
            retrieval_timestamp=now_utc,
            unavailable_reason="No licensed historical OHLCV provider configured; enable educational fallback or add a paid provider.",
        )

    def get_exchange_coverage(self) -> List[ExchangeCoverageEntry]:
        finnhub_ready = self.finnhub.is_configured()
        ssi_ready = self.ssi.is_configured()
        vnstock_ready = self.vnstock.is_configured()
        yf_ready = self.yfinance_fallback.is_configured()

        global_cov_status = CoverageStatus.DELAYED_AVAILABLE if yf_ready else CoverageStatus.NOT_SUPPORTED
        global_quote_status = DataStatus.DELAYED if yf_ready else DataStatus.DATA_UNAVAILABLE
        global_hist_status = DataStatus.HISTORICAL if yf_ready else DataStatus.DATA_UNAVAILABLE

        return [
            ExchangeCoverageEntry(
                exchange_mic="XNYS", exchange_acronym="NYSE", exchange_name="New York Stock Exchange",
                region="North America", country="United States", currency="USD", timezone="America/New_York",
                phase="Phase 1",
                coverage_status=CoverageStatus.LIVE_VERIFIED if finnhub_ready else (CoverageStatus.DELAYED_AVAILABLE if yf_ready else CoverageStatus.CREDENTIALS_REQUIRED),
                quote_data_status=DataStatus.LIVE if finnhub_ready else (DataStatus.DELAYED if yf_ready else DataStatus.DATA_UNAVAILABLE),
                historical_data_status=global_hist_status,
                primary_provider="Finnhub (Free US REST + WS)",
                fallback_provider="yfinance (Educational Historical / Delayed)",
                requires_credentials=True, requires_paid_plan_for_live=False,
                notes="Add FINNHUB_API_KEY in .env for verified LIVE US quotes & WS trades; full IPO history via yfinance educational fallback.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XNAS", exchange_acronym="NASDAQ", exchange_name="NASDAQ Stock Market",
                region="North America", country="United States", currency="USD", timezone="America/New_York",
                phase="Phase 1",
                coverage_status=CoverageStatus.LIVE_VERIFIED if finnhub_ready else (CoverageStatus.DELAYED_AVAILABLE if yf_ready else CoverageStatus.CREDENTIALS_REQUIRED),
                quote_data_status=DataStatus.LIVE if finnhub_ready else (DataStatus.DELAYED if yf_ready else DataStatus.DATA_UNAVAILABLE),
                historical_data_status=global_hist_status,
                primary_provider="Finnhub (Free US REST + WS)",
                fallback_provider="yfinance (Educational Historical / Delayed)",
                requires_credentials=True, requires_paid_plan_for_live=False,
                notes="Add FINNHUB_API_KEY in .env for verified LIVE US quotes & WS trades; full IPO history via yfinance educational fallback.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XSTC", exchange_acronym="HOSE", exchange_name="Ho Chi Minh Stock Exchange",
                region="Southeast Asia", country="Vietnam", currency="VND", timezone="Asia/Ho_Chi_Minh",
                phase="Phase 1",
                coverage_status=CoverageStatus.LIVE_VERIFIED if ssi_ready else (CoverageStatus.DELAYED_AVAILABLE if (vnstock_ready or yf_ready) else CoverageStatus.CREDENTIALS_REQUIRED),
                quote_data_status=DataStatus.LIVE if ssi_ready else DataStatus.DELAYED,
                historical_data_status=global_hist_status,
                primary_provider="SSI FastConnect V3 (Live) / Vnstock v6",
                fallback_provider="yfinance (.VN Educational Historical)",
                requires_credentials=True, requires_paid_plan_for_live=False,
                notes="LIVE requires SSI brokerage credentials ($0 API fee); historical & delayed quotes active via yfinance/Vnstock.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XHAI", exchange_acronym="HNX", exchange_name="Hanoi Stock Exchange",
                region="Southeast Asia", country="Vietnam", currency="VND", timezone="Asia/Ho_Chi_Minh",
                phase="Phase 1",
                coverage_status=CoverageStatus.LIVE_VERIFIED if ssi_ready else (CoverageStatus.DELAYED_AVAILABLE if (vnstock_ready or yf_ready) else CoverageStatus.CREDENTIALS_REQUIRED),
                quote_data_status=DataStatus.LIVE if ssi_ready else DataStatus.DELAYED,
                historical_data_status=global_hist_status,
                primary_provider="SSI FastConnect V3 (Live) / Vnstock v6",
                fallback_provider="yfinance (.VN Educational Historical)",
                requires_credentials=True, requires_paid_plan_for_live=False,
                notes="Active through 2026-12-23; effective-dated transfer to HOSE (XSTC) on 2026-12-28.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XLON", exchange_acronym="LSE", exchange_name="London Stock Exchange",
                region="Europe", country="United Kingdom", currency="GBP", timezone="Europe/London",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider="yfinance (.L Educational) / Paid: EODHD",
                fallback_provider="yfinance (.L)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.L); real-time requires paid EODHD/Twelve Data.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XETR", exchange_acronym="Xetra", exchange_name="Deutsche Börse Xetra",
                region="Europe", country="Germany", currency="EUR", timezone="Europe/Berlin",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider="yfinance (.DE Educational) / Paid: EODHD",
                fallback_provider="yfinance (.DE)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.DE); real-time requires paid EODHD/Twelve Data.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XTKS", exchange_acronym="TSE", exchange_name="Tokyo Stock Exchange",
                region="Asia", country="Japan", currency="JPY", timezone="Asia/Tokyo",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider="yfinance (.T Educational) / Paid: EODHD",
                fallback_provider="yfinance (.T)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.T); real-time requires paid EODHD/Twelve Data.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XHKG", exchange_acronym="HKEX", exchange_name="Hong Kong Exchanges and Clearing",
                region="Asia", country="Hong Kong", currency="HKD", timezone="Asia/Hong_Kong",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider="yfinance (.HK Educational) / Paid: EODHD",
                fallback_provider="yfinance (.HK)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.HK); real-time requires paid EODHD/Twelve Data.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XSES", exchange_acronym="SGX", exchange_name="Singapore Exchange",
                region="Southeast Asia", country="Singapore", currency="SGD", timezone="Asia/Singapore",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider="yfinance (.SI Educational) / Paid: EODHD",
                fallback_provider="yfinance (.SI)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.SI); real-time requires paid EODHD/Twelve Data.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XASX", exchange_acronym="ASX", exchange_name="Australian Securities Exchange",
                region="Oceania", country="Australia", currency="AUD", timezone="Australia/Sydney",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider="yfinance (.AX Educational) / Paid: EODHD",
                fallback_provider="yfinance (.AX)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.AX); real-time requires paid EODHD/Twelve Data.",
            ),
        ]
