"""Frankfurter v2 FX reference rate engine (open-source, $0, no API key).

Covers all 15 QuantAI target currencies:
  USD, EUR, GBP, CHF, JPY, HKD, CNY, KRW, SGD, AUD, CAD, VND, MYR, IDR, THB

STRICT PROVENANCE:
  - Always tagged DataStatus.DAILY_REFERENCE (official central-bank midpoints,
    NOT live FX dealing quotes with bid/ask spreads).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from app.core.models import DataStatus, FXConversionResponse, FXRatesResponse
from app.data.base import TTLCache

TARGET_CURRENCIES: Tuple[str, ...] = (
    "USD", "EUR", "GBP", "CHF", "JPY",
    "HKD", "CNY", "KRW", "SGD", "AUD",
    "CAD", "VND", "MYR", "IDR", "THB",
)

REFERENCE_WARNING = (
    "Frankfurter v2 provides official central-bank DAILY_REFERENCE midpoint rates, "
    "not live intraday FX dealing quotes or bid/ask spreads."
)


class FrankfurterFXProvider:
    provider_id = "frankfurter_v2"

    def __init__(
        self,
        base_url: str = "https://api.frankfurter.dev/v2",
        timeout: float = 10.0,
        http_get: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._http_get = http_get or httpx.get
        self._cache: TTLCache[FXRatesResponse] = TTLCache(ttl_seconds=1800.0)

    def get_latest_rates(
        self,
        base: str = "USD",
        quotes: Optional[List[str]] = None,
        as_of: Optional[date] = None,
    ) -> FXRatesResponse:
        now_utc = datetime.now(timezone.utc)
        base_ccy = base.upper().strip()
        target_list = [c.upper().strip() for c in (quotes or list(TARGET_CURRENCIES)) if c.upper().strip() != base_ccy]
        cache_key = f"{base_ccy}:{','.join(sorted(target_list))}:{as_of.isoformat() if as_of else 'latest'}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.copy(update={"retrieval_timestamp": now_utc})

        params: Dict[str, str] = {"base": base_ccy}
        if target_list:
            params["quotes"] = ",".join(target_list)
        if as_of is not None:
            params["date"] = as_of.isoformat()

        try:
            resp = self._http_get(
                f"{self._base_url}/rates",
                params=params,
                timeout=self._timeout,
            )
            if getattr(resp, "status_code", 200) != 200:
                return FXRatesResponse(
                    base=base_ccy,
                    provider=self.provider_id,
                    data_status=DataStatus.DATA_UNAVAILABLE,
                    retrieval_timestamp=now_utc,
                    unavailable_reason=f"Frankfurter v2 returned HTTP {resp.status_code}.",
                )
            rows = resp.json()
        except Exception as exc:
            return FXRatesResponse(
                base=base_ccy,
                provider=self.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                retrieval_timestamp=now_utc,
                unavailable_reason=f"Frankfurter v2 connection error: {exc}",
            )

        rates: Dict[str, float] = {}
        latest_ref_date: Optional[date] = None

        if isinstance(rows, list):
            for item in rows:
                quote_ccy = str(item.get("quote", "")).upper()
                rate_val = item.get("rate")
                ref_str = item.get("date")
                if quote_ccy and isinstance(rate_val, (int, float)) and rate_val > 0:
                    rates[quote_ccy] = float(rate_val)
                    if isinstance(ref_str, str):
                        parsed_d = date.fromisoformat(ref_str)
                        if latest_ref_date is None or parsed_d > latest_ref_date:
                            latest_ref_date = parsed_d

        if not rates:
            return FXRatesResponse(
                base=base_ccy,
                provider=self.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                retrieval_timestamp=now_utc,
                unavailable_reason="No valid FX reference rates returned by Frankfurter v2.",
            )

        result = FXRatesResponse(
            base=base_ccy,
            provider=self.provider_id,
            data_status=DataStatus.DAILY_REFERENCE,
            reference_date=latest_ref_date,
            retrieval_timestamp=now_utc,
            rates=rates,
            warnings=[REFERENCE_WARNING],
        )
        self._cache.set(cache_key, result)
        return result

    def convert(
        self,
        base: str,
        quote: str,
        amount: float,
        as_of: Optional[date] = None,
    ) -> FXConversionResponse:
        now_utc = datetime.now(timezone.utc)
        base_ccy = base.upper().strip()
        quote_ccy = quote.upper().strip()

        if base_ccy == quote_ccy:
            return FXConversionResponse(
                base=base_ccy,
                quote=quote_ccy,
                amount=amount,
                converted_amount=amount,
                rate=1.0,
                reference_date=as_of or now_utc.date(),
                provider=self.provider_id,
                data_status=DataStatus.DAILY_REFERENCE,
                retrieval_timestamp=now_utc,
                warnings=["Identity currency conversion (base == quote)."],
            )

        rates_resp = self.get_latest_rates(base=base_ccy, quotes=[quote_ccy], as_of=as_of)
        rate = rates_resp.rates.get(quote_ccy)
        if rates_resp.data_status == DataStatus.DATA_UNAVAILABLE or rate is None:
            return FXConversionResponse(
                base=base_ccy,
                quote=quote_ccy,
                amount=amount,
                provider=self.provider_id,
                data_status=DataStatus.DATA_UNAVAILABLE,
                retrieval_timestamp=now_utc,
                unavailable_reason=rates_resp.unavailable_reason or f"FX rate unavailable for {base_ccy}/{quote_ccy}.",
            )

        return FXConversionResponse(
            base=base_ccy,
            quote=quote_ccy,
            amount=amount,
            converted_amount=round(amount * rate, 6),
            rate=rate,
            reference_date=rates_resp.reference_date,
            provider=self.provider_id,
            data_status=DataStatus.DAILY_REFERENCE,
            retrieval_timestamp=now_utc,
            warnings=rates_resp.warnings,
        )
