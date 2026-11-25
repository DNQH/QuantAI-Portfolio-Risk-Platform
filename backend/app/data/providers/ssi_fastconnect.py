"""SSI FastConnect Data (FC Data API v2) adapter for Vietnam market data (HOSE / HNX / UPCOM).

Verified against SSI's official documentation (guide.ssi.com.vn/ssi-products/fastconnect-data)
and the official ``ssi-fc-data`` Python SDK (v2.2.x):

* Base URL ``https://fc-data.ssi.com.vn/``.
* Auth: ``POST api/v2/Market/AccessToken`` with JSON ``{"consumerID", "consumerSecret"}``;
  the response carries ``data.accessToken`` (a JWT, sent as ``Authorization: Bearer``).
* Market data (GET, ``Bearer`` token):
  ``api/v2/Market/DailyOhlc`` and ``api/v2/Market/IntradayOhlc`` with ``symbol``,
  ``fromDate``/``toDate`` (``dd/mm/yyyy``), ``pageIndex`` (1-10), ``pageSize`` (<= 1000),
  ``ascending``; IntradayOhlc also takes ``resolution`` (minutes). Rows contain
  ``Symbol, TradingDate (dd/mm/yyyy), Time (HH:MM:SS), Open, High, Low, Close, Volume, Value``.
* There is no REST "quote" endpoint; bid/ask and every matched trade are streamed over
  SignalR (``X-QUOTE`` / ``X-TRADE``). This adapter uses the most recent IntradayOhlc tick
  as the last traded price, and the shared freshness classifier decides LIVE vs DELAYED from
  that trade's real exchange timestamp (so an illiquid stock is honestly reported as delayed).
* Access requires an SSI trading account and an FC Data registration (ConsumerID +
  ConsumerSecret, valid one year). Configure them as ``SSI_CONSUMER_ID`` /
  ``SSI_CONSUMER_SECRET`` (legacy names ``SSI_API_KEY`` / ``SSI_API_SECRET`` also work).

Price units are passed through exactly as SSI returns them.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx

from app.core.calendar import get_market_session
from app.core.models import DataStatus, OHLCVBar, OHLCVResponse, QuoteResponse
from app.core.symbology import resolve_effective_exchange
from app.data.base import BaseMarketDataProvider, ProviderCapabilities
from app.data.freshness import classify_quote_freshness

SSI_BASE_URL = "https://fc-data.ssi.com.vn/"
ACCESS_TOKEN_PATH = "api/v2/Market/AccessToken"
DAILY_OHLC_PATH = "api/v2/Market/DailyOhlc"
INTRADAY_OHLC_PATH = "api/v2/Market/IntradayOhlc"

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
VN_MICS = ("XSTC", "XHAI", "XUPC")
MAX_PAGE_SIZE = 1000
MAX_PAGE_INDEX = 10
# Matched trades arrive tick by tick; allow a little latency before calling a print stale.
LIVE_MAX_AGE_SECONDS = 180
# Earliest HOSE trading session (28 July 2000); used when the full history is requested.
HOSE_FIRST_SESSION = date(2000, 7, 28)


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        out = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return out if out == out else None  # drop NaN


def _ok(payload: Dict[str, Any]) -> bool:
    status = payload.get("status")
    return status in (200, "200") or str(status).strip().lower() == "success"


def _parse_vn_datetime(trading_date: Any, time_str: Any) -> Optional[datetime]:
    """``"14/08/2023"`` + ``"14:45:04"`` (Vietnam local time) -> aware UTC datetime."""
    if not trading_date:
        return None
    try:
        d = datetime.strptime(str(trading_date).strip()[:10], "%d/%m/%Y")
    except ValueError:
        return None
    if time_str:
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(str(time_str).strip(), fmt).time()
                d = datetime.combine(d.date(), t)
                break
            except ValueError:
                continue
    return d.replace(tzinfo=VN_TZ).astimezone(timezone.utc)


def _jwt_expiry(token: str) -> Optional[float]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        return float(exp) if exp else None
    except Exception:
        return None


class SSIFastConnectProvider(BaseMarketDataProvider):
    capabilities = ProviderCapabilities(
        provider_id="ssi_fastconnect_data",
        display_name="SSI FastConnect Data (Vietnam Real-Time)",
        supported_mics=VN_MICS,
        supports_live_quotes=True,
        supports_websocket=False,  # SignalR streaming not used; REST intraday ticks instead
        supports_historical_ohlcv=True,
        is_educational_fallback_only=False,
        requires_api_key=True,
        requires_paid_plan_for_live=False,  # requires an SSI trading account + FC Data registration
        official_docs_url="https://guide.ssi.com.vn/ssi-products/fastconnect-data",
    )

    def __init__(
        self,
        api_key: Optional[str],
        api_secret: Optional[str],
        timeout: float = 10.0,
        http_post: Optional[Callable[..., Any]] = None,
        http_get: Optional[Callable[..., Any]] = None,
        clock: Callable[[], float] = time.time,
        base_url: str = SSI_BASE_URL,
    ) -> None:
        # api_key / api_secret are the FC Data ConsumerID / ConsumerSecret.
        self._consumer_id = api_key
        self._consumer_secret = api_secret
        self._timeout = timeout
        self._http_post = http_post or httpx.post
        self._http_get = http_get or httpx.get
        self._clock = clock
        self._base_url = base_url if base_url.endswith("/") else base_url + "/"
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._lock = threading.Lock()

    def is_configured(self) -> bool:
        return bool(self._consumer_id and self._consumer_secret)

    # ------------------------------------------------------------------ auth / transport

    def authenticate(self, force: bool = False) -> Optional[str]:
        """Return a cached bearer token, refreshing it one hour before the JWT expires."""
        if not self.is_configured():
            return None
        with self._lock:
            if not force and self._access_token and self._clock() < self._token_expires_at:
                return self._access_token
            resp = self._http_post(
                self._base_url + ACCESS_TOKEN_PATH,
                json={"consumerID": self._consumer_id, "consumerSecret": self._consumer_secret},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=self._timeout,
            )
            if getattr(resp, "status_code", 200) != 200:
                return None
            body = resp.json() or {}
            data = body.get("data") or {}
            token = (data.get("accessToken") if isinstance(data, dict) else None) or body.get("accessToken")
            if not _ok(body) or not token:
                return None
            exp = _jwt_expiry(token)
            now = self._clock()
            # Same safety margin as the official SDK (refresh 1 h early); fallback TTL 1 h.
            self._token_expires_at = (exp - 3600) if exp and exp - 3600 > now else now + 3600
            self._access_token = token
            return token

    def _get(self, path: str, params: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        token = self.authenticate()
        if not token:
            return None, "SSI FastConnect Data authentication failed (check ConsumerID / ConsumerSecret)."
        for attempt in range(2):
            resp = self._http_get(
                self._base_url + path,
                params=params,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=self._timeout,
            )
            code = getattr(resp, "status_code", 200)
            if code == 401 and attempt == 0:
                token = self.authenticate(force=True)
                if not token:
                    break
                continue
            if code != 200:
                return None, f"SSI FastConnect Data HTTP {code} error."
            body = resp.json() or {}
            if not _ok(body):
                return None, f"SSI FastConnect Data error: {body.get('message') or body.get('status')}"
            return body, None
        return None, "SSI FastConnect Data authentication failed (token rejected)."

    # ----------------------------------------------------------------------------- quote

    def _unavailable_quote(self, ticker: str, eff_mic: str, session, now_utc: datetime, reason: str) -> QuoteResponse:
        return QuoteResponse(
            instrument_id=f"{eff_mic}:{ticker}",
            ticker=ticker,
            exchange_mic=eff_mic,
            currency="VND",
            provider=self.capabilities.provider_id,
            data_status=DataStatus.DATA_UNAVAILABLE,
            market_session=session,
            retrieval_timestamp=now_utc,
            unavailable_reason=reason,
        )

    def get_quote(self, ticker: str, exchange_mic: str) -> QuoteResponse:
        now_utc = datetime.now(timezone.utc)
        eff_mic, _, is_suspended, migration_note = resolve_effective_exchange(
            ticker, exchange_mic, as_of=now_utc.date()
        )
        session = get_market_session(eff_mic, now_utc=now_utc, is_migration_suspended=is_suspended).session

        if not self.is_configured():
            return self._unavailable_quote(
                ticker, eff_mic, session, now_utc,
                "SSI_CONSUMER_ID and SSI_CONSUMER_SECRET are not configured "
                "(SSI trading account + FastConnect Data registration required).",
            )

        today_vn = now_utc.astimezone(VN_TZ).date()
        try:
            body, err = self._get(
                INTRADAY_OHLC_PATH,
                {
                    "symbol": ticker,
                    "fromDate": _fmt(today_vn),
                    "toDate": _fmt(today_vn),
                    "pageIndex": 1,
                    "pageSize": 10,
                    "ascending": "false",
                    "resolution": 1,
                },
            )
        except Exception as exc:  # network / JSON errors never crash the API
            return self._unavailable_quote(ticker, eff_mic, session, now_utc, f"SSI FastConnect Data connection error: {exc}")
        if err:
            return self._unavailable_quote(ticker, eff_mic, session, now_utc, err)

        rows = [r for r in (body.get("data") or []) if isinstance(r, dict)]
        latest = None
        for row in rows:
            ts = _parse_vn_datetime(row.get("TradingDate"), row.get("Time"))
            if ts is not None and _num(row.get("Close")) is not None and (latest is None or ts > latest[0]):
                latest = (ts, row)
        if latest is None:
            return self._unavailable_quote(
                ticker, eff_mic, session, now_utc,
                "SSI FastConnect Data returned no matched trades for this symbol today.",
            )

        market_ts, row = latest
        price = _num(row.get("Close"))
        status, delay_min, warnings = classify_quote_freshness(
            price=price,
            market_timestamp=market_ts,
            retrieval_timestamp=now_utc,
            market_session=session,
            provider_entitled_live=True,
            max_live_age_seconds=LIVE_MAX_AGE_SECONDS,
        )
        if migration_note:
            warnings.append(migration_note)
        return QuoteResponse(
            instrument_id=f"{eff_mic}:{ticker}",
            ticker=ticker,
            exchange_mic=eff_mic,
            currency="VND",
            provider=self.capabilities.provider_id,
            data_status=status,
            delay_minutes=delay_min,
            market_session=session,
            market_timestamp=market_ts,
            retrieval_timestamp=now_utc,
            price=price if status != DataStatus.DATA_UNAVAILABLE else None,
            warnings=warnings,
        )

    # ---------------------------------------------------------------------- daily history

    def get_ohlcv(
        self,
        ticker: str,
        exchange_mic: str,
        interval: str = "1d",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> OHLCVResponse:
        now_utc = datetime.now(timezone.utc)
        end = end_date or now_utc.astimezone(VN_TZ).date()
        start = start_date or HOSE_FIRST_SESSION
        eff_mic, _, _, _ = resolve_effective_exchange(ticker, exchange_mic, as_of=end)

        def unavailable(reason: str) -> OHLCVResponse:
            return OHLCVResponse(
                instrument_id=f"{eff_mic}:{ticker}",
                ticker=ticker,
                exchange_mic=eff_mic,
                currency="VND",
                interval=interval,
                provider=self.capabilities.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                retrieval_timestamp=now_utc,
                unavailable_reason=reason,
            )

        if not self.is_configured():
            return unavailable("SSI FastConnect Data credentials are not configured.")
        if interval != "1d":
            return unavailable("SSI FastConnect Data adapter serves daily (1d) bars only.")
        if start > end:
            return unavailable("start_date is after end_date.")

        bars: Dict[datetime, OHLCVBar] = {}
        chunk_start = start
        try:
            # One calendar year per request keeps each window well under pageSize=1000 rows.
            while chunk_start <= end:
                chunk_end = min(end, chunk_start + timedelta(days=365))
                for page in range(1, MAX_PAGE_INDEX + 1):
                    body, err = self._get(
                        DAILY_OHLC_PATH,
                        {
                            "symbol": ticker,
                            "fromDate": _fmt(chunk_start),
                            "toDate": _fmt(chunk_end),
                            "pageIndex": page,
                            "pageSize": MAX_PAGE_SIZE,
                            "ascending": "true",
                        },
                    )
                    if err:
                        return unavailable(err)
                    rows = [r for r in (body.get("data") or []) if isinstance(r, dict)]
                    for row in rows:
                        bar = self._row_to_bar(row)
                        if bar is not None:
                            bars[bar.timestamp] = bar
                    total = body.get("totalRecord")
                    if len(rows) < MAX_PAGE_SIZE or (isinstance(total, int) and page * MAX_PAGE_SIZE >= total):
                        break
                chunk_start = chunk_end + timedelta(days=1)
        except Exception as exc:
            return unavailable(f"SSI FastConnect Data connection error: {exc}")

        ordered: List[OHLCVBar] = [bars[k] for k in sorted(bars)]
        if not ordered:
            return unavailable("SSI FastConnect Data returned no daily bars for this range.")
        return OHLCVResponse(
            instrument_id=f"{eff_mic}:{ticker}",
            ticker=ticker,
            exchange_mic=eff_mic,
            currency="VND",
            interval="1d",
            provider=self.capabilities.provider_id,
            data_status=DataStatus.HISTORICAL,
            market_timestamp=ordered[-1].timestamp,
            retrieval_timestamp=now_utc,
            bars=ordered,
        )

    @staticmethod
    def _row_to_bar(row: Dict[str, Any]) -> Optional[OHLCVBar]:
        try:
            d = datetime.strptime(str(row.get("TradingDate", "")).strip()[:10], "%d/%m/%Y")
        except ValueError:
            return None
        o, h, lo, c = (_num(row.get(k)) for k in ("Open", "High", "Low", "Close"))
        if None in (o, h, lo, c) or min(o, h, lo, c) <= 0:
            return None
        vol = _num(row.get("Volume")) or 0.0
        return OHLCVBar(
            timestamp=d.replace(tzinfo=timezone.utc),
            open=o,
            high=max(h, o, c, lo),
            low=min(lo, o, c, h),
            close=c,
            volume=int(vol),
        )
