"""Phase 3: Global Portfolio Management, Modern Portfolio Theory (MPT), CAPM & FX Attribution.

Implements:
  - Portfolio expected return, variance, volatility, Sharpe ratio, and risk contributions.
  - SciPy SLSQP Global Minimum Variance (GMV) and Maximum Sharpe optimization.
  - Efficient Frontier curve generation.
  - CAPM Beta, Market Risk Premium, and Expected Return.
  - Multi-currency FX return decomposition: (1 + r_local)(1 + r_fx) - 1.
  - SQLite persistence for user portfolios.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy.optimize import minimize

from app.core.database import DatabaseManager

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
    local_return: float = Field(..., description="Asset return in native currency, e.g. 0.10 for +10%")
    fx_return: float = Field(..., description="FX appreciation of asset currency vs base currency, e.g. -0.03")


class FXAttributionResponse(BaseModel):
    local_return: float
    fx_return: float
    interaction_term: float
    base_currency_return: float


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


def optimize_portfolio(req: PortfolioOptimizeRequest) -> PortfolioOptimizeResponse:
    if len(req.asset_price_maps) < 2:
        raise ValueError("Portfolio optimization requires at least 2 assets.")

    df = pd.DataFrame(req.asset_price_maps).sort_index().dropna(how="any")
    rets = df.pct_change().dropna(how="any")
    if len(rets) < 5:
        raise ValueError("Need at least 6 aligned historical price dates across all assets.")

    symbols = list(rets.columns)
    n = len(symbols)
    if req.min_weight * n > 1.0 + 1e-9 or req.max_weight * n < 1.0 - 1e-9:
        raise ValueError("Infeasible weight bounds: ensure n*min_weight <= 1 <= n*max_weight.")

    mu = rets.mean().to_numpy(dtype=float) * req.periods_per_year
    cov = rets.cov(ddof=1).to_numpy(dtype=float) * req.periods_per_year
    # Small ridge regularization for numerical stability on near-singular matrices
    cov = cov + np.eye(n) * 1e-10

    bounds = tuple((req.min_weight, req.max_weight) for _ in range(n))
    sum_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    w0 = np.full(n, 1.0 / n, dtype=float)

    # 1. Global Minimum Variance (GMV)
    gmv_res = minimize(
        lambda w: float(w @ cov @ w),
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=[sum_constraint],
    )
    w_gmv = gmv_res.x if gmv_res.success else w0

    # 2. Maximum Sharpe Ratio
    def neg_sharpe(w: np.ndarray) -> float:
        r, v, s, _ = compute_portfolio_stats(w, mu, cov, req.risk_free_rate_annual)
        return -s if v > 1e-12 else 1e6

    ms_res = minimize(
        neg_sharpe,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=[sum_constraint],
    )
    w_ms = ms_res.x if ms_res.success else w0

    # 3. Efficient Frontier
    gmv_ret = float(w_gmv @ mu)
    max_feasible_ret = float(np.max(mu))
    min_target = min(gmv_ret, max_feasible_ret)
    max_target = max(gmv_ret, max_feasible_ret)
    targets = np.linspace(min_target, max_target, req.frontier_points)

    frontier: List[PortfolioPoint] = []
    for target_r in targets:
        res = minimize(
            lambda w: float(w @ cov @ w),
            w_gmv,
            method="SLSQP",
            bounds=bounds,
            constraints=[
                sum_constraint,
                {"type": "eq", "fun": lambda w, tr=target_r: float(w @ mu) - tr},
            ],
        )
        if res.success:
            frontier.append(_pack_point(symbols, res.x, mu, cov, req.risk_free_rate_annual))

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
        assumptions=[
            f"Mean-Variance Optimization uses sample mean returns and sample covariance annualized by {req.periods_per_year}.",
            f"Constraints: sum(weights) = 1, bounds = [{req.min_weight:.2f}, {req.max_weight:.2f}], Rf = {req.risk_free_rate_annual:.2%}.",
            f"Estimated turnover/rebalancing transaction cost assumption: {req.transaction_cost_bps:.1f} bps (disclosed separately from gross MPT return).",
            "Historical sample inputs are subject to estimation error and do not guarantee future portfolio performance.",
        ],
    )


def compute_capm(req: CAPMRequest) -> CAPMResponse:
    if len(req.asset_returns) != len(req.market_returns):
        raise ValueError("asset_returns and market_returns must have equal length.")
    ra = np.asarray(req.asset_returns, dtype=float)
    rm = np.asarray(req.market_returns, dtype=float)
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
            "exposures": {
                "currency": ccy_exp,
                "country": country_exp,
                "sector": sector_exp,
            },
        }

    def list_portfolios(self) -> List[Dict[str, object]]:
        with self._db.connect() as conn:
            ids = [r["portfolio_id"] for r in conn.execute("SELECT portfolio_id FROM portfolios ORDER BY created_at DESC").fetchall()]
        return [p for pid in ids if (p := self.get_portfolio(pid)) is not None]
