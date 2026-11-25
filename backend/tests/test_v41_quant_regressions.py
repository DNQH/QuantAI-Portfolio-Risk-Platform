"""v4.1.0 regression tests for every quantitative / robustness fix.

All inputs are deterministic synthetic data with closed-form expected answers.
"""

from __future__ import annotations

import math
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List

import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy.stats import norm

from app import __version__
from app.analytics.engine import SingleAssetAnalyticsRequest, run_single_asset_analytics
from app.analytics.returns import (
    drawdown_analysis,
    infer_periods_per_year,
    rolling_volatility,
    sharpe_ratio,
    sortino_ratio,
)
from app.analytics.statistics import ledoit_wolf_covariance
from app.backtesting.engine import (
    BacktestRequest,
    PortfolioBacktestRequest,
    run_backtest,
    run_portfolio_backtest,
)
from app.core.config import Settings
from app.core.models import OHLCVBar
from app.main import create_app
from app.portfolio.advisor import DiverseRiskAdvisorRequest, ask_diverse_risk_advisor
from app.portfolio.optimizer import (
    DiverseRiskRequest,
    PortfolioOptimizeRequest,
    analyze_diverse_risk,
    optimize_portfolio,
)
from app.portfolio.simulator import DRIFT_SHRINKAGE, PortfolioSimulationRequest, run_portfolio_10y_simulation
from app.risk.bankruptcy import (
    BankruptcyRequest,
    FinancialStatementInputs,
    _merton_distance_to_default,
    run_bankruptcy_pipeline,
)
from app.risk.engine import RiskAnalysisRequest, _expected_shortfall_from_sample, run_risk_analysis


# ----------------------------------------------------------------------------- helpers

def _weekdays(start: date, n: int) -> List[date]:
    out: List[date] = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _bars_from_closes(dates: List[date], closes: List[float]) -> List[OHLCVBar]:
    return [
        OHLCVBar(
            timestamp=datetime(d.year, d.month, d.day, 16, tzinfo=timezone.utc),
            open=c,
            high=c * 1.01,
            low=c * 0.99,
            close=c,
            adjusted_close=c,
            volume=1000,
        )
        for d, c in zip(dates, closes)
    ]


def _exact_moment_sample(mu: float, sigma: float, n: int = 400, seed: int = 7) -> np.ndarray:
    """Sample whose SAMPLE mean is exactly mu and sample std (ddof=1) exactly sigma."""
    z = np.random.default_rng(seed).normal(size=n)
    z = (z - z.mean()) / z.std(ddof=1)
    return mu + sigma * z


@pytest.fixture()
def client() -> TestClient:
    settings = Settings(database_path=":memory:", enable_yfinance_fallback=False, gemini_api_key=None)
    return TestClient(create_app(settings=settings))


# ------------------------------------------------------------------- VaR / CVaR (risk)

@pytest.mark.parametrize("alpha", [0.95, 0.99])
@pytest.mark.parametrize("horizon", [1, 10])
def test_parametric_var_cvar_matches_normal_closed_form(alpha: float, horizon: int) -> None:
    mu, sigma = 0.0004, 0.012
    rets = _exact_moment_sample(mu, sigma)
    res = run_risk_analysis(
        RiskAnalysisRequest(returns=rets.tolist(), confidence_levels=[alpha], horizon_days=horizon)
    )
    row = next(r for r in res.var_results if r.method == "parametric_normal")
    z = norm.ppf(alpha)
    exp_var = z * sigma * math.sqrt(horizon) - mu * horizon
    exp_es = sigma * math.sqrt(horizon) * norm.pdf(z) / (1 - alpha) - mu * horizon
    assert row.var_pct == pytest.approx(exp_var, rel=1e-10)
    assert row.cvar_pct == pytest.approx(exp_es, rel=1e-10)
    assert row.var_amount == pytest.approx(round(exp_var * 100000.0, 2), abs=0.01)


def test_historical_es_uses_acerbi_tasche_tail_mass() -> None:
    # 20 observations: worst two are -10% and -5%.
    sample = np.array([-0.10, -0.05] + [0.01 * k for k in range(18)])
    # alpha = 0.95 -> tail mass n*(1-a) = 1 -> ES = worst observation exactly.
    assert _expected_shortfall_from_sample(sample, 0.95) == pytest.approx(-0.10)
    # alpha = 0.90 -> tail mass 2 -> mean of the two worst.
    assert _expected_shortfall_from_sample(sample, 0.90) == pytest.approx(-0.075)
    # alpha = 0.925 -> tail mass 1.5 -> (x1 + 0.5 x2) / 1.5
    assert _expected_shortfall_from_sample(sample, 0.925) == pytest.approx((-0.10 - 0.025) / 1.5)


def test_historical_var_horizon_scaling_consistent_with_parametric() -> None:
    rets = _exact_moment_sample(0.001, 0.02, n=500, seed=3)
    one = run_risk_analysis(RiskAnalysisRequest(returns=rets.tolist(), confidence_levels=[0.95], horizon_days=1))
    four = run_risk_analysis(RiskAnalysisRequest(returns=rets.tolist(), confidence_levels=[0.95], horizon_days=4))
    h1 = next(r for r in one.var_results if r.method == "historical").var_pct
    h4 = next(r for r in four.var_results if r.method == "historical").var_pct
    q1 = -h1  # 1-day return quantile
    mu = float(np.mean(rets))
    # Drift scales with T, the de-meaned shock with sqrt(T): q_T = mu*T + (q_1 - mu)*sqrt(T)
    assert h4 == pytest.approx(-(mu * 4 + (q1 - mu) * 2.0), rel=1e-9)
    assert h1 == pytest.approx(-float(np.quantile(rets, 0.05)), rel=1e-12)


def test_risk_analysis_drops_non_finite_and_validates_confidence(client: TestClient) -> None:
    rets = [0.01, -0.02, float("nan"), 0.005, -0.01, 0.02, float("inf"), -0.015, 0.012, -0.004, 0.003, 0.007]
    res = run_risk_analysis(RiskAnalysisRequest(returns=rets))
    assert res.observations == 10
    assert any("non-finite" in a for a in res.assumptions)

    r = client.post("/api/v1/risk/analyze", json={"returns": [0.01, -0.01] * 6, "confidence_levels": [1.2]})
    assert r.status_code == 422

    with pytest.raises(ValueError):
        run_risk_analysis(RiskAnalysisRequest(returns=[0.01] * 5 + [float("nan")] * 6))


# --------------------------------------------------------- Sharpe / Sortino / drawdown

def test_sharpe_exact_for_alternating_series_and_none_for_constant() -> None:
    c, d, n = 0.001, 0.01, 252
    rets = [c + d if i % 2 == 0 else c - d for i in range(n)]
    sample_std = d * math.sqrt(n / (n - 1))
    expected = (c * 252 - 0.02) / (sample_std * math.sqrt(252))
    assert sharpe_ratio(rets, 0.02, 252) == pytest.approx(expected, rel=1e-12)
    # A constant (zero-volatility) excess-return series has an undefined Sharpe ratio: None, not inf.
    assert sharpe_ratio([0.0005] * 100, 0.0, 252) is None


def test_sortino_uses_target_downside_deviation_over_all_observations() -> None:
    rets = [0.02, -0.01, 0.02, -0.01]
    dd = math.sqrt((0.01 ** 2 + 0.01 ** 2) / 4)  # denominator = ALL observations
    expected = (np.mean(rets) * 252) / (dd * math.sqrt(252))
    assert sortino_ratio(rets, 0.0, 252) == pytest.approx(expected, rel=1e-12)


def test_max_drawdown_hand_built_path_and_missing_values() -> None:
    path = [100.0, 120.0, 90.0, 95.0, 130.0, 65.0, 70.0]
    dd = drawdown_analysis(path)
    assert dd.max_drawdown == pytest.approx(-0.5)
    assert (dd.peak_index, dd.trough_index, dd.recovery_index) == (4, 5, None)
    # None / NaN no longer crash and do not reset the running peak.
    dd2 = drawdown_analysis([100.0, None, 80.0, float("nan"), 120.0])  # type: ignore[list-item]
    assert dd2.max_drawdown == pytest.approx(-0.2)
    assert len(dd2.series) == 5 and dd2.recovery_index == 4


def test_rolling_volatility_first_full_window_is_not_skipped() -> None:
    rets = [0.01, -0.01, 0.02, 0.0, -0.02]
    out = rolling_volatility(rets, window=3, periods_per_year=1)
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx(float(np.std(rets[0:3], ddof=1)))


def test_infer_periods_per_year_from_calendar() -> None:
    weekdays = _weekdays(date(2021, 1, 4), 261 * 3)
    assert infer_periods_per_year(weekdays) == pytest.approx(261, rel=0.01)
    daily = [date(2021, 1, 1) + timedelta(days=i) for i in range(366 * 2)]
    assert infer_periods_per_year(daily) == pytest.approx(365.25, rel=0.01)


# ------------------------------------------------------------- analytics engine fixes

def test_atr_uses_adjusted_basis_across_a_split() -> None:
    dates = _weekdays(date(2024, 1, 1), 40)
    bars: List[OHLCVBar] = []
    for i, d in enumerate(dates):
        raw = 200.0 if i < 20 else 100.0  # 2:1 split at bar 20, adjusted close continuous at 100
        bars.append(
            OHLCVBar(
                timestamp=datetime(d.year, d.month, d.day, tzinfo=timezone.utc),
                open=raw, high=raw * 1.01, low=raw * 0.99, close=raw, adjusted_close=100.0, volume=10,
            )
        )
    res = run_single_asset_analytics(SingleAssetAnalyticsRequest(instrument_id="XNAS:TEST", bars=bars))
    # On the adjusted basis every bar has H-L = 2 and |H - C_prev| = |L - C_prev| = 1 -> ATR = 2.
    assert res.summary.latest_atr_14 == pytest.approx(2.0, abs=1e-9)


def test_weekly_interval_annualises_with_52_and_bad_bars_are_dropped() -> None:
    dates = [date(2022, 1, 3) + timedelta(weeks=i) for i in range(60)]
    closes = [100.0 * (1.0 + (0.02 if i % 2 else -0.01)) ** (i // 2) for i in range(60)]
    bars = _bars_from_closes(dates, closes)
    bars.append(bars[5].copy())  # duplicate timestamp
    bars.append(OHLCVBar(timestamp=datetime(2030, 1, 1, tzinfo=timezone.utc), open=1, high=1, low=1, close=float("nan"), volume=1))
    res = run_single_asset_analytics(SingleAssetAnalyticsRequest(instrument_id="XNAS:W", bars=bars, interval="1wk"))
    assert res.summary.observations == 60
    rets = np.diff(closes) / np.array(closes[:-1])
    assert res.summary.annualized_volatility == pytest.approx(float(np.std(rets, ddof=1)) * math.sqrt(52), rel=1e-9)


# ------------------------------------------------------------------- optimizer fixes

def _price_maps_from_returns(rets: np.ndarray, names: List[str]) -> Dict[str, Dict[str, float]]:
    dates = [d.isoformat() for d in _weekdays(date(2023, 1, 2), rets.shape[0] + 1)]
    out: Dict[str, Dict[str, float]] = {}
    for j, name in enumerate(names):
        px = 100.0 * np.concatenate([[1.0], np.cumprod(1.0 + rets[:, j])])
        out[name] = {d: float(p) for d, p in zip(dates, px)}
    return out


def test_ledoit_wolf_is_positive_definite_when_t_le_n() -> None:
    X = np.random.default_rng(1).normal(0, 0.01, size=(5, 8))  # T=5 < N=8 -> sample cov singular
    lw, delta = ledoit_wolf_covariance(X)
    assert 0.0 < delta <= 1.0
    assert np.min(np.linalg.eigvalsh(lw)) > 0.0
    Xc = X - X.mean(axis=0)
    assert np.trace(lw) == pytest.approx(np.trace(Xc.T @ Xc / 5), rel=1e-12)  # trace preserved


def test_optimizer_switches_to_shrinkage_for_singular_covariance() -> None:
    rets = np.random.default_rng(2).normal(0.0005, 0.01, size=(6, 8))  # 6 returns, 8 assets
    names = [f"XNAS:A{i}" for i in range(8)]
    res = optimize_portfolio(PortfolioOptimizeRequest(asset_price_maps=_price_maps_from_returns(rets, names)))
    assert res.covariance_estimator == "ledoit_wolf"
    assert res.shrinkage_intensity is not None and 0.0 < res.shrinkage_intensity <= 1.0
    assert sum(res.min_variance_portfolio.weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_efficient_frontier_respects_max_weight_bound() -> None:
    rng = np.random.default_rng(4)
    drifts = np.array([0.0002, 0.0005, 0.0008, 0.0012])
    rets = drifts + rng.normal(0, 0.01, size=(300, 4))
    names = ["XNAS:A", "XNAS:B", "XNAS:C", "XNAS:D"]
    req = PortfolioOptimizeRequest(
        asset_price_maps=_price_maps_from_returns(rets, names), max_weight=0.4, frontier_points=12
    )
    res = optimize_portfolio(req)
    mu = rets.mean(axis=0) * 252
    order = np.argsort(mu)[::-1]
    lp_max = 0.4 * mu[order[0]] + 0.4 * mu[order[1]] + 0.2 * mu[order[2]]
    # Old code targeted max(mu), which is unattainable with max_weight=0.4 -> silent failures.
    assert len(res.efficient_frontier) == 12
    assert res.efficient_frontier[-1].expected_return == pytest.approx(lp_max, rel=1e-5)
    assert all(w <= 0.4 + 1e-6 for p in res.efficient_frontier for w in p.weights.values())
    vols = [p.volatility for p in res.efficient_frontier]
    assert vols == sorted(vols)  # frontier is monotone in risk
    assert not res.optimizer_warnings


def test_diverse_risk_candidate_returns_are_aligned_on_prices() -> None:
    dates = _weekdays(date(2024, 1, 1), 60)
    rng = np.random.default_rng(5)
    a = 100 * np.cumprod(1 + rng.normal(0, 0.01, 60))
    b = 50 * np.cumprod(1 + rng.normal(0, 0.01, 60))
    basket = {
        "XNAS:A": {d.isoformat(): float(p) for d, p in zip(dates, a)},
        "XNAS:B": {d.isoformat(): float(p) for d, p in zip(dates, b)},
    }
    # Candidate trades every other day at exactly A's price.
    cand = {d.isoformat(): float(p) for i, (d, p) in enumerate(zip(dates, a)) if i % 2 == 0}
    res = analyze_diverse_risk(DiverseRiskRequest(asset_price_maps=basket, candidate_price_maps={"XNAS:C": cand}))
    # With price alignment, C and A returns cover identical 2-day intervals -> corr(C, A) = 1,
    # so the average correlation with the basket is (1 + corr(A,B)_2day) / 2.
    assert len(res.candidate_additions) == 1
    joined_a = np.array([a[i] for i in range(0, 60, 2)])
    joined_b = np.array([b[i] for i in range(0, 60, 2)])
    ra, rb = np.diff(joined_a) / joined_a[:-1], np.diff(joined_b) / joined_b[:-1]
    expected = (1.0 + float(np.corrcoef(ra, rb)[0, 1])) / 2.0
    assert res.candidate_additions[0].avg_correlation_with_portfolio == pytest.approx(expected, abs=1e-4)


def test_fx_attribution_rejects_impossible_returns(client: TestClient) -> None:
    r = client.post("/api/v1/portfolio/fx-attribution", json={"local_return": -1.5, "fx_return": 0.0})
    assert r.status_code == 422


# ------------------------------------------------------------------ backtester fixes

def test_single_asset_buy_and_hold_equals_benchmark() -> None:
    dates = _weekdays(date(2024, 1, 1), 60)
    closes = [100.0 + 2.0 * math.sin(i / 3.0) + 0.3 * i for i in range(60)]
    res = run_backtest(BacktestRequest(instrument_id="XNAS:T", bars=_bars_from_closes(dates, closes), strategy="buy_and_hold"))
    # Same T+1 fill and cost model -> identical curves (benchmark used to be filled one bar earlier).
    assert res.equity_curve == pytest.approx(res.benchmark_curve, abs=1e-3)


def _two_asset_series(dates: List[date], pa: List[float], pb: List[float]):
    return {"XNAS:A": _bars_from_closes(dates, pa), "XNAS:B": _bars_from_closes(dates, pb)}


def test_portfolio_backtest_charges_full_turnover_including_entry() -> None:
    dates = _weekdays(date(2020, 1, 1), 262)
    q1_len = sum(1 for d in dates if d.month <= 3)
    pa = [100.0] * len(dates)
    pb = [100.0 * (1.0 + 0.10 * min(i, q1_len - 1) / (q1_len - 1)) for i in range(len(dates))]
    req = PortfolioBacktestRequest(
        instrument_ids=["XNAS:A", "XNAS:B"], asset_series=_two_asset_series(dates, pa, pb), years=2,
        allocation_method="equal_weight", rebalance_frequency="quarterly", initial_capital=100000.0,
        commission_bps=10.0, slippage_bps=5.0,
    )
    res = run_portfolio_backtest(req)
    k = 15.0 / 10000.0
    v0 = 100000.0 * (1 - k)
    # Entry: the whole capital is traded. At the first rebalance A = 0.5*V0, B = 0.55*V0, the
    # target is 0.525*V0 each, so traded notional |dA| + |dB| = 0.025*V0 + 0.025*V0 = 0.05*V0.
    # (The old code charged only half of this: 0.5 * sum|d|.) Later rebalances trade nothing.
    expected_costs = 100000.0 * k + k * (v0 * 0.10 / 2.0)
    assert res.total_transaction_costs == pytest.approx(expected_costs, abs=0.02)
    assert res.rebalance_count == 3  # first trading day of Q2, Q3 and Q4


def test_portfolio_calendar_year_return_includes_first_trading_day() -> None:
    dates = _weekdays(date(2020, 6, 1), 400)
    first_2021 = next(i for i, d in enumerate(dates) if d.year == 2021)
    px = [100.0 * (1.10 if i >= first_2021 else 1.0) for i in range(len(dates))]  # +10% jump on Jan 4, 2021
    req = PortfolioBacktestRequest(
        instrument_ids=["XNAS:A", "XNAS:B"], asset_series=_two_asset_series(dates, px, px), years=5,
        allocation_method="equal_weight", rebalance_frequency="buy_and_hold", commission_bps=0.0, slippage_bps=0.0,
    )
    res = run_portfolio_backtest(req)
    y2021 = next(c for c in res.calendar_year_returns if c.year == 2021)
    assert y2021.portfolio_return == pytest.approx(0.10, abs=1e-4)
    assert y2021.benchmark_return == pytest.approx(0.10, abs=1e-4)


def test_portfolio_backtest_has_no_look_ahead() -> None:
    dates = _weekdays(date(2019, 1, 1), 500)
    rng = np.random.default_rng(11)
    series = {}
    paths = {}
    for j, name in enumerate(["XNAS:A", "XNAS:B", "XNAS:C"]):
        r = rng.normal(0.0004 * (j + 1), 0.01 + 0.004 * j, size=len(dates))
        paths[name] = list(100.0 * np.cumprod(1 + r))
        series[name] = _bars_from_closes(dates, paths[name])
    base_req = dict(instrument_ids=list(series), years=5, allocation_method="min_variance", rebalance_frequency="quarterly")
    full = run_portfolio_backtest(PortfolioBacktestRequest(asset_series=series, **base_req))

    cut = 300  # perturb every price strictly AFTER bar `cut`
    perturbed = {}
    for name, p in paths.items():
        shocked = p[: cut + 1] + [x * (1.0 + 0.3 * math.sin(i)) for i, x in enumerate(p[cut + 1:])]
        perturbed[name] = _bars_from_closes(dates, shocked)
    alt = run_portfolio_backtest(PortfolioBacktestRequest(asset_series=perturbed, **base_req))

    assert full.timestamps == alt.timestamps
    cut_date = dates[cut].isoformat()
    n_same = sum(1 for ts in full.timestamps if ts <= cut_date)
    assert n_same > 100
    assert full.equity_curve[:n_same] == alt.equity_curve[:n_same]
    assert full.equity_curve[n_same:] != alt.equity_curve[n_same:]
    assert full.warmup_observations > 0 and full.start_date > dates[0].isoformat()


def test_simulator_median_path_compounds_at_shrunk_cagr() -> None:
    dates = _weekdays(date(2015, 1, 1), 2700)
    rng = np.random.default_rng(21)
    series = {}
    for j, name in enumerate(["XNAS:A", "XNAS:B", "XNAS:C"]):
        r = rng.normal(0.0005, 0.018, size=len(dates))
        series[name] = _bars_from_closes(dates, list(50.0 * (j + 1) * np.cumprod(1 + r)))
    res = run_portfolio_10y_simulation(
        PortfolioSimulationRequest(instrument_ids=list(series), asset_series=series, allocation_method="equal_weight")
    )
    shrunk = max(-0.05, min(0.16, res.cagr * DRIFT_SHRINKAGE))
    sigma = max(0.06, min(0.65, res.portfolio_volatility))
    five = next(s for s in res.forward_scenarios if s.horizon_years == 5)
    assert sigma ** 2 / 2 > 0.004  # the old volatility-drag double count would be detectable
    assert five.base_cagr == pytest.approx(shrunk, abs=0.003)
    # Allocation vols are measured on the aligned evaluation window.
    assert all(a.annualized_volatility > 0 for a in res.allocations)


# -------------------------------------------------------------- credit-model fixes

def _fin(scale: float = 1.0, **kw) -> FinancialStatementInputs:
    base = dict(
        total_assets=500e6, current_assets=200e6, current_liabilities=120e6, total_liabilities=300e6,
        total_debt=180e6, retained_earnings=90e6, ebit=45e6, ebitda=60e6, net_income=30e6,
        prev_net_income=26e6, revenue=420e6, interest_expense=9e6, operating_cash_flow=50e6,
        market_cap=400e6, equity_volatility_annual=0.35,
    )
    base.update(kw)
    for k in list(base):
        if k != "equity_volatility_annual":
            base[k] = base[k] * scale
    return FinancialStatementInputs(**base)


def test_ohlson_o_score_is_currency_invariant() -> None:
    usd = run_bankruptcy_pipeline(BankruptcyRequest(instrument_id="XNAS:X", override_financials=_fin()), currency_hint="USD")
    vnd = run_bankruptcy_pipeline(
        BankruptcyRequest(instrument_id="XSTC:X", override_financials=_fin(scale=26300.0)), currency_hint="VND"
    )
    o_usd = next(m for m in usd.models if m.model_name.startswith("Ohlson"))
    o_vnd = next(m for m in vnd.models if m.model_name.startswith("Ohlson"))
    assert o_vnd.raw_score == pytest.approx(o_usd.raw_score, abs=0.01)  # was ~ +4.1 apart before the fix
    assert vnd.ensemble_pd_12m == pytest.approx(usd.ensemble_pd_12m, abs=1e-3)


def test_merton_bharath_shumway_asset_volatility() -> None:
    E, D, sE, r = 100.0, 200.0, 0.40, 0.04
    dd, pd_ = _merton_distance_to_default(E, D, sE, r)
    F = 0.75 * D
    V = E + F
    sV = (E / V) * sE + (F / V) * (0.05 + 0.25 * sE)
    exp_dd = (math.log(V / F) + (r - 0.5 * sV ** 2)) / sV
    assert dd == pytest.approx(exp_dd, rel=1e-12)
    assert pd_ == pytest.approx(norm.cdf(-exp_dd), rel=1e-9)
    # Riskless-debt version (old) overstated DD for this levered firm.
    s_old = sE * E / V
    old_dd = (math.log(V / F) + (r - 0.5 * s_old ** 2)) / s_old
    assert dd < old_dd


def test_zero_interest_expense_does_not_explode_coverage() -> None:
    res = run_bankruptcy_pipeline(
        BankruptcyRequest(instrument_id="XNAS:NODEBT", override_financials=_fin(interest_expense=0.0, total_debt=0.0)),
        currency_hint="USD",
    )
    ic = next(m for m in res.models if m.model_name == "Interest Coverage Ratio")
    dscr = next(m for m in res.models if m.model_name.startswith("DSCR"))
    assert ic.raw_score == 999.0  # previously EBIT / 1.0 = 45,000,000x
    assert dscr.raw_score == 999.0


# --------------------------------------------------------------- security / ops

def test_assistant_status_does_not_leak_key_and_cors_has_no_credentials() -> None:
    settings = Settings(database_path=":memory:", enable_yfinance_fallback=False, gemini_api_key="AIzaSECRETSECRET")
    c = TestClient(create_app(settings=settings))
    body = c.get("/api/v1/assistant/status").json()
    assert body["gemini_configured"] is True
    assert "key_prefix" not in body and "AIza" not in str(body)
    r = c.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-credentials" not in r.headers
    assert r.json()["version"] == __version__ == "4.1.0"


def test_env_file_does_not_override_real_environment(tmp_path, monkeypatch) -> None:
    from app.core import config as cfg

    (tmp_path / ".env").write_text("QUANTAI_TEST_PRECEDENCE=from-file\nQUANTAI_TEST_UNSET=file-only\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANTAI_TEST_PRECEDENCE", "from-env")
    monkeypatch.delenv("QUANTAI_TEST_UNSET", raising=False)
    # Explicit candidates: exercise the precedence logic without reading the developer's .env.
    cfg._load_env_files(candidates=[tmp_path / ".env"])
    import os

    assert os.environ["QUANTAI_TEST_PRECEDENCE"] == "from-env"
    assert os.environ["QUANTAI_TEST_UNSET"] == "file-only"
    monkeypatch.delenv("QUANTAI_TEST_UNSET", raising=False)


def test_gemini_calls_respect_total_time_budget() -> None:
    calls = {"n": 0}

    class _Resp:
        status_code = 500
        text = "boom"

    def slow_post(*_a, **kw):
        calls["n"] += 1
        time.sleep(0.25)
        return _Resp()

    t0 = time.monotonic()
    res = ask_diverse_risk_advisor(
        DiverseRiskAdvisorRequest(question="How risky is my portfolio?", selected_stocks=["XNAS:AAPL"]),
        gemini_api_key="AQ.fake",
        http_post=slow_post,
        total_budget_seconds=1.0,
    )
    assert time.monotonic() - t0 < 2.0
    assert calls["n"] <= 4
    assert res.used_llm is False


def test_no_key_reply_is_honest() -> None:
    res = ask_diverse_risk_advisor(DiverseRiskAdvisorRequest(question="tell me a joke", selected_stocks=[]))
    assert "GEMINI_API_KEY" in res.answer and "high-demand" not in res.answer
