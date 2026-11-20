"""Descriptive statistics, correlation matrix, and annualized covariance matrix."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


def descriptive_statistics(returns: Sequence[Optional[float]]) -> Dict[str, Optional[float]]:
    """Compute sample mean, median, variance, std dev, unbiased skewness, and excess kurtosis."""
    valid = [r for r in returns if r is not None and math.isfinite(r)]
    n = len(valid)
    if n == 0:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "variance": None,
            "std_dev": None,
            "skewness": None,
            "excess_kurtosis": None,
        }

    arr = np.asarray(valid, dtype=float)
    mean_val = float(np.mean(arr))
    median_val = float(np.median(arr))
    var_val = float(np.var(arr, ddof=1)) if n >= 2 else None
    std_val = float(np.std(arr, ddof=1)) if n >= 2 else None
    skew_val = float(scipy_stats.skew(arr, bias=False)) if (n >= 3 and (std_val or 0) > 0) else None
    kurt_val = float(scipy_stats.kurtosis(arr, fisher=True, bias=False)) if (n >= 4 and (std_val or 0) > 0) else None

    return {
        "count": n,
        "mean": mean_val,
        "median": median_val,
        "variance": var_val,
        "std_dev": std_val,
        "skewness": skew_val,
        "excess_kurtosis": kurt_val,
    }


def correlation_and_covariance_matrices(
    asset_price_maps: Dict[str, Dict[str, float]],
    periods_per_year: int = 252,
) -> Tuple[List[str], int, Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """Align multi-asset prices by common dates (inner join), compute daily simple
    returns, and return (symbols, aligned_return_count, correlation_matrix, annualized_covariance_matrix).
    """
    if len(asset_price_maps) < 2:
        raise ValueError("At least two assets are required for correlation and covariance matrices.")

    df = pd.DataFrame(asset_price_maps).sort_index()
    aligned_prices = df.dropna(how="any")
    returns_df = aligned_prices.pct_change().dropna(how="any")

    if len(returns_df) < 2:
        raise ValueError(
            "Insufficient overlapping trading dates across assets (need at least 3 aligned price dates)."
        )

    corr_df = returns_df.corr(method="pearson")
    cov_df = returns_df.cov(ddof=1) * periods_per_year

    symbols = list(returns_df.columns)
    corr_dict = {
        r: {c: float(corr_df.loc[r, c]) for c in symbols}
        for r in symbols
    }
    cov_dict = {
        r: {c: float(cov_df.loc[r, c]) for c in symbols}
        for r in symbols
    }
    return symbols, int(len(returns_df)), corr_dict, cov_dict
