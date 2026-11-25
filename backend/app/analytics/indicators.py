"""Trend, momentum, and volatility technical indicators.

Fixes every calculation bug audited in the Phase 0 prototype:
  - Exact index alignment (len(output) == len(input)).
  - Canonical Wilder RSI smoothing with avg_loss == 0 -> 100.0 and both 0 -> 50.0.
  - Explicit ddof=1 sample standard deviation for Bollinger Bands.
  - Graceful None padding when lookback length is insufficient.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np


def sma(prices: Sequence[float], period: int) -> List[Optional[float]]:
    if period <= 0:
        raise ValueError("SMA period must be positive.")
    n = len(prices)
    out: List[Optional[float]] = []
    for i in range(n):
        if i < period - 1:
            out.append(None)
        else:
            window = prices[i - period + 1 : i + 1]
            out.append(float(sum(window)) / period)
    return out


def ema(prices: Sequence[float], period: int) -> List[Optional[float]]:
    """Standard Exponential Moving Average seeded with SMA over the first `period` bars."""
    if period <= 0:
        raise ValueError("EMA period must be positive.")
    n = len(prices)
    if n < period:
        return [None] * n
    alpha = 2.0 / (period + 1.0)
    out: List[Optional[float]] = [None] * (period - 1)
    prev = float(sum(prices[:period])) / period
    out.append(prev)
    for i in range(period, n):
        curr = alpha * prices[i] + (1.0 - alpha) * prev
        out.append(curr)
        prev = curr
    return out


def rsi_wilder(prices: Sequence[float], period: int = 14) -> List[Optional[float]]:
    """Canonical Wilder's Relative Strength Index (RSI).

    Returns a list of exact length `len(prices)` where index `period` is the
    first defined RSI value. Handles zero-loss and flat-price edge cases cleanly.
    """
    if period <= 0:
        raise ValueError("RSI period must be positive.")
    n = len(prices)
    if n <= period:
        return [None] * n

    out: List[Optional[float]] = [None] * period
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains += diff
        elif diff < 0:
            losses -= diff

    avg_gain = gains / period
    avg_loss = losses / period

    def _compute_rsi(ag: float, al: float) -> float:
        if al == 0.0 and ag == 0.0:
            return 50.0
        if al == 0.0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    out.append(_compute_rsi(avg_gain, avg_loss))

    for i in range(period + 1, n):
        diff = prices[i] - prices[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out.append(_compute_rsi(avg_gain, avg_loss))

    return out


def macd(
    prices: Sequence[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Dict[str, List[Optional[float]]]:
    """Compute MACD line (EMA_12 - EMA_26), Signal line (EMA_9 of MACD), and Histogram."""
    n = len(prices)
    ema_fast = ema(prices, fast_period)
    ema_slow = ema(prices, slow_period)

    macd_line: List[Optional[float]] = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(ema_fast, ema_slow)
    ]

    valid_indices = [i for i, v in enumerate(macd_line) if v is not None]
    valid_values = [macd_line[i] for i in valid_indices if macd_line[i] is not None]

    signal_line: List[Optional[float]] = [None] * n
    histogram: List[Optional[float]] = [None] * n

    if len(valid_values) >= signal_period:
        sig_sub = ema([float(v) for v in valid_values], signal_period)
        for idx, sig_val in zip(valid_indices, sig_sub):
            signal_line[idx] = sig_val
            if sig_val is not None and macd_line[idx] is not None:
                histogram[idx] = macd_line[idx] - sig_val

    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def rate_of_change(prices: Sequence[float], period: int = 12) -> List[Optional[float]]:
    """Compute percentage Rate of Change: ((P_t - P_{t-k}) / P_{t-k}) * 100."""
    n = len(prices)
    out: List[Optional[float]] = []
    for i in range(n):
        if i < period or prices[i - period] <= 0:
            out.append(None)
        else:
            out.append(((prices[i] - prices[i - period]) / prices[i - period]) * 100.0)
    return out


def bollinger_bands(
    prices: Sequence[float],
    period: int = 20,
    num_std: float = 2.0,
    ddof: int = 1,
) -> Dict[str, List[Optional[float]]]:
    """Compute Bollinger Bands (middle SMA, upper/lower bands using sample std ddof=1)."""
    n = len(prices)
    middle: List[Optional[float]] = []
    upper: List[Optional[float]] = []
    lower: List[Optional[float]] = []

    for i in range(n):
        if i < period - 1:
            middle.append(None)
            upper.append(None)
            lower.append(None)
        else:
            window = np.asarray(prices[i - period + 1 : i + 1], dtype=float)
            mean = float(np.mean(window))
            std = float(np.std(window, ddof=ddof))
            middle.append(mean)
            upper.append(mean + num_std * std)
            lower.append(mean - num_std * std)

    return {"middle": middle, "upper": upper, "lower": lower}


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> List[Optional[float]]:
    """Compute Wilder's Average True Range (ATR)."""
    n = len(closes)
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows, and closes must have equal length.")
    if n == 0:
        return []

    true_ranges: List[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    if n < period:
        return [None] * n

    out: List[Optional[float]] = [None] * (period - 1)
    prev_atr = sum(true_ranges[:period]) / period
    out.append(prev_atr)
    for i in range(period, n):
        curr_atr = (prev_atr * (period - 1) + true_ranges[i]) / period
        out.append(curr_atr)
        prev_atr = curr_atr
    return out
