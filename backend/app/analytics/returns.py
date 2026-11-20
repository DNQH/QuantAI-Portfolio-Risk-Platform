"""Return calculations, volatility, risk-adjusted ratios, and drawdown analysis.

All functions operate on finite, chronologically ordered price series and
handle insufficient lookback periods gracefully without fabricating values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np


@dataclass(frozen=True)
class DrawdownResult:
    max_drawdown: Optional[float]
    peak_index: Optional[int]
    trough_index: Optional[int]
    recovery_index: Optional[int]
    recovery_bars: Optional[int]
    series: List[float]


def simple_returns(prices: Sequence[float]) -> List[Optional[float]]:
    """Compute period-over-period simple returns: (P_t - P_{t-1}) / P_{t-1}."""
    n = len(prices)
    if n == 0:
        return []
    out: List[Optional[float]] = [None]
    for i in range(1, n):
        prev, curr = prices[i - 1], prices[i]
        if prev is None or curr is None or prev <= 0 or not (math.isfinite(prev) and math.isfinite(curr)):
            out.append(None)
        else:
            out.append((curr - prev) / prev)
    return out


def log_returns(prices: Sequence[float]) -> List[Optional[float]]:
    """Compute period-over-period logarithmic returns: ln(P_t / P_{t-1})."""
    n = len(prices)
    if n == 0:
        return []
    out: List[Optional[float]] = [None]
    for i in range(1, n):
        prev, curr = prices[i - 1], prices[i]
        if prev is None or curr is None or prev <= 0 or curr <= 0 or not (math.isfinite(prev) and math.isfinite(curr)):
            out.append(None)
        else:
            out.append(math.log(curr / prev))
    return out


def cumulative_returns(prices: Sequence[float]) -> List[Optional[float]]:
    """Compute cumulative wealth return relative to initial price: P_t / P_0 - 1."""
    if not prices or prices[0] <= 0:
        return [None for _ in prices]
    p0 = prices[0]
    return [((p / p0) - 1.0) if (p is not None and p > 0 and math.isfinite(p)) else None for p in prices]


def annualized_return(prices: Sequence[float], periods_per_year: int = 252) -> Optional[float]:
    """Compute geometric annualized return (CAGR) over T = len(prices) - 1 return periods."""
    if len(prices) < 2 or prices[0] <= 0 or prices[-1] <= 0:
        return None
    n_periods = len(prices) - 1
    total_growth = prices[-1] / prices[0]
    return (total_growth ** (periods_per_year / n_periods)) - 1.0


def annualized_volatility(
    returns: Sequence[Optional[float]],
    periods_per_year: int = 252,
    ddof: int = 1,
) -> Optional[float]:
    """Compute annualized sample volatility: std(r, ddof=1) * sqrt(periods_per_year)."""
    valid = [r for r in returns if r is not None and math.isfinite(r)]
    if len(valid) <= ddof:
        return None
    std = float(np.std(valid, ddof=ddof))
    return std * math.sqrt(periods_per_year)


def rolling_volatility(
    returns: Sequence[Optional[float]],
    window: int = 20,
    periods_per_year: int = 252,
    ddof: int = 1,
) -> List[Optional[float]]:
    """Compute annualized rolling sample standard deviation of returns."""
    n = len(returns)
    out: List[Optional[float]] = []
    scale = math.sqrt(periods_per_year)
    for i in range(n):
        if i < window:
            out.append(None)
            continue
        slice_vals = [r for r in returns[i - window + 1 : i + 1] if r is not None and math.isfinite(r)]
        if len(slice_vals) < window or len(slice_vals) <= ddof:
            out.append(None)
        else:
            out.append(float(np.std(slice_vals, ddof=ddof)) * scale)
    return out


def sharpe_ratio(
    returns: Sequence[Optional[float]],
    risk_free_rate_annual: float = 0.0,
    periods_per_year: int = 252,
) -> Optional[float]:
    """Compute annualized Sharpe Ratio: (mean_r * N - Rf) / (std_r * sqrt(N))."""
    valid = [r for r in returns if r is not None and math.isfinite(r)]
    if len(valid) < 2:
        return None
    arr = np.asarray(valid, dtype=float)
    std = float(np.std(arr, ddof=1))
    if std == 0.0:
        return None
    ann_mean = float(np.mean(arr)) * periods_per_year
    ann_vol = std * math.sqrt(periods_per_year)
    return (ann_mean - risk_free_rate_annual) / ann_vol


def sortino_ratio(
    returns: Sequence[Optional[float]],
    risk_free_rate_annual: float = 0.0,
    periods_per_year: int = 252,
) -> Optional[float]:
    """Compute annualized Sortino Ratio using downside semi-deviation below daily Rf."""
    valid = [r for r in returns if r is not None and math.isfinite(r)]
    if len(valid) < 2:
        return None
    arr = np.asarray(valid, dtype=float)
    rf_period = risk_free_rate_annual / periods_per_year
    downside_diff = np.minimum(0.0, arr - rf_period)
    downside_dev = math.sqrt(float(np.mean(downside_diff ** 2)))
    if downside_dev == 0.0:
        return None
    ann_mean = float(np.mean(arr)) * periods_per_year
    ann_downside = downside_dev * math.sqrt(periods_per_year)
    return (ann_mean - risk_free_rate_annual) / ann_downside


def drawdown_analysis(prices: Sequence[float]) -> DrawdownResult:
    """Compute running drawdown series, Maximum Drawdown, and recovery period."""
    if not prices:
        return DrawdownResult(None, None, None, None, None, [])

    running_peak = prices[0]
    running_peak_idx = 0
    dd_series: List[float] = []

    max_dd = 0.0
    mdd_peak_idx = 0
    mdd_trough_idx = 0

    for i, p in enumerate(prices):
        if p > running_peak:
            running_peak = p
            running_peak_idx = i
        dd = (p - running_peak) / running_peak if running_peak > 0 else 0.0
        dd_series.append(dd)
        if dd < max_dd:
            max_dd = dd
            mdd_peak_idx = running_peak_idx
            mdd_trough_idx = i

    if max_dd == 0.0:
        return DrawdownResult(0.0, 0, 0, 0, 0, dd_series)

    peak_price = prices[mdd_peak_idx]
    recovery_idx: Optional[int] = None
    for j in range(mdd_trough_idx + 1, len(prices)):
        if prices[j] >= peak_price:
            recovery_idx = j
            break

    recovery_bars = (recovery_idx - mdd_trough_idx) if recovery_idx is not None else None
    return DrawdownResult(
        max_drawdown=max_dd,
        peak_index=mdd_peak_idx,
        trough_index=mdd_trough_idx,
        recovery_index=recovery_idx,
        recovery_bars=recovery_bars,
        series=dd_series,
    )
