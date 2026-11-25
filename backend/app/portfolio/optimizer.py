"""Phase 3: Global Portfolio Management, MPT, CAPM, FX Attribution & Diverse-Risk Analyzer.

Implements:
  - Portfolio expected return, variance, volatility, Sharpe ratio, and risk contributions.
  - SciPy SLSQP Global Minimum Variance (GMV) and Maximum Sharpe optimization.
  - Efficient Frontier curve generation.
  - CAPM Beta, Market Risk Premium, and Expected Return.
  - Multi-currency FX return decomposition: (1 + r_local)(1 + r_fx) - 1.
  - Diverse-Risk Analyzer (up to 10 assets): Diversification Ratio (Choueifaty-Coignard),
    Risk Reduction %, pairwise correlation diagnostics, optimal risk-reducing subsets,
    and marginal volatility reduction for candidate additions.
  - SQLite persistence for user portfolios.
"""

from __future__ import annotations

import itertools
import math
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy.optimize import linprog, minimize

from app.analytics.statistics import aligned_simple_returns, ledoit_wolf_covariance
from app.core.database import DatabaseManager

# Condition number above which the sample covariance is treated as numerically singular.
ILL_CONDITIONED_THRESHOLD = 1e8

PORTFOLIO_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS portfolios (
    portfolio_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_currency TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    portfolio_id TEXT NOT NULL,
    instrument_id TEXT NOT NULL,
    weight REAL NOT NULL,
    currency TEXT NOT NULL,
    country TEXT NOT NULL,
    sector TEXT NOT NULL,
    PRIMARY KEY (portfolio_id, instrument_id)
);
"""


class PortfolioHoldingInput(BaseModel):
    instrument_id: str
    weight: float = Field(..., ge=0.0, le=1.0)
    currency: str = "USD"
    country: str = "United States"
    sector: str = "Unknown"


class PortfolioCreateRequest(BaseModel):
    portfolio_id: str
    name: str
    base_currency: str = "USD"
    holdings: List[PortfolioHoldingInput] = Field(..., min_items=1)


class PortfolioOptimizeRequest(BaseModel):
    asset_price_maps: Dict[str, Dict[str, float]] = Field(
        ..., description="Mapping of instrument_id -> {ISO_date: close_price}"
    )
    risk_free_rate_annual: float = Field(default=0.04)
    periods_per_year: int = Field(default=252, ge=1, le=365)
    min_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    max_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    frontier_points: int = Field(default=15, ge=5, le=50)
    transaction_cost_bps: float = Field(default=10.0, ge=0.0, le=500.0)
    covariance_method: Literal["auto", "sample", "ledoit_wolf"] = Field(
        default="auto",
        description="auto = sample covariance unless it is singular/ill-conditioned (then Ledoit-Wolf shrinkage).",
    )


class PortfolioPoint(BaseModel):
    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: Dict[str, float]
    risk_contributions_pct: Dict[str, float]


class PortfolioOptimizeResponse(BaseModel):
    symbols: List[str]
    aligned_return_observations: int
    computed_at_utc: datetime
    min_variance_portfolio: PortfolioPoint
    max_sharpe_portfolio: PortfolioPoint
    equal_weight_portfolio: PortfolioPoint
    efficient_frontier: List[PortfolioPoint]
    assumptions: List[str]
    covariance_estimator: str = "sample"
    shrinkage_intensity: Optional[float] = None
    optimizer_warnings: List[str] = Field(default_factory=list)


class CAPMRequest(BaseModel):
    asset_returns: List[float] = Field(..., min_items=5)
    market_returns: List[float] = Field(..., min_items=5)
    risk_free_rate_annual: float = Field(default=0.04)
    periods_per_year: int = Field(default=252, ge=1, le=365)


class CAPMResponse(BaseModel):
    beta: float
    market_expected_return_annual: float
    market_risk_premium_annual: float
    capm_expected_return_annual: float
    realized_asset_return_annual: float
    jensen_alpha_annual: float
    r_squared: float
    assumptions: List[str]


class FXAttributionRequest(BaseModel):
    local_return: float = Field(..., ge=-1.0, description="Local-currency asset return (>= -100%)")
    fx_return: float = Field(..., ge=-1.0, description="Return of the local currency vs. the base currency (>= -100%)")


class FXAttributionResponse(BaseModel):
    local_return: float
    fx_return: float
    interaction_term: float
    base_currency_return: float


# --- Diverse-Risk Models ---

class DiverseRiskRequest(BaseModel):
    asset_price_maps: Dict[str, Dict[str, float]] = Field(
        ..., description="2 to 10 selected stocks: instrument_id -> {ISO_date: close_price}"
    )
    candidate_price_maps: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Optional external candidate stocks to evaluate for marginal risk reduction",
    )
    periods_per_year: int = Field(default=252, ge=1, le=365)


class CorrelationPair(BaseModel):
    asset_a: str
    asset_b: str
    correlation: float


class SuggestedCombination(BaseModel):
    symbols: List[str]
    portfolio_volatility: float
    standalone_avg_volatility: float
    diversification_ratio: float
    risk_reduction_pct: float
    avg_pairwise_correlation: float
    optimal_weights: Dict[str, float]


class CandidateAdditionResult(BaseModel):
    symbol: str
    standalone_volatility: float
    avg_correlation_with_portfolio: float
    new_portfolio_volatility: float
    volatility_change_pct: float
    is_risk_reducing: bool


class DiverseRiskResponse(BaseModel):
    symbols: List[str]
    aligned_return_observations: int
    computed_at_utc: datetime
    is_risk_reducing: bool
    verdict: str
    verdict_summary: str
    equal_weight_volatility: float
    standalone_weighted_volatility: float
    diversification_ratio: float
    risk_reduction_pct: float
    gmv_volatility: float
    gmv_risk_reduction_pct: float
    avg_pairwise_correlation: float
    effective_num_bets: float
    highest_correlation_pairs: List[CorrelationPair]
    lowest_correlation_pairs: List[CorrelationPair]
    suggested_combinations: List[SuggestedCombination]
    candidate_additions: List[CandidateAdditionResult]
    assumptions: List[str]


def compute_portfolio_stats(
    weights: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float,
) -> Tuple[float, float, float, np.ndarray]:
    ret = float(weights @ mu)
    var = float(weights @ cov @ weights)
    vol = math.sqrt(max(var, 0.0))
    sharpe = (ret - rf) / vol if vol > 1e-12 else 0.0
    if vol > 1e-12:
        mrc = (cov @ weights) / vol
        rc_pct = (weights * mrc) / vol
    else:
        rc_pct = np.zeros_like(weights)
    return ret, vol, sharpe, rc_pct


def _pack_point(symbols: List[str], w: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float) -> PortfolioPoint:
    ret, vol, sharpe, rc_pct = compute_portfolio_stats(w, mu, cov, rf)
    return PortfolioPoint(
        expected_return=ret,
        volatility=vol,
        sharpe_ratio=sharpe,
        weights={s: round(float(val), 6) for s, val in zip(symbols, w)},
        risk_contributions_pct={s: round(float(val), 6) for s, val in zip(symbols, rc_pct)},
    )


def _solve_gmv(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]
    w0 = np.full(n, 1.0 / n, dtype=float)
    bounds = tuple((0.0, 1.0) for _ in range(n))
    res = minimize(
        lambda w: float(w @ cov @ w),
        w0,
        jac=lambda w: 2.0 * (cov @ w),
        method="SLSQP",
        bounds=bounds,
        constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
    )
    return _clean_weights(res.x, 0.0, 1.0) if res.success else w0


def _clean_weights(w: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Clip SLSQP round-off (e.g. -1e-12) back into the box and renormalise to sum 1."""
    w = np.clip(np.asarray(w, dtype=float), lo, hi)
    total = float(np.sum(w))
    return w / total if total > 0 else np.full_like(w, 1.0 / len(w))


def _feasible(w: np.ndarray, lo: float, hi: float, tol: float = 1e-6) -> bool:
    return bool(abs(float(np.sum(w)) - 1.0) < tol and np.all(w >= lo - tol) and np.all(w <= hi + tol))


def estimate_covariance(
    rets: pd.DataFrame, periods_per_year: float, method: str = "auto"
) -> Tuple[np.ndarray, str, Optional[float]]:
    """Annualised covariance with optional Ledoit-Wolf shrinkage.

    ``auto`` keeps the unbiased sample covariance unless T <= N or its condition number
    exceeds ILL_CONDITIONED_THRESHOLD, in which case it switches to Ledoit-Wolf so the
    optimiser never works on a singular matrix.
    """
    X = rets.to_numpy(dtype=float)
    t_obs, n_assets = X.shape
    sample = np.cov(X, rowvar=False, ddof=1).reshape(n_assets, n_assets)
    use_lw = method == "ledoit_wolf"
    if method == "auto":
        try:
            cond = float(np.linalg.cond(sample))
        except np.linalg.LinAlgError:
            cond = float("inf")
        use_lw = t_obs <= n_assets or not math.isfinite(cond) or cond > ILL_CONDITIONED_THRESHOLD
    if use_lw:
        lw, delta = ledoit_wolf_covariance(X)
        return lw * periods_per_year, "ledoit_wolf", delta
    return sample * periods_per_year, "sample", None


def _max_feasible_return(mu: np.ndarray, lo: float, hi: float) -> float:
    """Highest expected return attainable under sum(w)=1 and lo <= w_i <= hi (linear program)."""
    n = len(mu)
    res = linprog(-mu, A_eq=np.ones((1, n)), b_eq=[1.0], bounds=[(lo, hi)] * n, method="highs")
    if res.success:
        return float(-res.fun)
    return float(np.max(mu))


def optimize_portfolio(req: PortfolioOptimizeRequest) -> PortfolioOptimizeResponse:
    if len(req.asset_price_maps) < 2:
        raise ValueError("Portfolio optimization requires at least 2 assets.")
    if req.min_weight > req.max_weight:
        raise ValueError("min_weight must not exceed max_weight.")

    rets = aligned_simple_returns(req.asset_price_maps)
    if len(rets) < 5:
        raise ValueError("Need at least 6 aligned historical price dates across all assets.")

    symbols = list(rets.columns)
    n = len(symbols)
    if req.min_weight * n > 1.0 + 1e-9 or req.max_weight * n < 1.0 - 1e-9:
        raise ValueError("Infeasible weight bounds: ensure n*min_weight <= 1 <= n*max_weight.")

    warnings: List[str] = []
    mu = rets.mean().to_numpy(dtype=float) * req.periods_per_year
    cov, cov_label, shrink = estimate_covariance(rets, req.periods_per_year, req.covariance_method)
    if cov_label == "ledoit_wolf" and req.covariance_method == "auto":
        warnings.append(
            f"Sample covariance was singular/ill-conditioned ({len(rets)} observations, {n} assets); "
            f"switched to Ledoit-Wolf shrinkage (intensity {shrink:.3f})."
        )
    cov = cov + np.eye(n) * 1e-12  # numerical jitter only

    lo, hi = req.min_weight, req.max_weight
    bounds = tuple((lo, hi) for _ in range(n))
    sum_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones_like(w)}
    w0 = np.full(n, 1.0 / n, dtype=float)

    def variance(w: np.ndarray) -> float:
        return float(w @ cov @ w)

    def variance_grad(w: np.ndarray) -> np.ndarray:
        return 2.0 * (cov @ w)

    gmv_res = minimize(variance, w0, jac=variance_grad, method="SLSQP", bounds=bounds, constraints=[sum_constraint])
    if gmv_res.success and _feasible(gmv_res.x, lo, hi):
        w_gmv = _clean_weights(gmv_res.x, lo, hi)
    else:
        w_gmv = w0
        warnings.append(f"Minimum-variance optimisation did not converge ({gmv_res.message}); reporting equal weights.")

    def neg_sharpe(w: np.ndarray) -> float:
        _, v, s, _ = compute_portfolio_stats(w, mu, cov, req.risk_free_rate_annual)
        return -s if v > 1e-12 else 1e6

    # Multi-start (equal weight + GMV) to avoid SLSQP stalling at a flat starting point.
    best_ms: Optional[np.ndarray] = None
    best_val = float("inf")
    for start in (w0, w_gmv):
        ms_res = minimize(neg_sharpe, start, method="SLSQP", bounds=bounds, constraints=[sum_constraint])
        if ms_res.success and _feasible(ms_res.x, lo, hi) and float(ms_res.fun) < best_val:
            best_val = float(ms_res.fun)
            best_ms = _clean_weights(ms_res.x, lo, hi)
    if best_ms is None:
        w_ms = w0
        warnings.append("Maximum-Sharpe optimisation did not converge; reporting equal weights.")
    else:
        w_ms = best_ms

    # Efficient frontier: target returns span [GMV return, max return attainable under the weight bounds].
    gmv_ret = float(w_gmv @ mu)
    max_feasible_ret = _max_feasible_return(mu, lo, hi)
    frontier: List[PortfolioPoint] = []
    failed_targets = 0
    if max_feasible_ret - gmv_ret > 1e-10:
        targets = np.linspace(gmv_ret, max_feasible_ret, req.frontier_points)
        w_prev = w_gmv
        for target_r in targets:
            res = minimize(
                variance,
                w_prev,
                jac=variance_grad,
                method="SLSQP",
                bounds=bounds,
                constraints=[
                    sum_constraint,
                    {"type": "eq", "fun": lambda w, tr=target_r: float(w @ mu) - tr, "jac": lambda w: mu},
                ],
            )
            if res.success and _feasible(res.x, lo, hi) and abs(float(res.x @ mu) - target_r) < 1e-6 * max(1.0, abs(target_r)):
                w_prev = _clean_weights(res.x, lo, hi)
                frontier.append(_pack_point(symbols, w_prev, mu, cov, req.risk_free_rate_annual))
            else:
                failed_targets += 1
    if failed_targets:
        warnings.append(f"{failed_targets} efficient-frontier target(s) failed to converge and were omitted.")
    if not frontier:
        frontier.append(_pack_point(symbols, w_gmv, mu, cov, req.risk_free_rate_annual))

    return PortfolioOptimizeResponse(
        symbols=symbols,
        aligned_return_observations=int(len(rets)),
        computed_at_utc=datetime.now(timezone.utc),
        min_variance_portfolio=_pack_point(symbols, w_gmv, mu, cov, req.risk_free_rate_annual),
        max_sharpe_portfolio=_pack_point(symbols, w_ms, mu, cov, req.risk_free_rate_annual),
        equal_weight_portfolio=_pack_point(symbols, w0, mu, cov, req.risk_free_rate_annual),
        efficient_frontier=frontier,
        covariance_estimator=cov_label,
        shrinkage_intensity=shrink,
        optimizer_warnings=warnings,
        assumptions=[
            f"Mean-Variance Optimization uses sample mean returns and {'Ledoit-Wolf shrunk' if cov_label == 'ledoit_wolf' else 'sample'} covariance annualized by {req.periods_per_year}.",
            f"Constraints: sum(weights) = 1, bounds = [{lo:.2f}, {hi:.2f}], Rf = {req.risk_free_rate_annual:.2%}.",
            f"Efficient frontier spans target returns from the GMV portfolio ({gmv_ret:.2%}) to the maximum attainable under the bounds ({max_feasible_ret:.2%}).",
            f"Estimated turnover/rebalancing transaction cost assumption: {req.transaction_cost_bps:.1f} bps.",
            "Historical sample inputs do not guarantee future portfolio performance.",
        ]
        + warnings,
    )


def analyze_diverse_risk(req: DiverseRiskRequest) -> DiverseRiskResponse:
    """Evaluate whether a basket of 2–10 stocks achieves genuine diversification risk
    reduction, and recommend optimal risk-reducing subsets and candidate additions.
    """
    n_assets = len(req.asset_price_maps)
    if n_assets < 2 or n_assets > 10:
        raise ValueError(f"Diverse-Risk analysis requires between 2 and 10 stocks (received {n_assets}).")

    rets = aligned_simple_returns(req.asset_price_maps)
    if len(rets) < 5:
        raise ValueError("Need at least 6 overlapping trading dates across all selected stocks.")
    constant = [str(c) for c in rets.columns if float(rets[c].std(ddof=1)) == 0.0]
    if constant:
        raise ValueError(f"Correlation-based diversification is undefined for constant-price series: {', '.join(constant)}.")

    symbols = list(rets.columns)
    n = len(symbols)
    cov = rets.cov(ddof=1).to_numpy(dtype=float) * req.periods_per_year
    cov_reg = cov + np.eye(n) * 1e-10
    corr = rets.corr(method="pearson").to_numpy(dtype=float)
    vols = np.sqrt(np.maximum(np.diag(cov), 0.0))

    w_eq = np.full(n, 1.0 / n, dtype=float)
    port_vol = math.sqrt(max(float(w_eq @ cov @ w_eq), 0.0))
    standalone_avg_vol = float(w_eq @ vols)

    dr = (standalone_avg_vol / port_vol) if port_vol > 1e-12 else 1.0
    risk_red_pct = max(0.0, (1.0 - (port_vol / standalone_avg_vol)) * 100.0) if standalone_avg_vol > 1e-12 else 0.0

    # GMV achievable risk reduction within the same selected basket
    w_gmv = _solve_gmv(cov_reg)
    gmv_vol = math.sqrt(max(float(w_gmv @ cov @ w_gmv), 0.0))
    gmv_standalone = float(w_gmv @ vols)
    gmv_red_pct = max(0.0, (1.0 - (gmv_vol / gmv_standalone)) * 100.0) if gmv_standalone > 1e-12 else 0.0

    # Effective Number of Independent Bets via Risk Contributions
    if port_vol > 1e-12:
        rc_pct = (w_eq * (cov @ w_eq)) / (port_vol ** 2)
        enb = float(1.0 / np.sum(rc_pct ** 2)) if np.sum(rc_pct ** 2) > 1e-12 else 1.0
    else:
        enb = 1.0

    pairs: List[CorrelationPair] = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append(
                CorrelationPair(
                    asset_a=symbols[i],
                    asset_b=symbols[j],
                    correlation=round(float(corr[i, j]), 4),
                )
            )

    avg_corr = float(np.mean([p.correlation for p in pairs])) if pairs else 1.0
    sorted_pairs = sorted(pairs, key=lambda p: p.correlation)
    lowest_pairs = sorted_pairs[: min(5, len(sorted_pairs))]
    highest_pairs = list(reversed(sorted_pairs[-min(5, len(sorted_pairs)) :]))

    # Verdict classification
    if risk_red_pct >= 15.0 and avg_corr < 0.60:
        is_rr = True
        verdict = "STRONG_RISK_REDUCTION"
        verdict_summary = (
            f"YES — This {n}-stock basket achieves strong diversification, cutting volatility by "
            f"{risk_red_pct:.1f}% vs. standalone average risk (Diversification Ratio = {dr:.2f}, avg correlation = {avg_corr:.2f})."
        )
    elif risk_red_pct >= 5.0 and dr > 1.05:
        is_rr = True
        verdict = "MODERATE_RISK_REDUCTION"
        verdict_summary = (
            f"YES (Moderate) — This {n}-stock basket reduces volatility by {risk_red_pct:.1f}% "
            f"(DR = {dr:.2f}, avg correlation = {avg_corr:.2f}). Adding lower-correlation sectors or markets can lower risk further."
        )
    else:
        is_rr = False
        verdict = "WEAK_OR_CONCENTRATED"
        verdict_summary = (
            f"LIMITED — High correlation (avg = {avg_corr:.2f}) leaves only {risk_red_pct:.1f}% risk reduction "
            f"(DR = {dr:.2f}). Consider replacing redundant highly correlated stocks with uncorrelated markets or defensive sectors."
        )

    # Optimal Risk-Reducing Subsets (evaluate combinations of size k in {2, 3, 4} up to n)
    suggestions: List[SuggestedCombination] = []
    candidate_sizes = [k for k in (3, 4, 2) if k <= n]
    for k in candidate_sizes:
        for combo_idx in itertools.combinations(range(n), k):
            idx_arr = list(combo_idx)
            sub_cov = cov_reg[np.ix_(idx_arr, idx_arr)]
            sub_vols = vols[idx_arr]
            sub_w = _solve_gmv(sub_cov)
            sub_pvol = math.sqrt(max(float(sub_w @ cov[np.ix_(idx_arr, idx_arr)] @ sub_w), 0.0))
            sub_savol = float(sub_w @ sub_vols)
            sub_dr = (sub_savol / sub_pvol) if sub_pvol > 1e-12 else 1.0
            sub_red = max(0.0, (1.0 - sub_pvol / sub_savol) * 100.0) if sub_savol > 1e-12 else 0.0
            sub_corrs = [corr[idx_arr[a], idx_arr[b]] for a in range(k) for b in range(a + 1, k)]
            suggestions.append(
                SuggestedCombination(
                    symbols=[symbols[i] for i in idx_arr],
                    portfolio_volatility=round(sub_pvol, 6),
                    standalone_avg_volatility=round(sub_savol, 6),
                    diversification_ratio=round(sub_dr, 4),
                    risk_reduction_pct=round(sub_red, 2),
                    avg_pairwise_correlation=round(float(np.mean(sub_corrs)), 4),
                    optimal_weights={symbols[i]: round(float(w), 4) for i, w in zip(idx_arr, sub_w)},
                )
            )
    # Rank by lowest portfolio volatility, breaking ties by highest risk_reduction_pct
    suggestions.sort(key=lambda s: (s.portfolio_volatility, -s.risk_reduction_pct))
    top_suggestions = suggestions[:5]

    # Candidate Additions: measure marginal volatility impact of adding each external candidate
    candidate_results: List[CandidateAdditionResult] = []
    for cand_sym, cand_map in req.candidate_price_maps.items():
        if cand_sym in symbols or not cand_map:
            continue
        # Align PRICES first, then compute returns, so every return in the joined sample spans
        # the identical calendar interval for the basket and the candidate (computing the
        # candidate's returns on its own calendar mixes 1-day and multi-day returns).
        try:
            joined = aligned_simple_returns({**req.asset_price_maps, cand_sym: cand_map})
        except ValueError:
            continue
        if len(joined) < 6 or float(joined[cand_sym].std(ddof=1)) == 0.0:
            continue
        cand_ret = joined[cand_sym]
        sub_rets = joined[symbols]
        cand_vol = float(cand_ret.std(ddof=1)) * math.sqrt(req.periods_per_year)
        corrs_with_basket = [float(cand_ret.corr(sub_rets[s])) for s in symbols]
        avg_c = float(np.mean(corrs_with_basket))

        # New equal-weight portfolio with candidate added (weight 1/(n+1) each)
        new_cov = joined.cov(ddof=1).to_numpy(dtype=float) * req.periods_per_year
        w_new = np.full(n + 1, 1.0 / (n + 1), dtype=float)
        new_vol = math.sqrt(max(float(w_new @ new_cov @ w_new), 0.0))
        base_sub_cov = sub_rets.cov(ddof=1).to_numpy(dtype=float) * req.periods_per_year
        base_sub_vol = math.sqrt(max(float(w_eq @ base_sub_cov @ w_eq), 0.0))
        vol_change_pct = ((new_vol - base_sub_vol) / base_sub_vol) * 100.0 if base_sub_vol > 1e-12 else 0.0

        candidate_results.append(
            CandidateAdditionResult(
                symbol=cand_sym,
                standalone_volatility=round(cand_vol, 6),
                avg_correlation_with_portfolio=round(avg_c, 4),
                new_portfolio_volatility=round(new_vol, 6),
                volatility_change_pct=round(vol_change_pct, 2),
                is_risk_reducing=new_vol < base_sub_vol,
            )
        )
    candidate_results.sort(key=lambda c: c.volatility_change_pct)

    return DiverseRiskResponse(
        symbols=symbols,
        aligned_return_observations=int(len(rets)),
        computed_at_utc=datetime.now(timezone.utc),
        is_risk_reducing=is_rr,
        verdict=verdict,
        verdict_summary=verdict_summary,
        equal_weight_volatility=round(port_vol, 6),
        standalone_weighted_volatility=round(standalone_avg_vol, 6),
        diversification_ratio=round(dr, 4),
        risk_reduction_pct=round(risk_red_pct, 2),
        gmv_volatility=round(gmv_vol, 6),
        gmv_risk_reduction_pct=round(gmv_red_pct, 2),
        avg_pairwise_correlation=round(avg_corr, 4),
        effective_num_bets=round(enb, 2),
        highest_correlation_pairs=highest_pairs,
        lowest_correlation_pairs=lowest_pairs,
        suggested_combinations=top_suggestions,
        candidate_additions=candidate_results[:6],
        assumptions=[
            "Diversification Ratio (DR) = (Weighted Avg Standalone Volatility) / (Portfolio Volatility); DR > 1 indicates genuine risk reduction.",
            "Suggested combinations evaluate minimum-variance allocations across aligned historical daily returns.",
            "Historical correlations can rise during systemic market crises; quantitative suggestions are analytical tools, not investment advice.",
        ],
    )


def compute_capm(req: CAPMRequest) -> CAPMResponse:
    if len(req.asset_returns) != len(req.market_returns):
        raise ValueError("asset_returns and market_returns must have equal length.")
    ra = np.asarray(req.asset_returns, dtype=float)
    rm = np.asarray(req.market_returns, dtype=float)
    if not (np.all(np.isfinite(ra)) and np.all(np.isfinite(rm))):
        raise ValueError("asset_returns and market_returns must contain only finite values.")
    var_m = float(np.var(rm, ddof=1))
    if var_m <= 1e-14:
        raise ValueError("Market return variance is zero; CAPM beta is undefined.")

    cov_am = float(np.cov(ra, rm, ddof=1)[0, 1])
    beta = cov_am / var_m
    mkt_ann = float(np.mean(rm)) * req.periods_per_year
    asset_ann = float(np.mean(ra)) * req.periods_per_year
    mrp = mkt_ann - req.risk_free_rate_annual
    capm_exp = req.risk_free_rate_annual + beta * mrp
    alpha = asset_ann - capm_exp
    corr = float(np.corrcoef(ra, rm)[0, 1]) if np.std(ra, ddof=1) > 0 else 0.0

    return CAPMResponse(
        beta=beta,
        market_expected_return_annual=mkt_ann,
        market_risk_premium_annual=mrp,
        capm_expected_return_annual=capm_exp,
        realized_asset_return_annual=asset_ann,
        jensen_alpha_annual=alpha,
        r_squared=corr ** 2,
        assumptions=[
            "CAPM assumes single-factor linear sensitivity to market excess returns over the estimation sample.",
            f"Annualized using {req.periods_per_year} periods/year and Rf = {req.risk_free_rate_annual:.2%}.",
        ],
    )


def fx_return_attribution(req: FXAttributionRequest) -> FXAttributionResponse:
    interaction = req.local_return * req.fx_return
    base_ret = (1.0 + req.local_return) * (1.0 + req.fx_return) - 1.0
    return FXAttributionResponse(
        local_return=req.local_return,
        fx_return=req.fx_return,
        interaction_term=interaction,
        base_currency_return=base_ret,
    )


class PortfolioStore:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        with self._db.connect() as conn:
            conn.executescript(PORTFOLIO_SCHEMA_SQL)

    def save_portfolio(self, req: PortfolioCreateRequest) -> Dict[str, object]:
        total_w = sum(h.weight for h in req.holdings)
        if abs(total_w - 1.0) > 0.01:
            raise ValueError(f"Portfolio weights must sum to 1.0 (got {total_w:.4f}).")
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO portfolios (portfolio_id, name, base_currency, created_at) VALUES (?, ?, ?, ?)",
                (req.portfolio_id, req.name, req.base_currency.upper(), now_iso),
            )
            conn.execute("DELETE FROM portfolio_holdings WHERE portfolio_id = ?", (req.portfolio_id,))
            for h in req.holdings:
                conn.execute(
                    "INSERT INTO portfolio_holdings (portfolio_id, instrument_id, weight, currency, country, sector) VALUES (?, ?, ?, ?, ?, ?)",
                    (req.portfolio_id, h.instrument_id, h.weight, h.currency.upper(), h.country, h.sector),
                )
        return self.get_portfolio(req.portfolio_id)  # type: ignore

    def get_portfolio(self, portfolio_id: str) -> Optional[Dict[str, object]]:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM portfolios WHERE portfolio_id = ?", (portfolio_id,)).fetchone()
            if not row:
                return None
            holdings = [
                dict(r)
                for r in conn.execute(
                    "SELECT instrument_id, weight, currency, country, sector FROM portfolio_holdings WHERE portfolio_id = ?",
                    (portfolio_id,),
                ).fetchall()
            ]
        ccy_exp: Dict[str, float] = {}
        country_exp: Dict[str, float] = {}
        sector_exp: Dict[str, float] = {}
        for h in holdings:
            ccy_exp[h["currency"]] = round(ccy_exp.get(h["currency"], 0.0) + h["weight"], 6)
            country_exp[h["country"]] = round(country_exp.get(h["country"], 0.0) + h["weight"], 6)
            sector_exp[h["sector"]] = round(sector_exp.get(h["sector"], 0.0) + h["weight"], 6)

        return {
            "portfolio_id": row["portfolio_id"],
            "name": row["name"],
            "base_currency": row["base_currency"],
            "created_at": row["created_at"],
            "holdings": holdings,
            "exposures": {"currency": ccy_exp, "country": country_exp, "sector": sector_exp},
        }

    def list_portfolios(self) -> List[Dict[str, object]]:
        with self._db.connect() as conn:
            ids = [r["portfolio_id"] for r in conn.execute("SELECT portfolio_id FROM portfolios ORDER BY created_at DESC").fetchall()]
        return [p for pid in ids if (p := self.get_portfolio(pid)) is not None]
