"""Data Freshness State Machine and integrity validator.

Enforces QuantAI's strict anti-fabrication and timestamp integrity rules:
  - Never label delayed, closed-market, historical, or reference data as LIVE.
  - Always distinguish market_timestamp from retrieval_timestamp.
  - Reject negative, zero, or NaN prices as DATA_UNAVAILABLE.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.core.models import DataStatus, MarketSession, OHLCVBar


def validate_price(value: Optional[float]) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    return math.isfinite(value) and value > 0.0


def validate_ohlcv_bars(bars: List[OHLCVBar]) -> Tuple[List[OHLCVBar], List[str]]:
    """Deduplicate by timestamp, sort chronologically, and drop corrupted bars."""
    warnings: List[str] = []
    seen: dict[datetime, OHLCVBar] = {}
    dropped = 0
    duplicates = 0

    for bar in bars:
        if not (
            validate_price(bar.open)
            and validate_price(bar.high)
            and validate_price(bar.low)
            and validate_price(bar.close)
            and bar.high >= max(bar.open, bar.close, bar.low)
            and bar.low <= min(bar.open, bar.close, bar.high)
            and bar.volume >= 0
        ):
            dropped += 1
            continue
        ts = bar.timestamp if bar.timestamp.tzinfo else bar.timestamp.replace(tzinfo=timezone.utc)
        if ts in seen:
            duplicates += 1
        seen[ts] = bar.copy(update={"timestamp": ts})

    if dropped:
        warnings.append(f"Dropped {dropped} corrupted OHLCV bar(s) failing integrity checks.")
    if duplicates:
        warnings.append(f"Deduplicated {duplicates} duplicate timestamp observation(s).")

    cleaned = [seen[ts] for ts in sorted(seen.keys())]
    return cleaned, warnings


def classify_quote_freshness(
    *,
    price: Optional[float],
    market_timestamp: Optional[datetime],
    retrieval_timestamp: datetime,
    market_session: MarketSession,
    provider_entitled_live: bool,
    provider_declared_delay_minutes: Optional[int] = None,
    max_live_age_seconds: int = 120,
) -> Tuple[DataStatus, Optional[int], List[str]]:
    """Deterministically classify a quote's DataStatus and delay minutes."""
    warnings: List[str] = []

    if not validate_price(price):
        return DataStatus.DATA_UNAVAILABLE, None, ["Missing or invalid price observation."]

    if market_session == MarketSession.MIGRATION_SUSPENDED:
        warnings.append("Instrument is suspended during scheduled HNX-to-HOSE migration.")
        return DataStatus.HISTORICAL, None, warnings

    if market_session in {MarketSession.CLOSED, MarketSession.HOLIDAY, MarketSession.LUNCH_BREAK}:
        warnings.append(
            f"Exchange session is {market_session.value}; last available trade/close is not live."
        )
        return DataStatus.HISTORICAL, None, warnings

    if market_timestamp is None:
        warnings.append("Exchange observation timestamp unavailable; cannot verify LIVE status.")
        return DataStatus.DELAYED, provider_declared_delay_minutes, warnings

    mkt_utc = market_timestamp if market_timestamp.tzinfo else market_timestamp.replace(tzinfo=timezone.utc)
    ret_utc = retrieval_timestamp if retrieval_timestamp.tzinfo else retrieval_timestamp.replace(tzinfo=timezone.utc)
    age_seconds = max(0.0, (ret_utc - mkt_utc).total_seconds())
    computed_delay_min = int(age_seconds // 60)

    if not provider_entitled_live:
        delay = provider_declared_delay_minutes if provider_declared_delay_minutes is not None else max(15, computed_delay_min)
        warnings.append("Provider is not verified for real-time exchange entitlement.")
        return DataStatus.DELAYED, delay, warnings

    if age_seconds <= max_live_age_seconds:
        return DataStatus.LIVE, 0, warnings

    warnings.append(
        f"Quote observation age ({int(age_seconds)}s) exceeds LIVE threshold ({max_live_age_seconds}s)."
    )
    return DataStatus.DELAYED, max(1, computed_delay_min), warnings
