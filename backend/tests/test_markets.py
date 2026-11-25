"""Supported market set: United States, Vietnam and Italy (Borsa Italiana / Euronext Milan)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.calendar import get_market_session
from app.core.config import Settings
from app.core.models import MarketSession
from app.core.symbology import GLOBAL_INSTRUMENTS, MIC_TO_ACRONYM, search_seed_instruments, to_yfinance_symbol
from app.data.registry import MarketDataRegistry

SUPPORTED = {"XNYS", "XNAS", "XSTC", "XHAI", "XUPC", "XMIL"}


def test_only_supported_markets_remain() -> None:
    assert set(MIC_TO_ACRONYM) == SUPPORTED
    assert {i.exchange_mic for i in GLOBAL_INSTRUMENTS} == SUPPORTED
    assert {i.country for i in GLOBAL_INSTRUMENTS} == {"United States", "Vietnam", "Italy"}
    reg = MarketDataRegistry(settings=Settings(database_path=":memory:", enable_yfinance_fallback=False))
    assert {e.exchange_mic for e in reg.get_exchange_coverage()} == SUPPORTED


def test_italy_universe() -> None:
    italy = search_seed_instruments(exchange="XMIL")
    assert len(italy) >= 15
    assert all(i.currency == "EUR" and i.timezone == "Europe/Rome" and i.country == "Italy" for i in italy)
    # Broad sector coverage so diversification analysis has real choices in Italy.
    assert len({i.sector for i in italy}) >= 9
    assert to_yfinance_symbol("RACE", "XMIL") == "RACE.MI"


@pytest.mark.parametrize(
    "utc, expected",
    [
        ("2026-11-25T07:30", MarketSession.PRE_MARKET),   # 08:30 CET opening auction
        ("2026-11-25T08:00", MarketSession.REGULAR),      # 09:00 CET continuous trading
        ("2026-11-25T16:29", MarketSession.REGULAR),      # 17:29 CET
        ("2026-11-25T16:31", MarketSession.CLOSED),       # 17:31 CET
        ("2026-07-15T07:15", MarketSession.REGULAR),      # 09:15 CEST (summer time)
        ("2026-11-28T10:00", MarketSession.CLOSED),       # Saturday
        ("2026-12-24T10:00", MarketSession.HOLIDAY),      # Christmas Eve
        ("2026-04-06T10:00", MarketSession.HOLIDAY),      # Easter Monday
    ],
)
def test_borsa_italiana_sessions(utc: str, expected: MarketSession) -> None:
    now = datetime.fromisoformat(utc).replace(tzinfo=timezone.utc)
    assert get_market_session("XMIL", now_utc=now).session == expected
