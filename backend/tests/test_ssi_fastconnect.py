"""SSI FastConnect Data (API v2) adapter, exercised with fakes shaped like SSI's documented samples."""

from __future__ import annotations

import base64
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.models import DataStatus, MarketSession
from app.data.providers import ssi_fastconnect as ssi_mod
from app.data.providers.ssi_fastconnect import VN_TZ, SSIFastConnectProvider
from app.data.registry import MarketDataRegistry


def _jwt(exp: float) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{enc({'alg': 'HS256'})}.{enc({'exp': int(exp)})}.sig"


class _Resp:
    def __init__(self, body, status_code: int = 200):
        self._body, self.status_code = body, status_code

    def json(self):
        return self._body


class FakeSSI:
    """Records calls; serves AccessToken + IntradayOhlc / DailyOhlc like SSI's samples."""

    def __init__(self, now: float = 1_800_000_000.0):
        self.now = now
        self.posts, self.gets = [], []
        self.intraday_rows: list = []
        self.daily_rows: list = []
        self.data_status = "Success"
        self.reject_next_get_with_401 = False

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append((url, json))
        return _Resp({"message": "Success", "status": 200, "data": {"accessToken": _jwt(self.now + 8 * 3600)}})

    def get(self, url, params=None, headers=None, timeout=None):
        self.gets.append((url, dict(params or {}), dict(headers or {})))
        if self.reject_next_get_with_401:
            self.reject_next_get_with_401 = False
            return _Resp({"message": "Unauthorized"}, 401)
        if url.endswith("IntradayOhlc"):
            rows = self.intraday_rows
        else:
            lo = datetime.strptime(params["fromDate"], "%d/%m/%Y").date()
            hi = datetime.strptime(params["toDate"], "%d/%m/%Y").date()
            rows = [r for r in self.daily_rows if lo <= datetime.strptime(r["TradingDate"], "%d/%m/%Y").date() <= hi]
        return _Resp({"message": "Success", "status": self.data_status, "totalRecord": len(rows), "data": rows})


def _provider(fake: FakeSSI) -> SSIFastConnectProvider:
    return SSIFastConnectProvider("consumer-id", "consumer-secret", http_post=fake.post, http_get=fake.get, clock=lambda: fake.now)


@pytest.fixture
def regular_session(monkeypatch):
    monkeypatch.setattr(ssi_mod, "get_market_session", lambda *a, **k: SimpleNamespace(session=MarketSession.REGULAR))


def _tick(ts_utc: datetime, close, symbol="FPT"):
    local = ts_utc.astimezone(VN_TZ)
    return {
        "Symbol": symbol, "Value": "1", "TradingDate": local.strftime("%d/%m/%Y"), "Time": local.strftime("%H:%M:%S"),
        "Open": close, "High": close, "Low": close, "Close": close, "Volume": "100",
    }


# ----------------------------------------------------------------------------- auth

def test_auth_uses_documented_v2_endpoint_and_fields_and_caches_token(regular_session) -> None:
    fake = FakeSSI()
    fake.intraday_rows = [_tick(datetime.now(timezone.utc) - timedelta(seconds=30), "95100")]
    p = _provider(fake)
    p.get_quote("FPT", "XSTC")
    p.get_quote("FPT", "XSTC")
    assert len(fake.posts) == 1, "token must be cached between calls"
    url, body = fake.posts[0]
    assert url == "https://fc-data.ssi.com.vn/api/v2/Market/AccessToken"
    assert body == {"consumerID": "consumer-id", "consumerSecret": "consumer-secret"}
    get_url, params, headers = fake.gets[0]
    assert get_url == "https://fc-data.ssi.com.vn/api/v2/Market/IntradayOhlc"
    assert headers["Authorization"].startswith("Bearer ")
    today = datetime.now(timezone.utc).astimezone(VN_TZ).strftime("%d/%m/%Y")
    assert params["symbol"] == "FPT" and params["fromDate"] == today and params["toDate"] == today


def test_token_refreshed_before_expiry_and_on_401(regular_session) -> None:
    fake = FakeSSI()
    fake.intraday_rows = [_tick(datetime.now(timezone.utc) - timedelta(seconds=30), 95100)]
    p = _provider(fake)
    p.get_quote("FPT", "XSTC")
    fake.now += 7.5 * 3600  # within 1 h of the 8 h JWT expiry -> refresh
    p.get_quote("FPT", "XSTC")
    assert len(fake.posts) == 2
    fake.reject_next_get_with_401 = True
    q = p.get_quote("FPT", "XSTC")
    assert len(fake.posts) == 3 and q.data_status == DataStatus.LIVE


# ---------------------------------------------------------------------------- quotes

def test_recent_trade_is_live_and_picks_latest_tick(regular_session) -> None:
    now = datetime.now(timezone.utc)
    fake = FakeSSI()
    fake.intraday_rows = [_tick(now - timedelta(minutes=5), "94,900"), _tick(now - timedelta(seconds=20), "95100")]
    q = _provider(fake).get_quote("FPT", "XSTC")
    assert q.data_status == DataStatus.LIVE
    assert q.price == 95100.0 and q.provider == "ssi_fastconnect_data" and q.currency == "VND"
    assert abs((q.market_timestamp - (now - timedelta(seconds=20))).total_seconds()) < 1.5


def test_stale_trade_is_delayed_with_real_age(regular_session) -> None:
    fake = FakeSSI()
    fake.intraday_rows = [_tick(datetime.now(timezone.utc) - timedelta(minutes=20), 95100)]
    q = _provider(fake).get_quote("FPT", "XSTC")
    assert q.data_status == DataStatus.DELAYED and q.delay_minutes in (19, 20)


def test_closed_session_is_not_live(monkeypatch) -> None:
    monkeypatch.setattr(ssi_mod, "get_market_session", lambda *a, **k: SimpleNamespace(session=MarketSession.CLOSED))
    fake = FakeSSI()
    fake.intraday_rows = [_tick(datetime.now(timezone.utc) - timedelta(seconds=10), 95100)]
    assert _provider(fake).get_quote("FPT", "XSTC").data_status == DataStatus.HISTORICAL


def test_errors_and_empty_data_are_unavailable_not_crashes(regular_session) -> None:
    fake = FakeSSI()
    q = _provider(fake).get_quote("FPT", "XSTC")  # no trades today
    assert q.data_status == DataStatus.DATA_UNAVAILABLE and "no matched trades" in q.unavailable_reason
    fake.data_status = "Fail"
    q = _provider(fake).get_quote("FPT", "XSTC")
    assert q.data_status == DataStatus.DATA_UNAVAILABLE and "SSI FastConnect Data error" in q.unavailable_reason

    def boom(*a, **k):
        raise ConnectionError("network down")

    p = SSIFastConnectProvider("id", "secret", http_post=fake.post, http_get=boom)
    assert p.get_quote("FPT", "XSTC").data_status == DataStatus.DATA_UNAVAILABLE


def test_unconfigured_provider() -> None:
    p = SSIFastConnectProvider(None, None)
    assert not p.is_configured()
    q = p.get_quote("FPT", "XSTC")
    assert q.data_status == DataStatus.DATA_UNAVAILABLE and "SSI_CONSUMER_ID" in q.unavailable_reason


# --------------------------------------------------------------------------- history

def _daily(d: date, close: float) -> dict:
    return {"Symbol": "FPT", "TradingDate": d.strftime("%d/%m/%Y"), "Time": None,
            "Open": str(close - 100), "High": str(close + 200), "Low": str(close - 300), "Close": str(close), "Volume": "1000", "Value": "1"}


def test_daily_history_chunks_by_year_parses_and_validates() -> None:
    fake = FakeSSI()
    start, end = date(2023, 1, 2), date(2025, 6, 30)
    d, rows = start, []
    while d <= end:
        if d.weekday() < 5:
            rows.append(_daily(d, 90000 + len(rows)))
        d += timedelta(days=1)
    rows.append({"Symbol": "FPT", "TradingDate": "03/01/2023", "Open": "0", "High": "0", "Low": "0", "Close": "0"})  # bad row
    fake.daily_rows = rows
    resp = _provider(fake).get_ohlcv("FPT", "XSTC", "1d", start, end)
    assert resp.data_status == DataStatus.HISTORICAL and resp.provider == "ssi_fastconnect_data"
    assert len(resp.bars) == len(rows) - 1  # invalid zero-price row dropped (good row for that day kept)
    assert resp.bars == sorted(resp.bars, key=lambda b: b.timestamp)
    daily_calls = [g for g in fake.gets if g[0].endswith("DailyOhlc")]
    assert len(daily_calls) == 3  # 2023, 2024, 2025 windows
    assert all(g[1]["pageSize"] == 1000 for g in daily_calls)
    b = resp.bars[0]
    assert b.low <= min(b.open, b.close) and b.high >= max(b.open, b.close)


def test_non_daily_interval_unavailable() -> None:
    assert _provider(FakeSSI()).get_ohlcv("FPT", "XSTC", "1h").data_status == DataStatus.DATA_UNAVAILABLE


# ------------------------------------------------------------------- wiring / config

def test_registry_prefers_ssi_for_vietnam_history_when_configured() -> None:
    fake = FakeSSI()
    today = datetime.now(timezone.utc).astimezone(VN_TZ).date()
    fake.daily_rows = [_daily(today - timedelta(days=i), 95000 + i) for i in range(1, 60)]
    settings = Settings(database_path=":memory:", enable_yfinance_fallback=False)
    reg = MarketDataRegistry(settings=settings, ssi=_provider(fake))
    resp = reg.get_ohlcv("XSTC:FPT", interval="1d", period="6mo")
    assert resp.provider == "ssi_fastconnect_data" and len(resp.bars) == 59
    assert reg.configured_provider_map()["ssi_fastconnect_data"] is True


def test_consumer_env_names_preferred_over_legacy(monkeypatch) -> None:
    monkeypatch.setenv("SSI_API_KEY", "legacy-id")
    monkeypatch.setenv("SSI_API_SECRET", "legacy-secret")
    s = Settings(database_path=":memory:")
    assert (s.ssi_api_key, s.ssi_api_secret) == ("legacy-id", "legacy-secret")
    monkeypatch.setenv("SSI_CONSUMER_ID", "new-id")
    monkeypatch.setenv("SSI_CONSUMER_SECRET", "new-secret")
    s = Settings(database_path=":memory:")
    assert (s.ssi_api_key, s.ssi_api_secret) == ("new-id", "new-secret")
