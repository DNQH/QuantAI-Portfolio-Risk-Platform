"""Pydantic schemas and strict data-integrity enumerations for QuantAI."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DataStatus(str, Enum):
    """Strict provenance and freshness classification.

    Never label delayed, historical, reference, or unavailable feeds as LIVE.
    """

    LIVE = "LIVE"
    DELAYED = "DELAYED"
    HISTORICAL = "HISTORICAL"
    DAILY_REFERENCE = "DAILY_REFERENCE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


class MarketSession(str, Enum):
    PRE_MARKET = "PRE_MARKET"
    REGULAR = "REGULAR"
    LUNCH_BREAK = "LUNCH_BREAK"
    AFTER_HOURS = "AFTER_HOURS"
    CLOSED = "CLOSED"
    HOLIDAY = "HOLIDAY"
    MIGRATION_SUSPENDED = "MIGRATION_SUSPENDED"


class CoverageStatus(str, Enum):
    LIVE_VERIFIED = "LIVE_VERIFIED"
    DELAYED_AVAILABLE = "DELAYED_AVAILABLE"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    CREDENTIALS_REQUIRED = "CREDENTIALS_REQUIRED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


class AssetType(str, Enum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    INDEX = "INDEX"
    FX = "FX"


class Instrument(BaseModel):
    """Exchange-qualified global security identifier (ISO 10383 MIC + ticker)."""

    instrument_id: str = Field(..., description="Canonical exchange-qualified ID, e.g. XNAS:AAPL or XSTC:FPT")
    ticker: str
    exchange_mic: str = Field(..., description="ISO 10383 Market Identifier Code (e.g. XNYS, XNAS, XSTC, XHAI)")
    exchange_acronym: str = Field(..., description="Human-readable exchange acronym (e.g. NYSE, NASDAQ, HOSE, HNX)")
    company_name: str
    country: str
    currency: str
    sector: str = "Unknown"
    industry: str = "Unknown"
    asset_type: AssetType = AssetType.EQUITY
    timezone: str
    migration_note: Optional[str] = None


class MarketSessionInfo(BaseModel):
    exchange_mic: str
    exchange_acronym: str
    timezone: str
    local_time: str
    session: MarketSession
    is_open: bool
    note: Optional[str] = None


class QuoteResponse(BaseModel):
    """Normalized market quote with mandatory freshness and timestamp provenance."""

    instrument_id: str
    ticker: str
    exchange_mic: str
    currency: str
    provider: str
    data_status: DataStatus
    delay_minutes: Optional[int] = None
    market_session: MarketSession
    market_timestamp: Optional[datetime] = Field(
        None, description="UTC timestamp of the underlying exchange observation"
    )
    retrieval_timestamp: datetime = Field(
        ..., description="UTC timestamp when QuantAI retrieved the observation"
    )
    price: Optional[float] = None
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    unavailable_reason: Optional[str] = None


class OHLCVBar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    adjusted_close: Optional[float] = None
    volume: int


class OHLCVResponse(BaseModel):
    instrument_id: str
    ticker: str
    exchange_mic: str
    currency: str
    interval: str
    provider: str
    data_status: DataStatus
    market_timestamp: Optional[datetime] = None
    retrieval_timestamp: datetime
    bars: List[OHLCVBar] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    unavailable_reason: Optional[str] = None


class FXRateItem(BaseModel):
    base: str
    quote: str
    rate: float
    reference_date: date


class FXRatesResponse(BaseModel):
    base: str
    provider: str
    data_status: DataStatus = DataStatus.DAILY_REFERENCE
    reference_date: Optional[date] = None
    retrieval_timestamp: datetime
    rates: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    unavailable_reason: Optional[str] = None


class FXConversionResponse(BaseModel):
    base: str
    quote: str
    amount: float
    converted_amount: Optional[float] = None
    rate: Optional[float] = None
    reference_date: Optional[date] = None
    provider: str
    data_status: DataStatus
    retrieval_timestamp: datetime
    warnings: List[str] = Field(default_factory=list)
    unavailable_reason: Optional[str] = None


class ExchangeCoverageEntry(BaseModel):
    exchange_mic: str
    exchange_acronym: str
    exchange_name: str
    region: str
    country: str
    currency: str
    timezone: str
    phase: str
    coverage_status: CoverageStatus
    quote_data_status: DataStatus
    historical_data_status: DataStatus
    primary_provider: str
    fallback_provider: Optional[str] = None
    requires_credentials: bool = False
    requires_paid_plan_for_live: bool = False
    notes: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp_utc: datetime
    configured_providers: Dict[str, bool]
    database_ready: bool
