"""Comprehensive automated tests for Phases 3, 4, 5, 6, and 7."""

from __future__ import annotations

import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.backtesting.engine import compute_strategy_target_positions
from app.core.config import Settings
from app.core.symbology import search_seed_instruments, to_yfinance_symbol
from app.main import create_app


def _make_deterministic_bars(n: int = 80, start_price: float = 100.0):
    base_dt = datetime(2026, 1, 2, tzinfo=timezone.utc)
    bars = []
    p = start_price
    for i in range(n):
        wave = 0.015 * math.sin(i / 4.0) + 0.0025
        p = p * (1.0 + wave)
        bars.append(
            {
                "timestamp": (base_dt + timedelta(days=i)).isoformat(),
                "open": round(p * 0.995, 4),
                "high": round(p * 1.012, 4),
                "low": round(p * 0.988, 4),
                "close": round(p, 4),
                "adjusted_close": round(p, 4),
                "volume": 150000 + (i % 7) * 12000,
            }
        )
    return bars


class TestPhases3To7(unittest.TestCase):
    def setUp(self) -> None:
        settings = Settings(database_path=":memory:", enable_yfinance_fallback=False)
        self.client = TestClient(create_app(settings=settings))

    def test_phase3_portfolio_optimization_capm_fx_and_crud(self) -> None:
        dates = [(datetime(2026, 1, 2) + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
        a_px = {}
        b_px = {}
        c_px = {}
        pa, pb, pc = 100.0, 50.0, 200.0
        for i, d in enumerate(dates):
            pa *= 1.0 + (0.012 if i % 2 == 0 else -0.005)
            pb *= 1.0 + (-0.004 if i % 2 == 0 else 0.011)
            pc *= 1.0 + (0.004 if i % 3 != 0 else -0.002)
            a_px[d], b_px[d], c_px[d] = round(pa, 4), round(pb, 4), round(pc, 4)

        r = self.client.post(
            "/api/v1/portfolio/optimize",
            json={
                "asset_price_maps": {"XNAS:AAPL": a_px, "XSTC:FPT": b_px, "XLON:HSBA": c_px},
                "risk_free_rate_annual": 0.03,
                "frontier_points": 10,
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        gmv = body["min_variance_portfolio"]
        eq = body["equal_weight_portfolio"]
        self.assertAlmostEqual(sum(gmv["weights"].values()), 1.0, places=4)
        self.assertAlmostEqual(sum(gmv["risk_contributions_pct"].values()), 1.0, places=3)
        self.assertLessEqual(gmv["volatility"], eq["volatility"] + 1e-6)
        self.assertGreaterEqual(len(body["efficient_frontier"]), 1)

        # CAPM exact check: r_a = 1.5 * r_m -> beta = 1.5
        rm = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02]
        ra = [1.5 * x for x in rm]
        capm = self.client.post(
            "/api/v1/portfolio/capm",
            json={"asset_returns": ra, "market_returns": rm, "risk_free_rate_annual": 0.04},
        ).json()
        self.assertAlmostEqual(capm["beta"], 1.5, places=6)
        self.assertAlmostEqual(capm["r_squared"], 1.0, places=6)

        # FX attribution exact check: (1 + 0.10)*(1 - 0.05) - 1 = 0.045
        fx = self.client.post(
            "/api/v1/portfolio/fx-attribution",
            json={"local_return": 0.10, "fx_return": -0.05},
        ).json()
        self.assertAlmostEqual(fx["base_currency_return"], 0.045, places=8)
        self.assertAlmostEqual(fx["interaction_term"], -0.005, places=8)

        # SQLite Portfolio CRUD
        saved = self.client.post(
            "/api/v1/portfolio/save",
            json={
                "portfolio_id": "global-core-1",
                "name": "Global Quant Core",
                "base_currency": "USD",
                "holdings": [
                    {"instrument_id": "XNAS:AAPL", "weight": 0.6, "currency": "USD", "country": "United States", "sector": "Technology"},
                    {"instrument_id": "XSTC:FPT", "weight": 0.4, "currency": "VND", "country": "Vietnam", "sector": "Technology"},
                ],
            },
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["exposures"]["currency"]["VND"], 0.4)
        listed = self.client.get("/api/v1/portfolio/list").json()
        self.assertEqual(len(listed), 1)

    def test_phase4_risk_var_cvar_monotonicity_and_stress(self) -> None:
        rets = [0.012, -0.018, 0.009, -0.025, 0.015, -0.008, 0.004, -0.031, 0.021, -0.014, 0.007, -0.019, 0.011, -0.005, 0.006]
        bench = [0.010, -0.012, 0.008, -0.020, 0.012, -0.006, 0.003, -0.024, 0.018, -0.010, 0.005, -0.015, 0.009, -0.004, 0.005]
        r = self.client.post(
            "/api/v1/risk/analyze",
            json={
                "returns": rets,
                "benchmark_returns": bench,
                "portfolio_value": 100000.0,
                "confidence_levels": [0.95, 0.99],
                "monte_carlo_simulations": 2000,
                "monte_carlo_seed": 42,
                "currency_weights": {"USD": 0.7, "VND": 0.3},
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["var_results"]), 6)  # 3 methods x 2 confidence levels
        for row in body["var_results"]:
            self.assertGreaterEqual(row["cvar_pct"], row["var_pct"] - 1e-9)
        self.assertIsNotNone(body["tracking_error"])
        self.assertIsNotNone(body["information_ratio"])
        self.assertEqual(len(body["stress_scenarios"]), 4)

    def test_phase5_ml_forecasting_chronological_split_and_all_models(self) -> None:
        bars = _make_deterministic_bars(80)
        r = self.client.post(
            "/api/v1/forecasting/run",
            json={"instrument_id": "XNAS:AAPL", "bars": bars, "test_ratio": 0.25},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # Strict chronological ordering: train_end < test_start
        self.assertLess(body["train_end"], body["test_start"])
        model_names = {m["model_name"] for m in body["models"]}
        self.assertEqual(
            model_names,
            {
                "naive_last_price",
                "naive_historical_mean",
                "ridge_regression",
                "arima_ar4_returns",
                "random_forest",
                "gradient_boosting",
            },
        )
        for m in body["models"]:
            self.assertGreaterEqual(m["mae"], 0.0)
            self.assertGreaterEqual(m["rmse"], 0.0)
            self.assertNotIn("confidence_score", m)  # Never fabricate confidence scores!

    def test_phase6_signals_and_bias_free_backtesting(self) -> None:
        bars = _make_deterministic_bars(70)
        sig = self.client.post(
            "/api/v1/signals/evaluate",
            json={"instrument_id": "XNAS:AAPL", "bars": bars},
        )
        self.assertEqual(sig.status_code, 200)
        self.assertIn(sig.json()["composite_signal"], {"BULLISH", "BEARISH", "NEUTRAL"})
        self.assertEqual(len(sig.json()["rules"]), 5)

        # Look-ahead bias invariance check: truncating closes at t must yield identical signal at t
        closes = [b["close"] for b in bars]
        full_pos = compute_strategy_target_positions(closes, "sma_crossover", fast_window=5, slow_window=15)
        trunc_pos = compute_strategy_target_positions(closes[:40], "sma_crossover", fast_window=5, slow_window=15)
        self.assertEqual(full_pos[:40], trunc_pos)

        bt = self.client.post(
            "/api/v1/backtesting/run",
            json={
                "instrument_id": "XNAS:AAPL",
                "bars": bars,
                "strategy": "sma_crossover",
                "fast_window": 5,
                "slow_window": 15,
                "commission_bps": 10.0,
                "slippage_bps": 5.0,
            },
        )
        self.assertEqual(bt.status_code, 200)
        bt_body = bt.json()
        self.assertEqual(len(bt_body["equity_curve"]), len(bars))
        self.assertEqual(len(bt_body["benchmark_curve"]), len(bars))
        self.assertGreaterEqual(bt_body["total_transaction_costs"], 0.0)

    def test_phase7_global_expansion_symbology(self) -> None:
        global_list = search_seed_instruments(query="")
        mics = {i.exchange_mic for i in global_list}
        for expected_mic in ("XNYS", "XNAS", "XSTC", "XHAI", "XLON", "XETR", "XPAR", "XSWX", "XTKS", "XHKG", "XSES", "XASX"):
            self.assertIn(expected_mic, mics)
        self.assertEqual(to_yfinance_symbol("7203", "XTKS"), "7203.T")
        self.assertEqual(to_yfinance_symbol("HSBA", "XLON"), "HSBA.L")
        self.assertEqual(to_yfinance_symbol("BHP", "XASX"), "BHP.AX")


if __name__ == "__main__":
    unittest.main()
