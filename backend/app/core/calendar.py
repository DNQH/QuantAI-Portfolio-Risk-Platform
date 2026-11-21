"""Global exchange market calendar and trading-session resolver.

Accounts for exchange time zones, DST transitions (via stdlib zoneinfo),
regular trading hours, lunch breaks (HOSE/HNX), US pre/after-hours sessions,
and major public market holidays so market closures are never misclassified
as API failures.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Dict, FrozenSet, Optional, Tuple
from zoneinfo import ZoneInfo

from app.core.models import MarketSession, MarketSessionInfo


@dataclass(frozen=True)
class ExchangeSchedule:
    mic: str
    acronym: str
    timezone_name: str
    regular_open: time
    regular_close: time
    pre_market_open: Optional[time] = None
    after_hours_close: Optional[time] = None
    lunch_start: Optional[time] = None
    lunch_end: Optional[time] = None
    holidays_2026: FrozenSet[date] = frozenset()


US_HOLIDAYS_2026: FrozenSet[date] = frozenset(
    {
        date(2026, 1, 1),   # New Year's Day
        date(2026, 1, 19),  # MLK Day
        date(2026, 2, 16),  # Presidents' Day
        date(2026, 4, 3),   # Good Friday
        date(2026, 5, 25),  # Memorial Day
        date(2026, 6, 19),  # Juneteenth
        date(2026, 7, 3),   # Independence Day (observed)
        date(2026, 9, 7),   # Labor Day
        date(2026, 11, 26), # Thanksgiving
        date(2026, 12, 25), # Christmas
    }
)

VN_HOLIDAYS_2026: FrozenSet[date] = frozenset(
    {
        date(2026, 1, 1),   # New Year's Day
        date(2026, 2, 16),  # Tet Holiday window
        date(2026, 2, 17),
        date(2026, 2, 18),
        date(2026, 2, 19),
        date(2026, 2, 20),
        date(2026, 4, 27),  # Hung Kings' Commemoration (observed)
        date(2026, 4, 30),  # Reunification Day
        date(2026, 5, 1),   # International Workers' Day
        date(2026, 9, 2),   # National Day
    }
)

EXCHANGE_SCHEDULES: Dict[str, ExchangeSchedule] = {
    "XNYS": ExchangeSchedule(
        mic="XNYS",
        acronym="NYSE",
        timezone_name="America/New_York",
        pre_market_open=time(4, 0),
        regular_open=time(9, 30),
        regular_close=time(16, 0),
        after_hours_close=time(20, 0),
        holidays_2026=US_HOLIDAYS_2026,
    ),
    "XNAS": ExchangeSchedule(
        mic="XNAS",
        acronym="NASDAQ",
        timezone_name="America/New_York",
        pre_market_open=time(4, 0),
        regular_open=time(9, 30),
        regular_close=time(16, 0),
        after_hours_close=time(20, 0),
        holidays_2026=US_HOLIDAYS_2026,
    ),
    "XSTC": ExchangeSchedule(
        mic="XSTC",
        acronym="HOSE",
        timezone_name="Asia/Ho_Chi_Minh",
        regular_open=time(9, 0),
        lunch_start=time(11, 30),
        lunch_end=time(13, 0),
        regular_close=time(14, 45),
        holidays_2026=VN_HOLIDAYS_2026,
    ),
    "XHAI": ExchangeSchedule(
        mic="XHAI",
        acronym="HNX",
        timezone_name="Asia/Ho_Chi_Minh",
        regular_open=time(9, 0),
        lunch_start=time(11, 30),
        lunch_end=time(13, 0),
        regular_close=time(15, 0),
        holidays_2026=VN_HOLIDAYS_2026,
    ),
    "XUPC": ExchangeSchedule(
        mic="XUPC",
        acronym="UPCOM",
        timezone_name="Asia/Ho_Chi_Minh",
        regular_open=time(9, 0),
        lunch_start=time(11, 30),
        lunch_end=time(13, 0),
        regular_close=time(15, 0),
        holidays_2026=VN_HOLIDAYS_2026,
    ),
}


def get_market_session(
    exchange_mic: str,
    now_utc: Optional[datetime] = None,
    is_migration_suspended: bool = False,
) -> MarketSessionInfo:
    """Evaluate the exact trading session for an exchange at a UTC timestamp."""
    mic = exchange_mic.upper().strip()
    schedule = EXCHANGE_SCHEDULES.get(mic)
    utc_dt = now_utc or datetime.now(timezone.utc)
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    if schedule is None:
        return MarketSessionInfo(
            exchange_mic=mic,
            exchange_acronym=mic,
            timezone="UTC",
            local_time=utc_dt.isoformat(),
            session=MarketSession.CLOSED,
            is_open=False,
            note="Exchange calendar not yet configured in Phase 1.",
        )

    tz = ZoneInfo(schedule.timezone_name)
    local_dt = utc_dt.astimezone(tz)
    local_date = local_dt.date()
    local_t = local_dt.time().replace(tzinfo=None)

    if is_migration_suspended:
        return MarketSessionInfo(
            exchange_mic=schedule.mic,
            exchange_acronym=schedule.acronym,
            timezone=schedule.timezone_name,
            local_time=local_dt.isoformat(),
            session=MarketSession.MIGRATION_SUSPENDED,
            is_open=False,
            note="Instrument suspended during scheduled HNX-to-HOSE market transfer.",
        )

    if local_date.weekday() >= 5:
        return MarketSessionInfo(
            exchange_mic=schedule.mic,
            exchange_acronym=schedule.acronym,
            timezone=schedule.timezone_name,
            local_time=local_dt.isoformat(),
            session=MarketSession.CLOSED,
            is_open=False,
            note="Weekend market closure (not an API failure).",
        )

    if local_date in schedule.holidays_2026:
        return MarketSessionInfo(
            exchange_mic=schedule.mic,
            exchange_acronym=schedule.acronym,
            timezone=schedule.timezone_name,
            local_time=local_dt.isoformat(),
            session=MarketSession.HOLIDAY,
            is_open=False,
            note="Scheduled exchange public holiday (not an API failure).",
        )

    if schedule.lunch_start and schedule.lunch_end and schedule.lunch_start <= local_t < schedule.lunch_end:
        return MarketSessionInfo(
            exchange_mic=schedule.mic,
            exchange_acronym=schedule.acronym,
            timezone=schedule.timezone_name,
            local_time=local_dt.isoformat(),
            session=MarketSession.LUNCH_BREAK,
            is_open=False,
            note="Midday exchange lunch break.",
        )

    if schedule.regular_open <= local_t < schedule.regular_close:
        return MarketSessionInfo(
            exchange_mic=schedule.mic,
            exchange_acronym=schedule.acronym,
            timezone=schedule.timezone_name,
            local_time=local_dt.isoformat(),
            session=MarketSession.REGULAR,
            is_open=True,
        )

    if schedule.pre_market_open and schedule.pre_market_open <= local_t < schedule.regular_open:
        return MarketSessionInfo(
            exchange_mic=schedule.mic,
            exchange_acronym=schedule.acronym,
            timezone=schedule.timezone_name,
            local_time=local_dt.isoformat(),
            session=MarketSession.PRE_MARKET,
            is_open=True,
            note="Pre-market extended session.",
        )

    if schedule.after_hours_close and schedule.regular_close <= local_t < schedule.after_hours_close:
        return MarketSessionInfo(
            exchange_mic=schedule.mic,
            exchange_acronym=schedule.acronym,
            timezone=schedule.timezone_name,
            local_time=local_dt.isoformat(),
            session=MarketSession.AFTER_HOURS,
            is_open=True,
            note="After-hours extended session.",
        )

    return MarketSessionInfo(
        exchange_mic=schedule.mic,
        exchange_acronym=schedule.acronym,
        timezone=schedule.timezone_name,
        local_time=local_dt.isoformat(),
        session=MarketSession.CLOSED,
        is_open=False,
        note="Outside regular and extended exchange hours.",
    )
