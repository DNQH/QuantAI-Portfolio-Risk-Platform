"""Comprehensive Phase 1 automated test suite (compatible with unittest and pytest)."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Ensure backend/ is on sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.core.calendar import get_market_session
from app.core.config import Settings
from app.core.models import DataStatus, MarketSession, OHLCVBar
from app.core.symbology import (
    parse_instrument_id,
    resolve_effective_exchange,
    search_seed_instruments,
)
from app.data.freshness import classify_quote_freshness, validate_ohlcv_bars
from app.data.providers.finnhub import FinnhubProvider
from app.data.registry import MarketDataRegistry
from app.fx.frankfurter import TARGET_CURRENCIES, FrankfurterFXProvider
from app.main import create_app


class _FakeHTTPResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class TestSymbologyAndMigration(unittest.TestCase):
    def test_unqualified_ticker_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_instrument_id("AAPL")

    def test_ticker_collision_disambiguation_vnm(self) -> None:
        matches = search_seed_instruments(query="VNM", as_of=date(2026, 11, 20))
        ids = {m.instrument_id for m in matches}
        self.assertIn("XSTC:VNM", ids)
        self.assertIn("XNYS:VNM", ids)
        currencies = {m.instrument_id: m.currency for m in matches}
        self.assertEqual(currencies["XSTC:VNM"], "VND")
        self.assertEqual(currencies["XNYS:VNM"], "USD")

    def test_hnx_to_hose_effective_dated_migration(self) -> None:
        # Before migration (2026-11-20 & 2026-12-23): remains active on HNX (XHAI)
        mic, acr, susp, _ = resolve_effective_exchange("SHS", "XHAI", as_of=date(2026, 11, 20))
        self.assertEqual((mic, acr, susp), ("XHAI", "HNX", False))

        mic, acr, susp, _ = resolve_effective_exchange("SHS", "XHAI", as_of=date(2026, 12, 23))
        self.assertEqual((mic, acr, susp), ("XHAI", "HNX", False))

        # Migration suspension window (2026-12-24 and 2026-12-25)
        for d in (date(2026, 12, 24), date(2026, 12, 25)):
            mic, acr, susp, _ = resolve_effective_exchange("SHS", "XHAI", as_of=d)
            self.assertEqual(mic, "XHAI")
            self.assertTrue(susp)

        # Effective date (2026-12-28): transferred to HOSE (XSTC)
        mic, acr, susp, note = resolve_effective_exchange("SHS", "XHAI", as_of=date(2026, 12, 28))
        self.assertEqual((mic, acr, susp), ("XSTC", "HOSE", False))
        self.assertIn("2026-12-28", note or "")


class TestExchangeCalendar(unittest.TestCase):
    def test_us_regular_and_holiday_sessions(self) -> None:
        # 2026-11-20 15:00 UTC = 10:00 EST -> NYSE regular session
        info = get_market_session("XNYS", now_utc=datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(info.session, MarketSession.REGULAR)
        self.assertTrue(info.is_open)

        # 2026-11-26 15:00 UTC = Thanksgiving Holiday
        hol = get_market_session("XNYS", now_utc=datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(hol.session, MarketSession.HOLIDAY)
        self.assertFalse(hol.is_open)

    def test_vietnam_lunch_break_and_weekend(self) -> None:
        # 2026-11-20 05:00 UTC = 12:00 ICT -> HOSE lunch break (11:30-13:00)
        lunch = get_market_session("XSTC", now_utc=datetime(2026, 11, 20, 5, 0, tzinfo=timezone.utc))
        self.assertEqual(lunch.session, MarketSession.LUNCH_BREAK)
        self.assertFalse(lunch.is_open)

        # 2026-11-21 03:00 UTC = Saturday -> CLOSED
        wknd = get_market_session("XSTC", now_utc=datetime(2026, 11, 21, 3, 0, tzinfo=timezone.utc))
        self.assertEqual(wknd.session, MarketSession.CLOSED)
        self.assertFalse(wknd.is_open)


class TestFreshnessAndIntegrity(unittest.TestCase):
    def test_strict_live_vs_delayed_vs_historical(self) -> None:
        now = datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc)
        # Fresh entitled open quote -> LIVE
        st, delay, _ = classify_quote_freshness(
            price=225.0,
            market_timestamp=datetime(2026, 11, 20, 14, 59, 30, tzinfo=timezone.utc),
            retrieval_timestamp=now,
            market_session=MarketSession.REGULAR,
            provider_entitled_live=True,
        )
        self.assertEqual((st, delay), (DataStatus.LIVE, 0))

        # Stale open quote (20 minutes old) -> DELAYED, never LIVE
        st, delay, _ = classify_quote_freshness(
            price=225.0,
            market_timestamp=datetime(2026, 11, 20, 14, 40, 0, tzinfo=timezone.utc),
            retrieval_timestamp=now,
            market_session=MarketSession.REGULAR,
            provider_entitled_live=True,
        )
        self.assertEqual(st, DataStatus.DELAYED)
        self.assertGreaterEqual(delay or 0, 20)

        # Closed exchange -> HISTORICAL, never LIVE
        st, _, _ = classify_quote_freshness(
            price=225.0,
            market_timestamp=now,
            retrieval_timestamp=now,
            market_session=MarketSession.CLOSED,
            provider_entitled_live=True,
        )
        self.assertEqual(st, DataStatus.HISTORICAL)

        # Unentitled provider (e.g. yfinance) -> DELAYED, never LIVE
        st, _, _ = classify_quote_freshness(
            price=225.0,
            market_timestamp=now,
            retrieval_timestamp=now,
            market_session=MarketSession.REGULAR,
            provider_entitled_live=False,
        )
        self.assertEqual(st, DataStatus.DELAYED)

        # Invalid/zero price -> DATA_UNAVAILABLE
        st, _, _ = classify_quote_freshness(
            price=0.0,
            market_timestamp=now,
            retrieval_timestamp=now,
            market_session=MarketSession.REGULAR,
            provider_entitled_live=True,
        )
        self.assertEqual(st, DataStatus.DATA_UNAVAILABLE)

    def test_ohlcv_deduplication_and_corrupted_bar_filtering(self) -> None:
        t1 = datetime(2026, 11, 18, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 19, tzinfo=timezone.utc)
        bars = [
            OHLCVBar(timestamp=t2, open=100, high=105, low=99, close=104, volume=1000),
            OHLCVBar(timestamp=t1, open=95, high=101, low=94, close=100, volume=900),
            OHLCVBar(timestamp=t1, open=95, high=101, low=94, close=100, volume=950),  # duplicate
            OHLCVBar(timestamp=t2, open=-5, high=10, low=-6, close=8, volume=100),   # corrupted negative price
        ]
        cleaned, warnings = validate_ohlcv_bars(bars)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(cleaned[0].timestamp, t1)
        self.assertEqual(cleaned[1].timestamp, t2)
        self.assertEqual(len(warnings), 2)


class TestProvidersAndFastAPI(unittest.TestCase):
    def _build_test_client(self) -> TestClient:
        settings = Settings(
            database_path=":memory:",
            finnhub_api_key="test-finnhub-key",
            ssi_api_key=None,
            ssi_api_secret=None,
            enable_yfinance_fallback=False,
        )

        def fake_finnhub_get(url: str, params: Dict[str, Any], timeout: float) -> _FakeHTTPResponse:
            if url.endswith("/quote"):
                return _FakeHTTPResponse(
                    200,
                    {
                        "c": 228.45,
                        "d": 2.15,
                        "dp": 0.95,
                        "h": 229.10,
                        "l": 226.00,
                        "o": 226.50,
                        "pc": 226.30,
                        "t": int(datetime.now(timezone.utc).timestamp()),
                    },
                )
            return _FakeHTTPResponse(200, {"result": []})

        def fake_fx_get(url: str, params: Dict[str, Any], timeout: float) -> _FakeHTTPResponse:
            return _FakeHTTPResponse(
                200,
                [
                    {"date": "2026-11-19", "base": "USD", "quote": "EUR", "rate": 0.92},
                    {"date": "2026-11-19", "base": "USD", "quote": "VND", "rate": 25400.0},
                ],
            )

        finnhub = FinnhubProvider(api_key="test-finnhub-key", http_get=fake_finnhub_get)
        frankfurter = FrankfurterFXProvider(http_get=fake_fx_get)
        registry = MarketDataRegistry(
            settings=settings,
            finnhub=finnhub,
            frankfurter=frankfurter,
        )
        app = create_app(settings=settings, registry=registry)
        return TestClient(app)

    def test_health_and_coverage_endpoints(self) -> None:
        client = self._build_test_client()
        r = client.get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["database_ready"])
        self.assertTrue(body["configured_providers"]["finnhub"])
        self.assertFalse(body["configured_providers"]["ssi_fastconnect_data"])

        cov = client.get("/api/v1/exchanges/coverage").json()
        mics = {row["exchange_mic"]: row for row in cov}
        self.assertEqual(mics["XNAS"]["phase"], "Phase 1")
        self.assertEqual(mics["XHAI"]["phase"], "Phase 1")
        self.assertEqual(mics["XLON"]["coverage_status"], "NOT_SUPPORTED")

    def test_no_silent_fallback_for_vietnam_live_without_ssi_keys(self) -> None:
        client = self._build_test_client()
        r = client.get("/api/v1/market/quote/XSTC:FPT?require_live=true")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["data_status"], "DATA_UNAVAILABLE")
        self.assertIsNone(body["price"])
        self.assertIn("SSI FastConnect Data", body["unavailable_reason"])

    def test_finnhub_quote_has_dual_timestamps_and_paid_ohlcv_honesty(self) -> None:
        client = self._build_test_client()
        q = client.get("/api/v1/market/quote/XNAS:AAPL").json()
        self.assertEqual(q["provider"], "finnhub")
        self.assertIsNotNone(q["market_timestamp"])
        self.assertIsNotNone(q["retrieval_timestamp"])
        self.assertEqual(q["price"], 228.45)

        # Phase 7 exchange must return DATA_UNAVAILABLE
        uk = client.get("/api/v1/market/quote/XLON:HSBA").json()
        self.assertEqual(uk["data_status"], "DATA_UNAVAILABLE")

        # Finnhub historical OHLCV with educational fallback disabled -> DATA_UNAVAILABLE
        ohlcv = client.get("/api/v1/market/ohlcv/XNAS:AAPL?allow_educational_fallback=false").json()
        self.assertEqual(ohlcv["data_status"], "DATA_UNAVAILABLE")

    def test_fx_reference_rates_and_conversion(self) -> None:
        client = self._build_test_client()
        ccys = client.get("/api/v1/fx/currencies").json()
        self.assertEqual(len(ccys), 15)
        self.assertEqual(tuple(ccys), TARGET_CURRENCIES)

        rates = client.get("/api/v1/fx/rates?base=USD").json()
        self.assertEqual(rates["data_status"], "DAILY_REFERENCE")
        self.assertEqual(rates["rates"]["VND"], 25400.0)

        conv = client.get("/api/v1/fx/convert?base=USD&quote=VND&amount=100").json()
        self.assertEqual(conv["data_status"], "DAILY_REFERENCE")
        self.assertEqual(conv["converted_amount"], 2540000.0)

    def test_websocket_enforces_strict_live_status(self) -> None:
        client = self._build_test_client()
        with client.websocket_connect("/api/v1/ws/quotes/XSTC:FPT") as ws:
            msg = ws.receive_json()
            self.assertEqual(msg["data_status"], "DATA_UNAVAILABLE")
            self.assertIsNone(msg["price"])


if __name__ == "__main__":
    unittest.main()
