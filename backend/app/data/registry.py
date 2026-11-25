"""Multi-provider market data router and Market Data Coverage registry (v1.2.0).

Enforces strict provenance and zero-silent-fallback guarantees:
  - Never silently substitutes yfinance, historical, or synthetic data for LIVE requests.
  - Supports all 17 global exchanges for explicitly opted-in educational historical/delayed data.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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


# Calendar days requested from SSI for the UI period selectors (max = full history).
_PERIOD_DAYS = {"1mo": 31, "6mo": 183, "1y": 366, "2y": 731, "5y": 1827, "10y": 3653}


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
            "ssi_fastconnect_data": self.ssi.is_configured(),
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
        q_clean = query.strip()
        if q_clean:
            existing_ids = {i.instrument_id for i in results}
            # 1. Finnhub live US search
            if self.finnhub.is_configured() and (not country or "united states" in country.lower()):
                for item in self.finnhub.search_instruments(q_clean):
                    if item.instrument_id not in existing_ids:
                        results.append(item)
                        existing_ids.add(item.instrument_id)
            # 2. Twelve Data global symbol_search across all exchanges (when key configured)
            if self.twelvedata.is_configured() and len(results) < 20:
                try:
                    import httpx
                    from app.core.models import AssetType
                    td_mic_map = {
                        "NYSE": ("XNYS", "United States", "USD", "America/New_York"),
                        "NASDAQ": ("XNAS", "United States", "USD", "America/New_York"),
                        "HOSE": ("XSTC", "Vietnam", "VND", "Asia/Ho_Chi_Minh"),
                        "HNX": ("XHAI", "Vietnam", "VND", "Asia/Ho_Chi_Minh"),
                        "UPCOM": ("XUPC", "Vietnam", "VND", "Asia/Ho_Chi_Minh"),
                        "LSE": ("XLON", "United Kingdom", "GBP", "Europe/London"),
                        "XETR": ("XETR", "Germany", "EUR", "Europe/Berlin"),
                        "TSE": ("XTKS", "Japan", "JPY", "Asia/Tokyo"),
                        "HKEX": ("XHKG", "Hong Kong", "HKD", "Asia/Hong_Kong"),
                        "SGX": ("XSES", "Singapore", "SGD", "Asia/Singapore"),
                        "ASX": ("XASX", "Australia", "AUD", "Australia/Sydney"),
                    }
                    with httpx.Client(timeout=3.0) as client:
                        resp = client.get(
                            "https://api.twelvedata.com/symbol_search",
                            params={"symbol": q_clean, "outputsize": 15, "apikey": self.settings.twelvedata_api_key},
                        )
                        if resp.status_code == 200:
                            for row in (resp.json().get("data") or [])[:15]:
                                sym = str(row.get("symbol") or "").strip().upper()
                                ex_name = str(row.get("exchange") or "").strip().upper()
                                ctry = str(row.get("country") or "").strip()
                                if not sym:
                                    continue
                                mic, resolved_ctry, ccy, tz = td_mic_map.get(
                                    ex_name,
                                    ("XNAS", ctry or "United States", str(row.get("currency") or "USD"), "America/New_York"),
                                )
                                if country and country.lower() not in resolved_ctry.lower():
                                    continue
                                if exchange and exchange.upper() not in {mic, ex_name}:
                                    continue
                                iid = f"{mic}:{sym}"
                                if iid in existing_ids:
                                    continue
                                existing_ids.add(iid)
                                results.append(
                                    Instrument(
                                        instrument_id=iid,
                                        ticker=sym,
                                        exchange_mic=mic,
                                        exchange_acronym=ex_name or mic,
                                        company_name=str(row.get("instrument_name") or sym),
                                        country=resolved_ctry,
                                        currency=ccy,
                                        sector=None,
                                        industry=None,
                                        asset_type=AssetType.ETF if "etf" in str(row.get("instrument_type", "")).lower() else AssetType.EQUITY,
                                        timezone=tz,
                                    )
                                )
                except Exception:
                    pass
            # 3. Yahoo Finance global autocomplete fallback (zero-key, covers all listed stocks worldwide)
            if len(results) < 15:
                try:
                    import httpx
                    from app.core.models import AssetType
                    yf_ex_map = {
                        "NMS": ("XNAS", "NASDAQ", "United States", "USD", "America/New_York"),
                        "NGM": ("XNAS", "NASDAQ", "United States", "USD", "America/New_York"),
                        "NYQ": ("XNYS", "NYSE", "United States", "USD", "America/New_York"),
                        "PCX": ("XNYS", "NYSE", "United States", "USD", "America/New_York"),
                        "LSE": ("XLON", "LSE", "United Kingdom", "GBP", "Europe/London"),
                        "GER": ("XETR", "Xetra", "Germany", "EUR", "Europe/Berlin"),
                        "JPX": ("XTKS", "TSE", "Japan", "JPY", "Asia/Tokyo"),
                        "HKG": ("XHKG", "HKEX", "Hong Kong", "HKD", "Asia/Hong_Kong"),
                        "SES": ("XSES", "SGX", "Singapore", "SGD", "Asia/Singapore"),
                        "ASX": ("XASX", "ASX", "Australia", "AUD", "Australia/Sydney"),
                        "HOSE": ("XSTC", "HOSE", "Vietnam", "VND", "Asia/Ho_Chi_Minh"),
                    }
                    with httpx.Client(timeout=3.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
                        resp = client.get(
                            "https://query2.finance.yahoo.com/v1/finance/search",
                            params={"q": q_clean, "quotesCount": 12, "newsCount": 0},
                        )
                        if resp.status_code == 200:
                            for q_item in (resp.json().get("quotes") or []):
                                qtype = str(q_item.get("quoteType") or "").upper()
                                if qtype not in {"EQUITY", "ETF"}:
                                    continue
                                raw_sym = str(q_item.get("symbol") or "").upper()
                                ex_code = str(q_item.get("exchange") or "").upper()
                                clean_sym = raw_sym.split(".")[0]
                                if raw_sym.endswith(".VN"):
                                    mic, acr, ctry, ccy, tz = ("XSTC", "HOSE", "Vietnam", "VND", "Asia/Ho_Chi_Minh")
                                else:
                                    mic, acr, ctry, ccy, tz = yf_ex_map.get(
                                        ex_code, ("XNAS", ex_code or "GLOBAL", "United States", "USD", "America/New_York")
                                    )
                                if country and country.lower() not in ctry.lower():
                                    continue
                                if exchange and exchange.upper() not in {mic, acr.upper()}:
                                    continue
                                iid = f"{mic}:{clean_sym}"
                                if iid in existing_ids:
                                    continue
                                existing_ids.add(iid)
                                results.append(
                                    Instrument(
                                        instrument_id=iid,
                                        ticker=clean_sym,
                                        exchange_mic=mic,
                                        exchange_acronym=acr,
                                        company_name=str(q_item.get("shortname") or q_item.get("longname") or clean_sym),
                                        country=ctry,
                                        currency=ccy,
                                        sector=q_item.get("sector"),
                                        industry=q_item.get("industry"),
                                        asset_type=AssetType.ETF if qtype == "ETF" else AssetType.EQUITY,
                                        timezone=tz,
                                    )
                                )
                except Exception:
                    pass
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
        if eff_mic in {"XSTC", "XHAI", "XUPC"}:
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
                    provider="ssi_fastconnect_data",
                    data_status=DataStatus.DATA_UNAVAILABLE,
                    market_session=session.session,
                    retrieval_timestamp=now_utc,
                    warnings=[migration_note] if migration_note else [],
                    unavailable_reason="Strict LIVE Vietnam quote requires SSI FastConnect Data credentials.",
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
                unavailable_reason="Neither SSI FastConnect Data credentials nor vnstock package are available.",
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


    def _fetch_vietnam_public_ohlcv(
        self, ticker: str, exchange_mic: str, years: int = 10
    ) -> Optional[OHLCVResponse]:
        """Fetch daily OHLCV for HOSE/HNX/UPCOM from VNDirect dchart & TCBS public APIs (zero-key)."""
        import time as _time
        import httpx
        from app.core.models import OHLCVBar

        now_utc = datetime.now(timezone.utc)
        to_ts = int(_time.time())
        from_ts = to_ts - int(years * 365.25 * 86400)
        sym = ticker.upper().strip()
        bars: List[OHLCVBar] = []
        provider_used = "vndirect_dchart"

        try:
            with httpx.Client(timeout=8.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
                # 1. VNDirect dchart (covers all ~1,600 HOSE, HNX, UPCOM stocks)
                r = client.get(
                    "https://dchart-api.vndirect.com.vn/dchart/history",
                    params={"resolution": "D", "symbol": sym, "from": from_ts, "to": to_ts},
                )
                if r.status_code == 200:
                    d = r.json()
                    if d.get("s") == "ok" and d.get("t"):
                        ts_list, o_list, h_list, l_list, c_list, v_list = (
                            d.get("t", []), d.get("o", []), d.get("h", []),
                            d.get("l", []), d.get("c", []), d.get("v", []),
                        )
                        for i in range(len(ts_list)):
                            c_val = float(c_list[i])
                            if c_val <= 0:
                                continue
                            # VNDirect prices are in thousands of VND (e.g. 95.5 = 95,500 VND)
                            scale = 1000.0 if c_val < 1000.0 else 1.0
                            bars.append(
                                OHLCVBar(
                                    timestamp=datetime.fromtimestamp(int(ts_list[i]), tz=timezone.utc),
                                    open=round(float(o_list[i]) * scale, 2),
                                    high=round(float(h_list[i]) * scale, 2),
                                    low=round(float(l_list[i]) * scale, 2),
                                    close=round(c_val * scale, 2),
                                    adjusted_close=round(c_val * scale, 2),
                                    volume=float(v_list[i]) if i < len(v_list) and v_list[i] is not None else 0.0,
                                )
                            )
                # 2. Fallback: TCBS public long-term bars API (also covers HOSE, HNX, UPCOM)
                if len(bars) < 20:
                    provider_used = "tcbs_public"
                    r2 = client.get(
                        "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term",
                        params={"ticker": sym, "type": "stock", "resolution": "D", "from": from_ts, "to": to_ts},
                    )
                    if r2.status_code == 200:
                        rows = r2.json().get("data") or []
                        for row in rows:
                            c_val = float(row.get("close") or 0.0)
                            if c_val <= 0:
                                continue
                            raw_t = row.get("tradingDate") or ""
                            try:
                                dt = datetime.fromisoformat(str(raw_t).replace("Z", "+00:00"))
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                            except Exception:
                                continue
                            bars.append(
                                OHLCVBar(
                                    timestamp=dt,
                                    open=float(row.get("open") or c_val),
                                    high=float(row.get("high") or c_val),
                                    low=float(row.get("low") or c_val),
                                    close=c_val,
                                    adjusted_close=c_val,
                                    volume=float(row.get("volume") or 0.0),
                                )
                            )
        except Exception:
            pass

        if len(bars) >= 20:
            bars.sort(key=lambda b: b.timestamp)
            return OHLCVResponse(
                instrument_id=f"{exchange_mic}:{sym}",
                ticker=sym,
                exchange_mic=exchange_mic,
                currency="VND",
                interval="1d",
                provider=provider_used,
                data_status=DataStatus.HISTORICAL,
                retrieval_timestamp=now_utc,
                bars=bars,
            )
        return None

    def _fetch_twelvedata_ohlcv(
        self, ticker: str, exchange_mic: str
    ) -> Optional[OHLCVResponse]:
        """Fallback daily OHLCV via Twelve Data /time_series when yfinance misses a global ticker."""
        if not self.twelvedata.is_configured():
            return None
        import httpx
        from app.core.models import OHLCVBar

        now_utc = datetime.now(timezone.utc)
        sym = ticker.upper().strip()
        ex_map = {
            "XNYS": "NYSE", "XNAS": "NASDAQ", "XLON": "LSE", "XETR": "XETR",
            "XTKS": "TSE", "XHKG": "HKEX", "XSES": "SGX", "XASX": "ASX",
        }
        params = {
            "symbol": sym,
            "interval": "1day",
            "outputsize": 2600,
            "apikey": self.settings.twelvedata_api_key,
        }
        if exchange_mic in ex_map:
            params["exchange"] = ex_map[exchange_mic]
        try:
            with httpx.Client(timeout=8.0) as client:
                r = client.get("https://api.twelvedata.com/time_series", params=params)
                if r.status_code == 200:
                    vals = r.json().get("values") or []
                    bars: List[OHLCVBar] = []
                    for row in vals:
                        c_val = float(row.get("close") or 0.0)
                        if c_val <= 0:
                            continue
                        dt = datetime.fromisoformat(str(row["datetime"])[:10]).replace(tzinfo=timezone.utc)
                        bars.append(
                            OHLCVBar(
                                timestamp=dt,
                                open=float(row.get("open") or c_val),
                                high=float(row.get("high") or c_val),
                                low=float(row.get("low") or c_val),
                                close=c_val,
                                adjusted_close=c_val,
                                volume=float(row.get("volume") or 0.0),
                            )
                        )
                    if len(bars) >= 20:
                        bars.sort(key=lambda b: b.timestamp)
                        return OHLCVResponse(
                            instrument_id=f"{exchange_mic}:{sym}",
                            ticker=sym,
                            exchange_mic=exchange_mic,
                            currency=CURRENCY_BY_MIC.get(exchange_mic, "USD"),
                            interval="1d",
                            provider="twelvedata",
                            data_status=DataStatus.HISTORICAL,
                            retrieval_timestamp=now_utc,
                            bars=bars,
                        )
        except Exception:
            pass
        return None

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

        # Licensed Vietnam daily history from SSI FastConnect Data when credentials are configured.
        if eff_mic in {"XSTC", "XHAI", "XUPC"} and interval == "1d" and self.ssi.is_configured():
            ssi_start = start_date
            if ssi_start is None and period and period != "max":
                ssi_start = (end_date or now_utc.date()) - timedelta(days=_PERIOD_DAYS.get(period, 3660))
            resp = self.ssi.get_ohlcv(ticker, eff_mic, interval, ssi_start, end_date)
            if resp.data_status != DataStatus.DATA_UNAVAILABLE and len(resp.bars) >= 20:
                return resp

        if eff_mic in {"XSTC", "XHAI", "XUPC"} and self.vnstock.is_configured() and period != "max":
            resp = self.vnstock.get_ohlcv(ticker, eff_mic, interval, start_date, end_date)
            if resp.data_status != DataStatus.DATA_UNAVAILABLE:
                return resp

        # For Vietnam HNX/UPCOM (and HOSE fallback), try direct VNDirect/TCBS public OHLCV first if HNX/UPCOM
        if eff_mic in {"XHAI", "XUPC"} and interval == "1d":
            vn_pub = self._fetch_vietnam_public_ohlcv(ticker, eff_mic, years=10)
            if vn_pub is not None:
                return vn_pub

        if allow_educational_fallback:
            yf_resp = self.yfinance_fallback.get_ohlcv(
                ticker=ticker,
                exchange_mic=eff_mic,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                period=period,
            )
            if yf_resp.bars and len(yf_resp.bars) >= 20:
                return yf_resp
            # If yfinance returned empty/sparse (e.g. VN HOSE/HNX/UPCOM or international), try public VN & Twelve Data fallbacks
            if eff_mic in {"XSTC", "XHAI", "XUPC"} and interval == "1d":
                vn_pub = self._fetch_vietnam_public_ohlcv(ticker, eff_mic, years=10)
                if vn_pub is not None:
                    return vn_pub
            if interval == "1d":
                td_resp = self._fetch_twelvedata_ohlcv(ticker, eff_mic)
                if td_resp is not None:
                    return td_resp
            return yf_resp

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

        # Global (non-US, non-VN) quotes are routed to yfinance in get_quote(); a paid provider
        # only counts as LIVE once its quote adapter is actually implemented. Having an API key
        # is not enough (Twelve Data is currently used solely as a historical-bars backup).
        global_live_provider = next(
            (
                p
                for p in (self.twelvedata, self.eodhd)
                if p.is_configured() and getattr(p, "live_quotes_implemented", False)
            ),
            None,
        )
        global_live_ready = global_live_provider is not None
        if global_live_provider is not None:
            global_primary = f"{global_live_provider.capabilities.display_name.split(' (')[0]} (Live Global)"
        else:
            global_primary = "yfinance (Delayed)"
        global_note_suffix = (
            " A Twelve Data key is configured and used as a backup source for historical daily bars;"
            " it does not provide live quotes here."
            if self.twelvedata.is_configured() and not global_live_ready
            else ""
        )
        global_cov_status = (
            CoverageStatus.LIVE_VERIFIED
            if global_live_ready
            else (CoverageStatus.DELAYED_AVAILABLE if yf_ready else CoverageStatus.NOT_SUPPORTED)
        )
        global_quote_status = (
            DataStatus.LIVE
            if global_live_ready
            else (DataStatus.DELAYED if yf_ready else DataStatus.DATA_UNAVAILABLE)
        )
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
                primary_provider="SSI FastConnect Data (Live) / Vnstock v6",
                fallback_provider="yfinance (.VN Educational Historical)",
                requires_credentials=True, requires_paid_plan_for_live=False,
                notes="LIVE requires SSI FastConnect Data credentials ($0 API fee); historical & delayed quotes active via yfinance/Vnstock.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XHAI", exchange_acronym="HNX", exchange_name="Hanoi Stock Exchange",
                region="Southeast Asia", country="Vietnam", currency="VND", timezone="Asia/Ho_Chi_Minh",
                phase="Phase 1",
                coverage_status=CoverageStatus.LIVE_VERIFIED if ssi_ready else (CoverageStatus.DELAYED_AVAILABLE if (vnstock_ready or yf_ready) else CoverageStatus.CREDENTIALS_REQUIRED),
                quote_data_status=DataStatus.LIVE if ssi_ready else DataStatus.DELAYED,
                historical_data_status=global_hist_status,
                primary_provider="SSI FastConnect Data (Live) / Vnstock v6",
                fallback_provider="yfinance (.VN Educational Historical)",
                requires_credentials=True, requires_paid_plan_for_live=False,
                notes="Active through 2026-12-23; effective-dated transfer to HOSE (XSTC) on 2026-12-28.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XUPC", exchange_acronym="UPCOM", exchange_name="Vietnam Unlisted Public Company Market (UPCoM)",
                region="Southeast Asia", country="Vietnam", currency="VND", timezone="Asia/Ho_Chi_Minh",
                phase="Phase 1",
                coverage_status=CoverageStatus.LIVE_VERIFIED if ssi_ready else (CoverageStatus.DELAYED_AVAILABLE if (vnstock_ready or yf_ready) else CoverageStatus.CREDENTIALS_REQUIRED),
                quote_data_status=DataStatus.LIVE if ssi_ready else DataStatus.DELAYED,
                historical_data_status=global_hist_status,
                primary_provider="SSI FastConnect Data (Live) / Vnstock v6",
                fallback_provider="yfinance (.VN Educational Historical)",
                requires_credentials=True, requires_paid_plan_for_live=False,
                notes="LIVE requires SSI FastConnect Data credentials ($0 API fee); historical & delayed quotes active via yfinance/Vnstock.",
            ),
            ExchangeCoverageEntry(
                exchange_mic="XLON", exchange_acronym="LSE", exchange_name="London Stock Exchange",
                region="Europe", country="United Kingdom", currency="GBP", timezone="Europe/London",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider=global_primary,
                fallback_provider="yfinance (.L)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.L); real-time requires paid EODHD/Twelve Data." + global_note_suffix,
            ),
            ExchangeCoverageEntry(
                exchange_mic="XETR", exchange_acronym="Xetra", exchange_name="Deutsche Börse Xetra",
                region="Europe", country="Germany", currency="EUR", timezone="Europe/Berlin",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider=global_primary,
                fallback_provider="yfinance (.DE)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.DE); real-time requires paid EODHD/Twelve Data." + global_note_suffix,
            ),
            ExchangeCoverageEntry(
                exchange_mic="XTKS", exchange_acronym="TSE", exchange_name="Tokyo Stock Exchange",
                region="Asia", country="Japan", currency="JPY", timezone="Asia/Tokyo",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider=global_primary,
                fallback_provider="yfinance (.T)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.T); real-time requires paid EODHD/Twelve Data." + global_note_suffix,
            ),
            ExchangeCoverageEntry(
                exchange_mic="XHKG", exchange_acronym="HKEX", exchange_name="Hong Kong Exchanges and Clearing",
                region="Asia", country="Hong Kong", currency="HKD", timezone="Asia/Hong_Kong",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider=global_primary,
                fallback_provider="yfinance (.HK)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.HK); real-time requires paid EODHD/Twelve Data." + global_note_suffix,
            ),
            ExchangeCoverageEntry(
                exchange_mic="XSES", exchange_acronym="SGX", exchange_name="Singapore Exchange",
                region="Southeast Asia", country="Singapore", currency="SGD", timezone="Asia/Singapore",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider=global_primary,
                fallback_provider="yfinance (.SI)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.SI); real-time requires paid EODHD/Twelve Data." + global_note_suffix,
            ),
            ExchangeCoverageEntry(
                exchange_mic="XASX", exchange_acronym="ASX", exchange_name="Australian Securities Exchange",
                region="Oceania", country="Australia", currency="AUD", timezone="Australia/Sydney",
                phase="Phase 7", coverage_status=global_cov_status, quote_data_status=global_quote_status,
                historical_data_status=global_hist_status,
                primary_provider=global_primary,
                fallback_provider="yfinance (.AX)", requires_credentials=False, requires_paid_plan_for_live=True,
                notes="Historical & delayed quotes available via yfinance (.AX); real-time requires paid EODHD/Twelve Data." + global_note_suffix,
            ),
        ]
