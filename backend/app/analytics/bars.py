"""Input hygiene for user-supplied OHLCV bars used by analytics, ML and backtests.

Provider adapters already run ``validate_ohlcv_bars``; API request bodies did not.
Every quantitative entry point now funnels bars through :func:`prepare_bars` so
duplicated timestamps, unsorted input, NaN/inf prices and non-positive closes can
never reach the return / indicator maths.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from app.core.models import OHLCVBar
from app.data.freshness import validate_ohlcv_bars

# Canonical annualisation factors for bar intervals (equity trading calendars).
INTERVAL_PERIODS_PER_YEAR = {
    "1d": 252,
    "1wk": 52,
    "1w": 52,
    "1mo": 12,
}


def prepare_bars(bars: Sequence[OHLCVBar], min_count: int, context: str = "analysis") -> Tuple[List[OHLCVBar], List[str]]:
    """Sort, de-duplicate and drop corrupted bars; reject if fewer than ``min_count`` remain."""
    cleaned, warnings = validate_ohlcv_bars(list(bars))
    out: List[OHLCVBar] = []
    fixed_adj = 0
    for b in cleaned:
        adj = b.adjusted_close
        if adj is not None and not (math.isfinite(adj) and adj > 0):
            out.append(b.copy(update={"adjusted_close": None}))
            fixed_adj += 1
        else:
            out.append(b)
    if fixed_adj:
        warnings.append(f"Ignored {fixed_adj} invalid adjusted_close value(s); fell back to raw close.")
    if len(out) < min_count:
        raise ValueError(
            f"{context}: only {len(out)} valid OHLCV bar(s) after integrity checks (minimum {min_count} required)."
        )
    return out, warnings


def adjusted_closes(bars: Sequence[OHLCVBar]) -> List[float]:
    return [float(b.adjusted_close if b.adjusted_close is not None else b.close) for b in bars]


def adjusted_high_low_close(bars: Sequence[OHLCVBar]) -> Tuple[List[float], List[float], List[float]]:
    """Return (high, low, close) expressed on the same split/dividend-adjusted basis.

    Providers such as yfinance (auto_adjust=False) deliver raw high/low/close plus a
    separately adjusted close. Mixing adjusted closes with raw highs/lows corrupts the
    True Range around every split or dividend, so highs/lows are rescaled by the
    per-bar adjustment factor adjusted_close / close.
    """
    highs: List[float] = []
    lows: List[float] = []
    closes: List[float] = []
    for b in bars:
        factor = (b.adjusted_close / b.close) if (b.adjusted_close is not None and b.close > 0) else 1.0
        highs.append(float(b.high) * factor)
        lows.append(float(b.low) * factor)
        closes.append(float(b.close) * factor)
    return highs, lows, closes


def resolve_periods_per_year(
    explicit: Optional[int], interval: str, timestamps: Sequence[object]
) -> float:
    """Explicit request value > canonical interval factor > empirical inference."""
    if explicit is not None:
        return float(explicit)
    canonical = INTERVAL_PERIODS_PER_YEAR.get(interval.strip().lower())
    if canonical is not None:
        return float(canonical)
    from app.analytics.returns import infer_periods_per_year

    return infer_periods_per_year(timestamps, default=252.0)
