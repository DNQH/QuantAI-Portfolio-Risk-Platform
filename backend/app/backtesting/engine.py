"""Phase 6: Transparent Quantitative Signals & Bias-Free Strategy Backtesting Engine.

Strict anti-bias guarantees:
  - Signals at bar t use ONLY information available up to and including bar t.
  - Trade execution occurs strictly at bar t+1 (next-bar lag) to prevent look-ahead bias.
  - Configurable transaction costs (commission bps) and slippage bps applied on every turnover event.
  - Always compared against a Buy-and-Hold benchmark over the identical evaluation window.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.analytics.indicators import macd, rate_of_change, rsi_wilder, sma
from app.analytics.returns import annualized_return, drawdown_analysis, rolling_volatility, sharpe_ratio, simple_returns
from app.core.models import OHLCVBar


class SignalDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class SignalRuleOutcome(BaseModel):
    rule_name: str
    direction: SignalDirection
    observed_value: Optional[float]
    condition: str
    rationale: str


class SignalsResponse(BaseModel):
    instrument_id: str
    evaluated_at_utc: datetime
    latest_bar_timestamp: datetime
    composite_signal: SignalDirection
    bullish_count: int
    bearish_count: int
    neutral_count: int
    rules: List[SignalRuleOutcome]
    disclaimer: str


class BacktestRequest(BaseModel):
    instrument_id: str
    bars: List[OHLCVBar] = Field(..., min_items=25)
    strategy: Literal["sma_crossover", "rsi_mean_reversion", "buy_and_hold"] = "sma_crossover"
    initial_capital: float = Field(default=100000.0, gt=0.0)
    fast_window: int = Field(default=10, ge=2, le=100)
    slow_window: int = Field(default=20, ge=5, le=250)
    rsi_period: int = Field(default=14, ge=2, le=50)
    rsi_oversold: float = Field(default=30.0, ge=5.0, le=45.0)
    rsi_overbought: float = Field(default=70.0, ge=55.0, le=95.0)
    commission_bps: float = Field(default=10.0, ge=0.0, le=500.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=500.0)
    periods_per_year: int = Field(default=252, ge=1, le=365)


class TradeRecord(BaseModel):
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    net_return_pct: float
    pnl_amount: float


class BacktestResponse(BaseModel):
    instrument_id: str
    strategy: str
    executed_at_utc: datetime
    initial_capital: float
    final_portfolio_value: float
    total_return: float
    annualized_return: Optional[float]
    max_drawdown: float
    sharpe_ratio: Optional[float]
    number_of_trades: int
    win_rate: Optional[float]
    total_transaction_costs: float
    benchmark_final_value: float
    benchmark_total_return: float
    timestamps: List[str]
    equity_curve: List[float]
    benchmark_curve: List[float]
    trades: List[TradeRecord]
    execution_assumptions: List[str]


def evaluate_quantitative_signals(instrument_id: str, bars: List[OHLCVBar]) -> SignalsResponse:
    ordered = sorted(bars, key=lambda b: b.timestamp)
    closes = [b.adjusted_close if b.adjusted_close is not None else b.close for b in ordered]

    rsi14 = rsi_wilder(closes, 14)[-1]
    macd_out = macd(closes, 12, 26, 9)
    macd_val = macd_out["macd"][-1]
    macd_sig = macd_out["signal"][-1]
    sma20 = sma(closes, 20)[-1]
    sma50 = sma(closes, 50)[-1]
    roc12 = rate_of_change(closes, 12)[-1]
    vol20 = rolling_volatility(simple_returns(closes), window=20)[-1]

    rules: List[SignalRuleOutcome] = []

    # 1. RSI 14
    if rsi14 is None:
        rules.append(SignalRuleOutcome(rule_name="RSI (14)", direction=SignalDirection.NEUTRAL, observed_value=None, condition="RSI < 30 bullish, > 70 bearish", rationale="Insufficient lookback (<15 bars)."))
    elif rsi14 < 30:
        rules.append(SignalRuleOutcome(rule_name="RSI (14)", direction=SignalDirection.BULLISH, observed_value=round(rsi14, 2), condition="RSI < 30", rationale="Oversold momentum regime."))
    elif rsi14 > 70:
        rules.append(SignalRuleOutcome(rule_name="RSI (14)", direction=SignalDirection.BEARISH, observed_value=round(rsi14, 2), condition="RSI > 70", rationale="Overbought momentum regime."))
    else:
        rules.append(SignalRuleOutcome(rule_name="RSI (14)", direction=SignalDirection.NEUTRAL, observed_value=round(rsi14, 2), condition="30 <= RSI <= 70", rationale="Balanced momentum zone."))

    # 2. MACD Crossover
    if macd_val is None or macd_sig is None:
        rules.append(SignalRuleOutcome(rule_name="MACD (12/26/9)", direction=SignalDirection.NEUTRAL, observed_value=None, condition="MACD > Signal bullish", rationale="Insufficient lookback (<34 bars)."))
    elif macd_val > macd_sig:
        rules.append(SignalRuleOutcome(rule_name="MACD (12/26/9)", direction=SignalDirection.BULLISH, observed_value=round(macd_val - macd_sig, 4), condition="MACD > Signal", rationale="Positive MACD histogram indicates upward momentum."))
    else:
        rules.append(SignalRuleOutcome(rule_name="MACD (12/26/9)", direction=SignalDirection.BEARISH, observed_value=round(macd_val - macd_sig, 4), condition="MACD <= Signal", rationale="Negative MACD histogram indicates downward momentum."))

    # 3. SMA 20 / 50 Trend
    if sma20 is None or sma50 is None:
        rules.append(SignalRuleOutcome(rule_name="SMA 20 / 50 Crossover", direction=SignalDirection.NEUTRAL, observed_value=None, condition="SMA20 > SMA50 bullish", rationale="Insufficient lookback (<50 bars)."))
    elif sma20 > sma50:
        rules.append(SignalRuleOutcome(rule_name="SMA 20 / 50 Crossover", direction=SignalDirection.BULLISH, observed_value=round(sma20 - sma50, 4), condition="SMA20 > SMA50", rationale="Short-term trend exceeds medium-term trend."))
    else:
        rules.append(SignalRuleOutcome(rule_name="SMA 20 / 50 Crossover", direction=SignalDirection.BEARISH, observed_value=round(sma20 - sma50, 4), condition="SMA20 <= SMA50", rationale="Short-term trend sits below medium-term trend."))

    # 4. 12-Bar Momentum (ROC)
    if roc12 is None:
        rules.append(SignalRuleOutcome(rule_name="Momentum ROC (12)", direction=SignalDirection.NEUTRAL, observed_value=None, condition="ROC > +2% bullish, < -2% bearish", rationale="Insufficient lookback."))
    elif roc12 > 2.0:
        rules.append(SignalRuleOutcome(rule_name="Momentum ROC (12)", direction=SignalDirection.BULLISH, observed_value=round(roc12, 2), condition="ROC > +2%", rationale="Positive 12-bar price velocity."))
    elif roc12 < -2.0:
        rules.append(SignalRuleOutcome(rule_name="Momentum ROC (12)", direction=SignalDirection.BEARISH, observed_value=round(roc12, 2), condition="ROC < -2%", rationale="Negative 12-bar price velocity."))
    else:
        rules.append(SignalRuleOutcome(rule_name="Momentum ROC (12)", direction=SignalDirection.NEUTRAL, observed_value=round(roc12, 2), condition="-2% <= ROC <= +2%", rationale="Range-bound momentum."))

    # 5. Historical Volatility Regime (informational neutral/caution)
    rules.append(
        SignalRuleOutcome(
            rule_name="20-Day Annualized Volatility",
            direction=SignalDirection.NEUTRAL,
            observed_value=round(vol20, 4) if vol20 is not None else None,
            condition="Contextual risk regime",
            rationale="Volatility informs position sizing rather than directional bias.",
        )
    )

    bull = sum(1 for r in rules if r.direction == SignalDirection.BULLISH)
    bear = sum(1 for r in rules if r.direction == SignalDirection.BEARISH)
    neut = sum(1 for r in rules if r.direction == SignalDirection.NEUTRAL)
    composite = (
        SignalDirection.BULLISH if bull > bear else (SignalDirection.BEARISH if bear > bull else SignalDirection.NEUTRAL)
    )

    return SignalsResponse(
        instrument_id=instrument_id,
        evaluated_at_utc=datetime.now(timezone.utc),
        latest_bar_timestamp=ordered[-1].timestamp,
        composite_signal=composite,
        bullish_count=bull,
        bearish_count=bear,
        neutral_count=neut,
        rules=rules,
        disclaimer="Rules-based quantitative signals are transparent analytical indicators, not investment advice.",
    )


def compute_strategy_target_positions(
    closes: List[float],
    strategy: str,
    fast_window: int = 10,
    slow_window: int = 20,
    rsi_period: int = 14,
    rsi_oversold: float = 30.0,
    rsi_overbought: float = 70.0,
) -> List[int]:
    """Generate causal target positions (0 = flat, 1 = long) using ONLY data <= t."""
    n = len(closes)
    if strategy == "buy_and_hold":
        return [1] * n

    if strategy == "sma_crossover":
        if fast_window >= slow_window:
            raise ValueError("fast_window must be strictly less than slow_window.")
        f_sma = sma(closes, fast_window)
        s_sma = sma(closes, slow_window)
        return [
            1 if (f is not None and s is not None and f > s) else 0
            for f, s in zip(f_sma, s_sma)
        ]

    if strategy == "rsi_mean_reversion":
        rsi_vals = rsi_wilder(closes, rsi_period)
        pos: List[int] = []
        current = 0
        for r in rsi_vals:
            if r is not None:
                if r < rsi_oversold:
                    current = 1
                elif r > rsi_overbought:
                    current = 0
            pos.append(current)
        return pos

    raise ValueError(f"Unsupported strategy: {strategy}")


def run_backtest(req: BacktestRequest) -> BacktestResponse:
    ordered = sorted(req.bars, key=lambda b: b.timestamp)
    timestamps = [b.timestamp.isoformat() for b in ordered]
    closes = [b.adjusted_close if b.adjusted_close is not None else b.close for b in ordered]
    n = len(closes)

    signals = compute_strategy_target_positions(
        closes=closes,
        strategy=req.strategy,
        fast_window=req.fast_window,
        slow_window=req.slow_window,
        rsi_period=req.rsi_period,
        rsi_oversold=req.rsi_oversold,
        rsi_overbought=req.rsi_overbought,
    )

    cost_rate = (req.commission_bps + req.slippage_bps) / 10000.0
    cash = req.initial_capital
    shares = 0.0
    total_costs = 0.0
    equity_curve: List[float] = [req.initial_capital]
    trades: List[TradeRecord] = []

    entry_ts: Optional[str] = None
    entry_price: Optional[float] = None
    entry_capital: Optional[float] = None

    # Execute signal from bar t-1 strictly at bar t (T+1 execution -> zero look-ahead bias)
    for t in range(1, n):
        target_pos = signals[t - 1]
        px = closes[t]

        if target_pos == 1 and shares == 0.0:
            exec_px = px * (1.0 + req.slippage_bps / 10000.0)
            fee = cash * (req.commission_bps / 10000.0)
            investable = cash - fee
            shares = investable / exec_px
            total_costs += fee + (investable * (req.slippage_bps / 10000.0))
            entry_capital = cash
            cash = 0.0
            entry_ts = timestamps[t]
            entry_price = exec_px
        elif target_pos == 0 and shares > 0.0:
            exec_px = px * (1.0 - req.slippage_bps / 10000.0)
            gross = shares * exec_px
            fee = gross * (req.commission_bps / 10000.0)
            net_proceeds = gross - fee
            total_costs += fee + (shares * px * (req.slippage_bps / 10000.0))
            if entry_ts is not None and entry_price is not None and entry_capital is not None:
                pnl = net_proceeds - entry_capital
                trades.append(
                    TradeRecord(
                        entry_timestamp=entry_ts,
                        exit_timestamp=timestamps[t],
                        entry_price=round(entry_price, 4),
                        exit_price=round(exec_px, 4),
                        net_return_pct=round((pnl / entry_capital) * 100.0, 4),
                        pnl_amount=round(pnl, 2),
                    )
                )
            cash = net_proceeds
            shares = 0.0
            entry_ts = None
            entry_price = None
            entry_capital = None

        equity_curve.append(round(cash + shares * px, 4))

    # Buy-and-Hold benchmark over identical window (with single entry fee/slippage)
    bh_start_cost = req.initial_capital * cost_rate
    bh_shares = (req.initial_capital - bh_start_cost) / closes[0]
    benchmark_curve = [round(bh_shares * p, 4) for p in closes]

    final_val = equity_curve[-1]
    total_ret = (final_val - req.initial_capital) / req.initial_capital
    ann_ret = annualized_return(equity_curve, req.periods_per_year)
    dd = drawdown_analysis(equity_curve)
    eq_rets = simple_returns(equity_curve)
    sr = sharpe_ratio(eq_rets, 0.0, req.periods_per_year)
    win_rate = (
        sum(1 for tr in trades if tr.pnl_amount > 0) / len(trades)
        if trades
        else None
    )

    return BacktestResponse(
        instrument_id=req.instrument_id,
        strategy=req.strategy,
        executed_at_utc=datetime.now(timezone.utc),
        initial_capital=req.initial_capital,
        final_portfolio_value=round(final_val, 2),
        total_return=total_ret,
        annualized_return=ann_ret,
        max_drawdown=dd.max_drawdown or 0.0,
        sharpe_ratio=sr,
        number_of_trades=len(trades),
        win_rate=win_rate,
        total_transaction_costs=round(total_costs, 2),
        benchmark_final_value=round(benchmark_curve[-1], 2),
        benchmark_total_return=(benchmark_curve[-1] - req.initial_capital) / req.initial_capital,
        timestamps=timestamps,
        equity_curve=equity_curve,
        benchmark_curve=benchmark_curve,
        trades=trades,
        execution_assumptions=[
            "Strict T+1 execution: signals computed from bar t-1 close execute at bar t to eliminate look-ahead bias.",
            f"Transaction costs: {req.commission_bps:.1f} bps commission + {req.slippage_bps:.1f} bps slippage per turnover.",
            "Long-only fully invested / cash allocation without leverage or short-selling margin assumptions.",
            "Historical backtest results are hypothetical simulations and do NOT guarantee future returns.",
        ],
    )


# --- v2.0.0: 10-Year Multi-Stock Portfolio Backtester ---

class CalendarYearReturn(BaseModel):
    year: int
    portfolio_return: float
    benchmark_return: float


class PortfolioBacktestRequest(BaseModel):
    instrument_ids: List[str] = Field(..., min_items=2, max_items=10)
    asset_series: Optional[Dict[str, List[OHLCVBar]]] = None
    years: int = Field(default=10, ge=1, le=20)
    allocation_method: Literal["equal_weight", "min_variance", "max_sharpe"] = "equal_weight"
    rebalance_frequency: Literal["quarterly", "annually", "buy_and_hold"] = "quarterly"
    initial_capital: float = Field(default=100000.0, gt=0.0)
    commission_bps: float = Field(default=10.0, ge=0.0, le=500.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=500.0)
    risk_free_rate_annual: float = Field(default=0.04)


class PortfolioBacktestResponse(BaseModel):
    instrument_ids: List[str]
    allocation_method: str
    rebalance_frequency: str
    executed_at_utc: datetime
    start_date: str
    end_date: str
    years_covered: float
    observations: int
    initial_capital: float
    final_portfolio_value: float
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: Optional[float]
    max_drawdown: float
    rebalance_count: int
    total_transaction_costs: float
    benchmark_final_value: float
    benchmark_total_return: float
    benchmark_cagr: float
    target_weights: Dict[str, float]
    timestamps: List[str]
    equity_curve: List[float]
    benchmark_curve: List[float]
    calendar_year_returns: List[CalendarYearReturn]
    assumptions: List[str]


def _compute_portfolio_weights(
    returns_matrix: "np.ndarray", method: str, rf_annual: float
) -> "np.ndarray":
    import numpy as np
    from scipy.optimize import minimize

    n = returns_matrix.shape[1]
    eq = np.full(n, 1.0 / n)
    if method == "equal_weight" or returns_matrix.shape[0] < 30:
        return eq

    cov = np.cov(returns_matrix, rowvar=False) * 252.0
    if cov.ndim == 0:
        return eq
    cov = cov + np.eye(n) * 1e-6
    mu = np.mean(returns_matrix, axis=0) * 252.0
    bounds = tuple((0.02, 0.60) for _ in range(n))
    constraints = ({"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)},)

    if method == "min_variance":
        res = minimize(lambda w: float(w @ cov @ w), eq, method="SLSQP", bounds=bounds, constraints=constraints)
        return res.x if res.success else eq

    if method == "max_sharpe":
        def neg_sr(w):
            vol = math.sqrt(max(float(w @ cov @ w), 1e-12))
            return -(float(w @ mu) - rf_annual) / vol
        res = minimize(neg_sr, eq, method="SLSQP", bounds=bounds, constraints=constraints)
        return res.x if res.success else eq

    return eq


def run_portfolio_backtest(req: PortfolioBacktestRequest) -> PortfolioBacktestResponse:
    import numpy as np

    if not req.asset_series or len(req.asset_series) < 2:
        raise ValueError("Portfolio backtest requires aligned OHLCV price series for at least 2 stocks.")

    # Align on common calendar dates (YYYY-MM-DD)
    price_maps: Dict[str, Dict[str, float]] = {}
    ordered_ids = [iid for iid in req.instrument_ids if iid in req.asset_series and len(req.asset_series[iid]) >= 20]
    if len(ordered_ids) < 2:
        raise ValueError("At least 2 selected stocks must have >= 20 valid historical bars.")

    for iid in ordered_ids:
        bars = sorted(req.asset_series[iid], key=lambda b: b.timestamp)
        pm: Dict[str, float] = {}
        for b in bars:
            px = b.adjusted_close if b.adjusted_close is not None else b.close
            if px > 0:
                pm[b.timestamp.strftime("%Y-%m-%d")] = float(px)
        price_maps[iid] = pm

    common_dates = sorted(set.intersection(*(set(m.keys()) for m in price_maps.values())))
    if len(common_dates) < 30:
        raise ValueError(
            f"Selected stocks share only {len(common_dates)} overlapping trading days (minimum 30 required)."
        )

    # Trim to requested lookback window (default 10 years ~ 2520 trading days)
    max_bars = int(req.years * 252) + 1
    if len(common_dates) > max_bars:
        common_dates = common_dates[-max_bars:]

    prices = np.array([[price_maps[iid][d] for iid in ordered_ids] for d in common_dates], dtype=float)
    asset_rets = np.diff(prices, axis=0) / prices[:-1]
    n_days, n_assets = asset_rets.shape

    # Compute target weights using initial 252-day (or first 25% of sample) estimation window to avoid full-sample look-ahead
    calib_len = min(252, max(30, n_days // 4))
    target_w = _compute_portfolio_weights(asset_rets[:calib_len], req.allocation_method, req.risk_free_rate_annual)
    target_w = target_w / np.sum(target_w)

    cost_rate = (req.commission_bps + req.slippage_bps) / 10000.0
    rebal_step = 63 if req.rebalance_frequency == "quarterly" else (252 if req.rebalance_frequency == "annually" else 10**9)

    port_val = req.initial_capital
    holdings = port_val * target_w
    bench_holdings = req.initial_capital * np.full(n_assets, 1.0 / n_assets)

    equity_curve: List[float] = [round(port_val, 2)]
    bench_curve: List[float] = [round(req.initial_capital, 2)]
    port_daily_rets: List[float] = []
    rebal_count = 0
    total_costs = 0.0

    for t in range(n_days):
        prev_val = float(np.sum(holdings))
        holdings = holdings * (1.0 + asset_rets[t])
        bench_holdings = bench_holdings * (1.0 + asset_rets[t])

        cur_val = float(np.sum(holdings))
        if (t + 1) % rebal_step == 0 and t < n_days - 1:
            desired = cur_val * target_w
            turnover = float(np.sum(np.abs(desired - holdings))) * 0.5
            cost = turnover * cost_rate
            total_costs += cost
            cur_val = max(0.01, cur_val - cost)
            holdings = cur_val * target_w
            rebal_count += 1

        port_daily_rets.append((cur_val - prev_val) / prev_val if prev_val > 0 else 0.0)
        equity_curve.append(round(cur_val, 2))
        bench_curve.append(round(float(np.sum(bench_holdings)), 2))

    # Downsample curves slightly for smooth charting if > 400 points (keeping exact start/end)
    final_val = equity_curve[-1]
    bench_final = bench_curve[-1]
    years_cov = max(0.08, n_days / 252.0)
    tot_ret = (final_val / req.initial_capital) - 1.0
    bench_tot_ret = (bench_final / req.initial_capital) - 1.0
    cagr = (final_val / req.initial_capital) ** (1.0 / years_cov) - 1.0 if final_val > 0 else -1.0
    bench_cagr = (bench_final / req.initial_capital) ** (1.0 / years_cov) - 1.0 if bench_final > 0 else -1.0
    ann_vol = float(np.std(port_daily_rets, ddof=1)) * math.sqrt(252.0) if len(port_daily_rets) > 1 else 0.0
    sr = sharpe_ratio(port_daily_rets, req.risk_free_rate_annual, 252)
    dd = drawdown_analysis(equity_curve)

    # Calendar-year breakdown
    by_year: Dict[int, List[int]] = {}
    for idx, d in enumerate(common_dates):
        yr = int(d[:4])
        by_year.setdefault(yr, []).append(idx)
    cal_returns: List[CalendarYearReturn] = []
    for yr in sorted(by_year.keys()):
        idxs = by_year[yr]
        if len(idxs) < 2:
            continue
        i0, i1 = idxs[0], idxs[-1]
        p_r = (equity_curve[i1] / equity_curve[i0]) - 1.0 if equity_curve[i0] > 0 else 0.0
        b_r = (bench_curve[i1] / bench_curve[i0]) - 1.0 if bench_curve[i0] > 0 else 0.0
        cal_returns.append(CalendarYearReturn(year=yr, portfolio_return=round(p_r, 4), benchmark_return=round(b_r, 4)))

    # Keep <= 300 chart points for fast frontend rendering while preserving exact endpoints
    if len(common_dates) > 300:
        step = max(1, len(common_dates) // 260)
        sel = list(range(0, len(common_dates), step))
        if sel[-1] != len(common_dates) - 1:
            sel.append(len(common_dates) - 1)
        out_ts = [common_dates[i] for i in sel]
        out_eq = [equity_curve[i] for i in sel]
        out_bm = [bench_curve[i] for i in sel]
    else:
        out_ts = common_dates
        out_eq = equity_curve
        out_bm = bench_curve

    return PortfolioBacktestResponse(
        instrument_ids=ordered_ids,
        allocation_method=req.allocation_method,
        rebalance_frequency=req.rebalance_frequency,
        executed_at_utc=datetime.now(timezone.utc),
        start_date=common_dates[0],
        end_date=common_dates[-1],
        years_covered=round(years_cov, 2),
        observations=len(common_dates),
        initial_capital=req.initial_capital,
        final_portfolio_value=final_val,
        total_return=round(tot_ret, 4),
        cagr=round(cagr, 4),
        annualized_volatility=round(ann_vol, 4),
        sharpe_ratio=round(sr, 3) if sr is not None else None,
        max_drawdown=round(dd.max_drawdown or 0.0, 4),
        rebalance_count=rebal_count,
        total_transaction_costs=round(total_costs, 2),
        benchmark_final_value=bench_final,
        benchmark_total_return=round(bench_tot_ret, 4),
        benchmark_cagr=round(bench_cagr, 4),
        target_weights={iid: round(float(w), 4) for iid, w in zip(ordered_ids, target_w)},
        timestamps=out_ts,
        equity_curve=out_eq,
        benchmark_curve=out_bm,
        calendar_year_returns=cal_returns,
        assumptions=[
            f"Aligned {len(ordered_ids)} portfolio stocks on {len(common_dates)} overlapping trading days ({common_dates[0]} to {common_dates[-1]}, {years_cov:.1f} years).",
            f"Target weights calibrated on the initial {calib_len}-day window ({req.allocation_method}) with {req.rebalance_frequency} rebalancing.",
            f"Transaction costs ({req.commission_bps:.1f} bps commission + {req.slippage_bps:.1f} bps slippage) deducted on every rebalance turnover.",
            "Benchmark is an Equal-Weight Buy-and-Hold basket of the identical selected stocks.",
        ],
    )
