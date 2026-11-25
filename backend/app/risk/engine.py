"""Phase 4: Financial Risk Management Engine.

Implements:
  - Historical VaR & CVaR (Expected Shortfall) at 95% and 99% confidence.
  - Parametric (Normal Variance-Covariance) VaR & CVaR.
  - Deterministic Seeded Monte Carlo VaR & CVaR.
  - Tracking Error & Information Ratio vs. benchmark.
  - Stress Testing & Scenario Analysis.
  - Currency Risk Exposure summary.

All VaR/CVaR loss numbers are reported as positive loss fractions (e.g. 0.025 = 2.5% loss)
and monetary loss amounts when portfolio_value is supplied.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel, Field, validator
from scipy.stats import norm

from app.analytics.returns import drawdown_analysis, sharpe_ratio, sortino_ratio


class VaRMethodResult(BaseModel):
    method: str
    confidence_level: float
    horizon_days: int
    var_pct: float
    cvar_pct: float
    var_amount: float
    cvar_amount: float


class StressScenarioResult(BaseModel):
    scenario_name: str
    shock_pct: float
    estimated_pnl: float
    post_shock_value: float
    rationale: str


class RiskAnalysisRequest(BaseModel):
    returns: List[float] = Field(..., min_items=10, description="Historical periodic (daily) portfolio returns")
    benchmark_returns: Optional[List[float]] = Field(default=None, description="Optional aligned benchmark returns")
    portfolio_value: float = Field(default=100000.0, gt=0.0)
    confidence_levels: List[float] = Field(default_factory=lambda: [0.95, 0.99])
    horizon_days: int = Field(default=1, ge=1, le=252)
    monte_carlo_simulations: int = Field(default=10000, ge=500, le=100000)
    monte_carlo_seed: int = Field(default=42)
    risk_free_rate_annual: float = Field(default=0.04)
    periods_per_year: int = Field(default=252, ge=1, le=365)
    currency_weights: Dict[str, float] = Field(default_factory=dict)

    @validator("confidence_levels")
    def _check_confidence_levels(cls, v: List[float]) -> List[float]:
        if not v:
            raise ValueError("At least one confidence level is required.")
        for alpha in v:
            if not (0.5 < alpha < 1.0):
                raise ValueError(f"Confidence level must be in (0.5, 1.0), got {alpha}.")
        return v


class RiskAnalysisResponse(BaseModel):
    computed_at_utc: datetime
    observations: int
    portfolio_value: float
    annualized_volatility: float
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown: float
    tracking_error: Optional[float]
    information_ratio: Optional[float]
    var_results: List[VaRMethodResult]
    stress_scenarios: List[StressScenarioResult]
    currency_exposure: Dict[str, float]
    assumptions: List[str]


def _expected_shortfall_from_sample(sample: np.ndarray, alpha: float) -> float:
    """Acerbi-Tasche (2002) empirical Expected Shortfall of the left tail (returned as a return, <= VaR return).

    ES = (1 / (n * a)) * [ sum_{i < k} x_(i) + (n * a - k) * x_(k) ],  a = 1 - alpha, k = floor(n * a)

    Unlike ``mean(x[x <= q])`` this estimator always averages exactly the worst (1 - alpha)
    probability mass (fractional weight on the boundary observation), so it is coherent and
    does not jump discontinuously with the quantile interpolation scheme.
    """
    x = np.sort(np.asarray(sample, dtype=float))
    n = x.size
    tail_mass = n * (1.0 - alpha)
    k = int(math.floor(tail_mass))
    k = min(k, n - 1)
    total = float(np.sum(x[:k])) + (tail_mass - k) * float(x[k])
    return total / tail_mass


def _historical_var_cvar(rets: np.ndarray, alpha: float, horizon: int) -> tuple[float, float]:
    # Horizon scaling consistent with the parametric method: drift scales with T,
    # the de-meaned shock scales with sqrt(T) (i.i.d. assumption). For T = 1 this is
    # exactly the raw empirical distribution.
    mu = float(np.mean(rets))
    scaled = mu * horizon + (rets - mu) * math.sqrt(horizon)
    q = float(np.quantile(scaled, 1.0 - alpha))
    es = _expected_shortfall_from_sample(scaled, alpha)
    return max(0.0, -q), max(0.0, -es)


def _parametric_var_cvar(rets: np.ndarray, alpha: float, horizon: int) -> tuple[float, float]:
    mu = float(np.mean(rets)) * horizon
    sigma = float(np.std(rets, ddof=1)) * math.sqrt(horizon)
    z = float(norm.ppf(alpha))
    # VaR_alpha = -(mu - z * sigma) ; returned as a positive loss fraction.
    var = max(0.0, -(mu - z * sigma))
    # Analytical Normal Expected Shortfall: ES = -mu + sigma * phi(z) / (1 - alpha)
    cvar = max(var, -(mu - sigma * float(norm.pdf(z)) / (1.0 - alpha)))
    return var, cvar


def _monte_carlo_var_cvar(
    rets: np.ndarray, alpha: float, horizon: int, n_sim: int, seed: int
) -> tuple[float, float]:
    mu = float(np.mean(rets)) * horizon
    sigma = float(np.std(rets, ddof=1)) * math.sqrt(horizon)
    rng = np.random.default_rng(seed)
    simulated = rng.normal(loc=mu, scale=sigma, size=n_sim)
    q = float(np.quantile(simulated, 1.0 - alpha))
    es = _expected_shortfall_from_sample(simulated, alpha)
    return max(0.0, -q), max(0.0, -es)


def run_risk_analysis(req: RiskAnalysisRequest) -> RiskAnalysisResponse:
    raw = np.asarray(req.returns, dtype=float)
    finite_mask = np.isfinite(raw)
    if req.benchmark_returns is not None:
        if len(req.benchmark_returns) != len(req.returns):
            raise ValueError("benchmark_returns must match length of returns.")
        bench_raw = np.asarray(req.benchmark_returns, dtype=float)
        finite_mask &= np.isfinite(bench_raw)
    if np.any(raw[finite_mask] < -1.0):
        raise ValueError("Simple returns cannot be below -100% (found a return < -1.0).")
    arr = raw[finite_mask]
    dropped = int(raw.size - arr.size)
    if arr.size < 10:
        raise ValueError(f"At least 10 finite return observations are required (got {arr.size}).")
    vol_ann = float(np.std(arr, ddof=1)) * math.sqrt(req.periods_per_year)
    sr = sharpe_ratio(arr.tolist(), req.risk_free_rate_annual, req.periods_per_year)
    sor = sortino_ratio(arr.tolist(), req.risk_free_rate_annual, req.periods_per_year)

    # Reconstruct wealth curve for drawdown
    wealth = [1.0]
    for r in arr:
        wealth.append(wealth[-1] * (1.0 + float(r)))
    dd = drawdown_analysis(wealth)

    tracking_err: Optional[float] = None
    info_ratio: Optional[float] = None
    if req.benchmark_returns is not None:
        active = arr - np.asarray(req.benchmark_returns, dtype=float)[finite_mask]
        te_val = float(np.std(active, ddof=1)) * math.sqrt(req.periods_per_year)
        tracking_err = te_val
        if te_val > 1e-12:
            info_ratio = (float(np.mean(active)) * req.periods_per_year) / te_val

    var_results: List[VaRMethodResult] = []
    for alpha in req.confidence_levels:
        for method_name, fn in (
            ("historical", lambda a=alpha: _historical_var_cvar(arr, a, req.horizon_days)),
            ("parametric_normal", lambda a=alpha: _parametric_var_cvar(arr, a, req.horizon_days)),
            (
                "monte_carlo_normal",
                lambda a=alpha: _monte_carlo_var_cvar(
                    arr, a, req.horizon_days, req.monte_carlo_simulations, req.monte_carlo_seed
                ),
            ),
        ):
            v_pct, cv_pct = fn()
            var_results.append(
                VaRMethodResult(
                    method=method_name,
                    confidence_level=alpha,
                    horizon_days=req.horizon_days,
                    var_pct=v_pct,
                    cvar_pct=max(v_pct, cv_pct),
                    var_amount=round(v_pct * req.portfolio_value, 2),
                    cvar_amount=round(max(v_pct, cv_pct) * req.portfolio_value, 2),
                )
            )

    stress_definitions = [
        ("2008 Global Financial Crisis Equity Shock", -0.35, "Severe systemic equity drawdown (-35%)."),
        ("2020 Pandemic Liquidity Shock", -0.22, "Rapid global equity sell-off (-22%)."),
        ("Inflation & +200bps Rate Shock", -0.12, "Duration & valuation multiple compression (-12%)."),
        ("Emerging Market FX Depreciation", -0.10, "Broad non-USD currency stress (-10%)."),
    ]
    stress_scenarios = [
        StressScenarioResult(
            scenario_name=name,
            shock_pct=shock,
            estimated_pnl=round(req.portfolio_value * shock, 2),
            post_shock_value=round(req.portfolio_value * (1.0 + shock), 2),
            rationale=rationale,
        )
        for name, shock, rationale in stress_definitions
    ]

    return RiskAnalysisResponse(
        computed_at_utc=datetime.now(timezone.utc),
        observations=int(len(arr)),
        portfolio_value=req.portfolio_value,
        annualized_volatility=vol_ann,
        sharpe_ratio=sr,
        sortino_ratio=sor,
        max_drawdown=dd.max_drawdown or 0.0,
        tracking_error=tracking_err,
        information_ratio=info_ratio,
        var_results=var_results,
        stress_scenarios=stress_scenarios,
        currency_exposure=req.currency_weights,
        assumptions=[
            "Historical VaR uses the empirical (linearly interpolated) return quantile; CVaR uses the Acerbi-Tasche tail-mass estimator.",
            "Multi-day horizons scale the mean by T and de-meaned shocks by sqrt(T) (i.i.d. assumption) for every method.",
            "Parametric VaR/CVaR assumes normally distributed i.i.d. returns and may underestimate fat-tail risk.",
            f"Monte Carlo VaR/CVaR runs {req.monte_carlo_simulations} deterministic seeded (seed={req.monte_carlo_seed}) normal draws.",
            "Stress scenarios apply transparent deterministic portfolio-level shocks for sensitivity illustration.",
        ]
        + ([f"Dropped {dropped} non-finite return observation(s) before analysis."] if dropped else []),
    )
