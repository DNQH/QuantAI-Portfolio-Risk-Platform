"""Institutional 10-Year Historical Portfolio Proof & Forward Scenario Forecast Engine (v3.0.0).

Combines:
  1. Risk-minimizing / Max-Sharpe / Equal-Weight portfolio optimization (SLSQP)
     with exact per-stock weight (%) and capital allocation (up to 1,000,000,000 in any currency).
  2. 10-Year historical portfolio backtest (CAGR, Volatility, Sharpe, Max Drawdown,
     Risk Reduction % vs. average single-stock volatility, Calendar-Year Returns).
  3. 5,000-path seeded Monte Carlo forward scenario projections (1Y, 3Y, 5Y) producing
     Bear (10th percentile), Base (50th percentile), and Bull (90th percentile) outcomes.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

import numpy as np
from pydantic import BaseModel, Field

from app.backtesting.engine import (
    CalendarYearReturn,
    PortfolioBacktestRequest,
    run_portfolio_backtest,
)
from app.core.models import OHLCVBar


DRIFT_SHRINKAGE = 0.75


class StockAllocationItem(BaseModel):
    instrument_id: str
    ticker: str
    company_name: str
    sector: str
    weight: float  # 0.0 to 1.0
    allocated_capital: float
    annualized_volatility: float


class ForwardScenarioHorizon(BaseModel):
    horizon_years: int
    bear_value: float  # 10th percentile
    base_value: float  # 50th percentile (median)
    bull_value: float  # 90th percentile
    bear_cagr: float
    base_cagr: float
    bull_cagr: float
    prob_positive: float  # Probability of ending above initial capital


class PortfolioSimulationRequest(BaseModel):
    instrument_ids: List[str] = Field(..., min_items=2, max_items=10)
    capital: float = Field(default=100000.0, gt=0.0, le=1_000_000_000.0)
    currency: str = Field(default="USD", min_length=3, max_length=5)
    allocation_method: Literal["min_variance", "max_sharpe", "equal_weight"] = "min_variance"
    rebalance_frequency: Literal["quarterly", "annually", "buy_and_hold"] = "quarterly"
    years: int = Field(default=10, ge=1, le=20)
    asset_series: Optional[Dict[str, List[OHLCVBar]]] = None


class PortfolioSimulationResponse(BaseModel):
    executed_at_utc: datetime
    currency: str
    initial_capital: float
    allocation_method: str
    rebalance_frequency: str
    start_date: str
    end_date: str
    years_covered: float
    observations: int
    # Optimal portfolio & risk reduction
    allocations: List[StockAllocationItem]
    portfolio_volatility: float
    weighted_avg_stock_volatility: float
    risk_reduction_pct: float
    diversification_ratio: float
    # 10Y Historical Proof
    final_portfolio_value: float
    total_return: float
    cagr: float
    sharpe_ratio: Optional[float]
    max_drawdown: float
    benchmark_final_value: float
    benchmark_cagr: float
    timestamps: List[str]
    equity_curve: List[float]
    benchmark_curve: List[float]
    calendar_year_returns: List[CalendarYearReturn]
    # Forward Scenario Projections (1Y, 3Y, 5Y)
    forward_scenarios: List[ForwardScenarioHorizon]
    excluded_tickers: List[Dict[str, str]] = Field(default_factory=list)
    pm_verdict: str
    assumptions: List[str]


def run_portfolio_10y_simulation(
    req: PortfolioSimulationRequest,
    metadata_map: Optional[Dict[str, Dict[str, str]]] = None,
) -> PortfolioSimulationResponse:
    bt_req = PortfolioBacktestRequest(
        instrument_ids=req.instrument_ids,
        asset_series=req.asset_series,
        years=req.years,
        allocation_method=req.allocation_method,
        rebalance_frequency=req.rebalance_frequency,
        initial_capital=req.capital,
    )
    bt = run_portfolio_backtest(bt_req)
    meta = metadata_map or {}

    # Individual stock volatilities measured on the SAME aligned evaluation window and with the
    # same annualisation factor as the portfolio volatility (previously each stock used its own
    # full, unaligned history and a hard-coded 252, which made the Diversification Ratio and
    # Risk Reduction % compare volatilities from different samples).
    indiv_vols: Dict[str, float] = dict(bt.asset_annualized_volatility)

    allocations: List[StockAllocationItem] = []
    weighted_avg_vol = 0.0
    for iid in bt.instrument_ids:
        w = float(bt.target_weights.get(iid, 0.0))
        v = indiv_vols.get(iid, bt.annualized_volatility)
        weighted_avg_vol += w * v
        ticker = iid.split(":", 1)[1] if ":" in iid else iid
        m = meta.get(iid, {})
        allocations.append(
            StockAllocationItem(
                instrument_id=iid,
                ticker=ticker,
                company_name=m.get("company_name", ticker),
                sector=m.get("sector", "Equity"),
                weight=round(w, 4),
                allocated_capital=round(w * req.capital, 2),
                annualized_volatility=round(v, 4),
            )
        )
    allocations.sort(key=lambda a: a.weight, reverse=True)

    port_vol = max(bt.annualized_volatility, 1e-6)
    div_ratio = weighted_avg_vol / port_vol if port_vol > 0 else 1.0
    risk_red = max(0.0, (weighted_avg_vol - port_vol) / weighted_avg_vol) if weighted_avg_vol > 0 else 0.0

    # Seeded Monte Carlo Forward Scenario Projections (1Y, 3Y, 5Y)
    # Conservative drift shrinkage: 0.75 * historical CAGR, capped to [-5%, +16%].
    shrunk_cagr = max(-0.05, min(0.16, bt.cagr * DRIFT_SHRINKAGE))
    sigma_ann = max(0.06, min(0.65, port_vol))
    # CAGR is already a GEOMETRIC (median) growth rate, i.e. it is net of volatility drag.
    # The continuously-compounded drift of log-wealth is therefore g = ln(1 + CAGR) and
    # W_T = W_0 * exp(g*T + sigma*sqrt(T)*Z). Subtracting 0.5*sigma^2 again (as the
    # arithmetic-drift GBM formula does) would double-count the drag and bias every
    # percentile down by ~sigma^2/2 per year.
    log_drift = math.log1p(shrunk_cagr)
    rng = np.random.default_rng(42)
    n_paths = 5000

    forward_scenarios: List[ForwardScenarioHorizon] = []
    for horizon in (1, 3, 5):
        z = rng.normal(0.0, 1.0, size=n_paths)
        growth = np.exp(log_drift * horizon + sigma_ann * math.sqrt(horizon) * z)
        end_vals = req.capital * growth
        bear_v = float(np.percentile(end_vals, 10))
        base_v = float(np.percentile(end_vals, 50))
        bull_v = float(np.percentile(end_vals, 90))
        prob_pos = float(np.mean(end_vals > req.capital))
        forward_scenarios.append(
            ForwardScenarioHorizon(
                horizon_years=horizon,
                bear_value=round(bear_v, 2),
                base_value=round(base_v, 2),
                bull_value=round(bull_v, 2),
                bear_cagr=round((bear_v / req.capital) ** (1.0 / horizon) - 1.0, 4),
                base_cagr=round((base_v / req.capital) ** (1.0 / horizon) - 1.0, 4),
                bull_cagr=round((bull_v / req.capital) ** (1.0 / horizon) - 1.0, 4),
                prob_positive=round(prob_pos, 4),
            )
        )

    top_str = ", ".join(f"{a.ticker} ({a.weight*100:.1f}%)" for a in allocations[:4])
    pm_verdict = (
        f"Portfolio Desk Assessment: Allocating {req.capital:,.0f} {req.currency} across {len(allocations)} equities "
        f"(core anchors: {top_str}) reduced portfolio volatility by {risk_red*100:.1f}% versus holding the same stocks "
        f"in isolation (Diversification Ratio: {div_ratio:.2f}x). Over the {bt.years_covered:.1f}-year historical window "
        f"({bt.start_date} to {bt.end_date}), the portfolio compounded at {bt.cagr*100:.1f}%/yr with a max drawdown of "
        f"{bt.max_drawdown*100:.1f}%."
    )

    return PortfolioSimulationResponse(
        executed_at_utc=datetime.now(timezone.utc),
        currency=req.currency.upper(),
        initial_capital=req.capital,
        allocation_method=req.allocation_method,
        rebalance_frequency=req.rebalance_frequency,
        start_date=bt.start_date,
        end_date=bt.end_date,
        years_covered=bt.years_covered,
        observations=bt.observations,
        allocations=allocations,
        portfolio_volatility=round(port_vol, 4),
        weighted_avg_stock_volatility=round(weighted_avg_vol, 4),
        risk_reduction_pct=round(risk_red, 4),
        diversification_ratio=round(div_ratio, 3),
        final_portfolio_value=bt.final_portfolio_value,
        total_return=bt.total_return,
        cagr=bt.cagr,
        sharpe_ratio=bt.sharpe_ratio,
        max_drawdown=bt.max_drawdown,
        benchmark_final_value=bt.benchmark_final_value,
        benchmark_cagr=bt.benchmark_cagr,
        timestamps=bt.timestamps,
        equity_curve=bt.equity_curve,
        benchmark_curve=bt.benchmark_curve,
        calendar_year_returns=bt.calendar_year_returns,
        forward_scenarios=forward_scenarios,
        pm_verdict=pm_verdict,
        assumptions=bt.assumptions + [
            "Forward 1Y/3Y/5Y scenarios run 5,000 seeded log-normal paths with log-drift ln(1 + 0.75 x historical CAGR, capped to [-5%, +16%]) and realized portfolio volatility; the median path compounds at the shrunk CAGR.",
            "Bear = 10th percentile, Base = Median (50th percentile), Bull = 90th percentile. Probabilistic simulations are not guaranteed future returns.",
        ],
    )
