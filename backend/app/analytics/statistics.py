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


def aligned_simple_returns(
    asset_price_maps: Dict[str, Dict[str, float]],
    min_assets: int = 2,
) -> pd.DataFrame:
    """Inner-join multi-asset close prices on common dates and return simple returns.

    Rejects non-finite and non-positive prices explicitly (a zero or negative close
    would otherwise produce +/-inf returns that silently poison the covariance).
    """
    if len(asset_price_maps) < min_assets:
        raise ValueError(f"At least {min_assets} assets are required.")
    for sym, series in asset_price_maps.items():
        if not series:
            raise ValueError(f"Price series for {sym} is empty.")
        bad = [d for d, px in series.items() if px is None or not math.isfinite(float(px)) or float(px) <= 0.0]
        if bad:
            raise ValueError(
                f"Price series for {sym} contains {len(bad)} non-finite or non-positive price(s) (e.g. {bad[0]})."
            )
    df = pd.DataFrame(asset_price_maps).sort_index()
    aligned_prices = df.dropna(how="any")
    return aligned_prices.pct_change().dropna(how="any")


def ledoit_wolf_covariance(returns: np.ndarray) -> Tuple[np.ndarray, float]:
    """Ledoit-Wolf (2004) shrinkage of the sample covariance towards a scaled identity.

    Sigma_LW = (1 - delta) * S + delta * mu * I, with S the (1/T) sample covariance of the
    demeaned returns, mu = trace(S) / N, and delta the analytically optimal intensity
    (same estimator as ``sklearn.covariance.ledoit_wolf``). The result is always
    symmetric positive-definite (when returns are not all constant), even if T <= N.

    Returns (per-period covariance, shrinkage intensity delta in [0, 1]).
    """
    X = np.asarray(returns, dtype=float)
    if X.ndim != 2 or X.shape[0] < 2:
        raise ValueError("Ledoit-Wolf shrinkage requires a 2-D (T x N) return matrix with T >= 2.")
    t_obs, n_assets = X.shape
    X = X - X.mean(axis=0)
    X2 = X ** 2
    emp_cov = (X.T @ X) / t_obs
    emp_cov_trace = X2.sum(axis=0) / t_obs
    mu = float(emp_cov_trace.sum()) / n_assets
    beta_ = float(np.sum(X2.T @ X2))
    delta_ = float(np.sum((X.T @ X) ** 2)) / (t_obs ** 2)
    beta = (beta_ / t_obs - delta_) / (n_assets * t_obs)
    delta = (delta_ - 2.0 * mu * float(emp_cov_trace.sum()) + n_assets * mu ** 2) / n_assets
    beta = min(beta, delta)
    shrinkage = 0.0 if delta <= 0.0 else max(0.0, min(1.0, beta / delta))
    shrunk = (1.0 - shrinkage) * emp_cov + shrinkage * mu * np.eye(n_assets)
    return shrunk, float(shrinkage)


def correlation_and_covariance_matrices(
    asset_price_maps: Dict[str, Dict[str, float]],
    periods_per_year: int = 252,
) -> Tuple[List[str], int, Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """Align multi-asset prices by common dates (inner join), compute daily simple
    returns, and return (symbols, aligned_return_count, correlation_matrix, annualized_covariance_matrix).
    """
    if len(asset_price_maps) < 2:
        raise ValueError("At least two assets are required for correlation and covariance matrices.")

    returns_df = aligned_simple_returns(asset_price_maps)

    if len(returns_df) < 2:
        raise ValueError(
            "Insufficient overlapping trading dates across assets (need at least 3 aligned price dates)."
        )

    zero_var = [c for c in returns_df.columns if float(returns_df[c].std(ddof=1)) == 0.0]
    if zero_var:
        raise ValueError(f"Correlation is undefined for constant-price series: {', '.join(map(str, zero_var))}.")

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
