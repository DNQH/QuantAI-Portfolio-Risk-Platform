"""High-level Phase 2 Quantitative Analysis orchestrator and Pydantic schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.analytics.bars import adjusted_closes, adjusted_high_low_close, prepare_bars, resolve_periods_per_year
from app.analytics.indicators import (
    atr,
    bollinger_bands,
    ema,
    macd,
    rate_of_change,
    rsi_wilder,
    sma,
)
from app.analytics.returns import (
    annualized_return,
    annualized_volatility,
    cumulative_returns,
    drawdown_analysis,
    log_returns,
    rolling_volatility,
    sharpe_ratio,
    simple_returns,
    sortino_ratio,
)
from app.analytics.statistics import (
    correlation_and_covariance_matrices,
    descriptive_statistics,
)
from app.core.models import OHLCVBar


class SingleAssetAnalyticsRequest(BaseModel):
    instrument_id: str = Field(..., description="Exchange-qualified identifier, e.g. XNAS:AAPL")
    bars: List[OHLCVBar] = Field(..., min_items=2, description="Chronological OHLCV bars")
    risk_free_rate_annual: float = Field(default=0.0, description="Annualized risk-free rate (e.g. 0.04 for 4%)")
    periods_per_year: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Annualization factor. Defaults by interval (1d=252, 1wk=52, 1mo=12) or is inferred from timestamps.",
    )
    interval: str = Field(default="1d")


class SingleAssetSummaryMetrics(BaseModel):
    observations: int
    total_return: Optional[float]
    annualized_return: Optional[float]
    annualized_volatility: Optional[float]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown: Optional[float]
    max_drawdown_recovery_bars: Optional[int]
    latest_sma_20: Optional[float]
    latest_sma_50: Optional[float]
    latest_sma_100: Optional[float]
    latest_sma_200: Optional[float]
    latest_ema_12: Optional[float]
    latest_ema_26: Optional[float]
    latest_rsi_14: Optional[float]
    latest_macd: Optional[float]
    latest_macd_signal: Optional[float]
    latest_macd_histogram: Optional[float]
    latest_roc_12: Optional[float]
    latest_atr_14: Optional[float]
    mean_daily_return: Optional[float]
    median_daily_return: Optional[float]
    variance_daily_return: Optional[float]
    std_daily_return: Optional[float]
    skewness: Optional[float]
    excess_kurtosis: Optional[float]


class SingleAssetAnalyticsResponse(BaseModel):
    instrument_id: str
    interval: str
    computed_at_utc: datetime
    start_timestamp: datetime
    end_timestamp: datetime
    summary: SingleAssetSummaryMetrics
    timestamps: List[str]
    closes: List[float]
    simple_returns: List[Optional[float]]
    log_returns: List[Optional[float]]
    cumulative_returns: List[Optional[float]]
    drawdown_series: List[float]
    rolling_volatility_20: List[Optional[float]]
    sma_20: List[Optional[float]]
    sma_50: List[Optional[float]]
    ema_12: List[Optional[float]]
    ema_26: List[Optional[float]]
    rsi_14: List[Optional[float]]
    macd: List[Optional[float]]
    macd_signal: List[Optional[float]]
    macd_histogram: List[Optional[float]]
    bollinger_upper: List[Optional[float]]
    bollinger_middle: List[Optional[float]]
    bollinger_lower: List[Optional[float]]
    atr_14: List[Optional[float]]
    assumptions: List[str]


class MatrixAnalyticsRequest(BaseModel):
    asset_price_maps: Dict[str, Dict[str, float]] = Field(
        ...,
        description="Mapping of instrument_id -> {ISO_date: close_price}",
    )
    periods_per_year: int = Field(default=252, ge=1, le=365)


class MatrixAnalyticsResponse(BaseModel):
    symbols: List[str]
    aligned_return_observations: int
    periods_per_year: int
    computed_at_utc: datetime
    correlation_matrix: Dict[str, Dict[str, float]]
    annualized_covariance_matrix: Dict[str, Dict[str, float]]
    assumptions: List[str]


def _last_valid(seq: List[Optional[float]]) -> Optional[float]:
    return seq[-1] if seq else None


def run_single_asset_analytics(req: SingleAssetAnalyticsRequest) -> SingleAssetAnalyticsResponse:
    ordered, data_warnings = prepare_bars(req.bars, min_count=2, context="Single-asset analytics")
    timestamps = [b.timestamp.isoformat() for b in ordered]
    closes = adjusted_closes(ordered)
    # ATR must use high/low/close on the same (adjusted) basis as the closes.
    atr_highs, atr_lows, atr_closes = adjusted_high_low_close(ordered)
    ppy = resolve_periods_per_year(req.periods_per_year, req.interval, [b.timestamp for b in ordered])

    s_ret = simple_returns(closes)
    l_ret = log_returns(closes)
    c_ret = cumulative_returns(closes)
    dd = drawdown_analysis(closes)
    roll_vol_20 = rolling_volatility(s_ret, window=20, periods_per_year=ppy)

    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    sma100 = sma(closes, 100)
    sma200 = sma(closes, 200)
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    rsi14 = rsi_wilder(closes, 14)
    macd_out = macd(closes, 12, 26, 9)
    roc12 = rate_of_change(closes, 12)
    bb = bollinger_bands(closes, 20, 2.0, ddof=1)
    atr14 = atr(atr_highs, atr_lows, atr_closes, 14)
    stats_out = descriptive_statistics(s_ret)

    summary = SingleAssetSummaryMetrics(
        observations=len(ordered),
        total_return=c_ret[-1] if c_ret else None,
        annualized_return=annualized_return(closes, ppy),
        annualized_volatility=annualized_volatility(s_ret, ppy),
        sharpe_ratio=sharpe_ratio(s_ret, req.risk_free_rate_annual, ppy),
        sortino_ratio=sortino_ratio(s_ret, req.risk_free_rate_annual, ppy),
        max_drawdown=dd.max_drawdown,
        max_drawdown_recovery_bars=dd.recovery_bars,
        latest_sma_20=_last_valid(sma20),
        latest_sma_50=_last_valid(sma50),
        latest_sma_100=_last_valid(sma100),
        latest_sma_200=_last_valid(sma200),
        latest_ema_12=_last_valid(ema12),
        latest_ema_26=_last_valid(ema26),
        latest_rsi_14=_last_valid(rsi14),
        latest_macd=_last_valid(macd_out["macd"]),
        latest_macd_signal=_last_valid(macd_out["signal"]),
        latest_macd_histogram=_last_valid(macd_out["histogram"]),
        latest_roc_12=_last_valid(roc12),
        latest_atr_14=_last_valid(atr14),
        mean_daily_return=stats_out["mean"],
        median_daily_return=stats_out["median"],
        variance_daily_return=stats_out["variance"],
        std_daily_return=stats_out["std_dev"],
        skewness=stats_out["skewness"],
        excess_kurtosis=stats_out["excess_kurtosis"],
    )

    return SingleAssetAnalyticsResponse(
        instrument_id=req.instrument_id,
        interval=req.interval,
        computed_at_utc=datetime.now(timezone.utc),
        start_timestamp=ordered[0].timestamp,
        end_timestamp=ordered[-1].timestamp,
        summary=summary,
        timestamps=timestamps,
        closes=closes,
        simple_returns=s_ret,
        log_returns=l_ret,
        cumulative_returns=c_ret,
        drawdown_series=dd.series,
        rolling_volatility_20=roll_vol_20,
        sma_20=sma20,
        sma_50=sma50,
        ema_12=ema12,
        ema_26=ema26,
        rsi_14=rsi14,
        macd=macd_out["macd"],
        macd_signal=macd_out["signal"],
        macd_histogram=macd_out["histogram"],
        bollinger_upper=bb["upper"],
        bollinger_middle=bb["middle"],
        bollinger_lower=bb["lower"],
        atr_14=atr14,
        assumptions=[
            f"Annualization assumes {ppy:.1f} periods per year (interval={req.interval}).",
            f"Sharpe and Sortino ratios use annualized risk-free rate = {req.risk_free_rate_annual:.4%}.",
            "Volatility and Bollinger Bands use unbiased sample standard deviation (ddof=1).",
            "RSI (14) and ATR (14) use canonical Wilder exponential smoothing; ATR high/low are rescaled to the adjusted-close basis.",
            "Historical metrics are backward-looking descriptors and do not guarantee future returns.",
        ]
        + data_warnings,
    )


def run_matrix_analytics(req: MatrixAnalyticsRequest) -> MatrixAnalyticsResponse:
    symbols, count, corr, cov = correlation_and_covariance_matrices(
        req.asset_price_maps, periods_per_year=req.periods_per_year
    )
    return MatrixAnalyticsResponse(
        symbols=symbols,
        aligned_return_observations=count,
        periods_per_year=req.periods_per_year,
        computed_at_utc=datetime.now(timezone.utc),
        correlation_matrix=corr,
        annualized_covariance_matrix=cov,
        assumptions=[
            "Multi-asset prices are inner-joined on common trading dates before computing daily simple returns.",
            f"Covariance matrix is annualized using sample covariance (ddof=1) multiplied by {req.periods_per_year}.",
            "Pearson linear correlation assumes stationarity over the estimation window and may understate tail dependence.",
        ],
    )
