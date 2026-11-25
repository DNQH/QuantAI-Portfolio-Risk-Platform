"""The coverage table must only show LIVE where a real-time quote source is wired up."""

from __future__ import annotations

from app.core.config import Settings
from app.core.models import CoverageStatus, DataStatus
from app.data.registry import MarketDataRegistry

GLOBAL = {"XMIL"}  # Italy: the only non-US, non-Vietnam market


class _YFReady:
    """Stand-in for an installed yfinance (CI does not install it)."""

    def is_configured(self) -> bool:
        return True


def _coverage(**keys):
    settings = Settings(database_path=":memory:", enable_yfinance_fallback=True, gemini_api_key=None, **keys)
    reg = MarketDataRegistry(settings=settings, yfinance_fallback=_YFReady())
    return reg, {e.exchange_mic: e for e in reg.get_exchange_coverage()}


def test_paid_key_alone_does_not_make_global_markets_live() -> None:
    # Regression: a Twelve Data / EODHD key used to flip every non-US market to LIVE although
    # get_quote() serves those markets from yfinance and the paid quote adapters are stubs.
    _, cov = _coverage(twelvedata_api_key="td", eodhd_api_key="eod")
    for mic in GLOBAL:
        e = cov[mic]
        assert e.quote_data_status == DataStatus.DELAYED, mic
        assert e.coverage_status == CoverageStatus.DELAYED_AVAILABLE, mic
        assert e.primary_provider == "yfinance (Delayed)", mic
        assert "Twelve Data key is configured" in e.notes, mic


def test_no_keys_global_delayed_without_twelvedata_note() -> None:
    _, cov = _coverage()
    for mic in GLOBAL:
        assert cov[mic].quote_data_status == DataStatus.DELAYED
        assert "Twelve Data key" not in cov[mic].notes


def test_global_live_once_a_real_time_adapter_exists() -> None:
    reg, _ = _coverage(twelvedata_api_key="td")
    reg.twelvedata.live_quotes_implemented = True  # simulate a future real adapter
    cov = {e.exchange_mic: e for e in reg.get_exchange_coverage()}
    for mic in GLOBAL:
        assert cov[mic].quote_data_status == DataStatus.LIVE
        assert cov[mic].primary_provider == "Twelve Data (Live Global)"


def test_us_live_with_finnhub_key_and_vietnam_needs_ssi() -> None:
    _, cov = _coverage(finnhub_api_key="fh")
    assert cov["XNYS"].quote_data_status == DataStatus.LIVE
    assert cov["XNAS"].quote_data_status == DataStatus.LIVE
    for mic in ("XSTC", "XHAI", "XUPC"):
        assert cov[mic].quote_data_status == DataStatus.DELAYED
