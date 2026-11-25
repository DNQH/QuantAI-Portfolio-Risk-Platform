"""Independent mathematical verification tests for Phase 2 Quantitative Analysis.

Every test validates against hand-calculated or SciPy-verified reference values.
"""

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

from app.analytics.indicators import (
    atr,
    bollinger_bands,
    ema,
    macd,
    rate_of_change,
    rsi_wilder,
    sma,
)
from app.analytics.returns import (
    annualized_return,
    annualized_volatility,
    cumulative_returns,
    drawdown_analysis,
    log_returns,
    sharpe_ratio,
    simple_returns,
    sortino_ratio,
)
from app.analytics.statistics import (
    correlation_and_covariance_matrices,
    descriptive_statistics,
)
from app.core.config import Settings
from app.main import create_app


class TestPhase2ReturnsAndRiskAdjusted(unittest.TestCase):
    def test_simple_log_cumulative_and_annualized_returns(self) -> None:
        prices = [100.0, 110.0, 99.0, 121.0]
        s = simple_returns(prices)
        lr = log_returns(prices)
        c = cumulative_returns(prices)

        self.assertIsNone(s[0])
        self.assertAlmostEqual(s[1], 0.10, places=10)
        self.assertAlmostEqual(s[2], -0.10, places=10)
        self.assertAlmostEqual(s[3], 22.0 / 99.0, places=10)

        self.assertIsNone(lr[0])
        self.assertAlmostEqual(lr[1], math.log(1.1), places=10)
        self.assertAlmostEqual(lr[2], math.log(0.9), places=10)

        self.assertAlmostEqual(c[0], 0.0, places=10)
        self.assertAlmostEqual(c[-1], 0.21, places=10)

        # 3 periods growing 1.21x annualized at 252 periods/yr
        expected_cagr = (1.21 ** (252 / 3)) - 1.0
        self.assertAlmostEqual(annualized_return(prices, 252), expected_cagr, places=8)

    def test_volatility_sharpe_and_sortino(self) -> None:
        # Known returns: [0.02, -0.01, 0.03, -0.02, 0.01] -> mean = 0.006
        returns = [None, 0.02, -0.01, 0.03, -0.02, 0.01]
        # Sample variance = ((0.014)^2 + (-0.016)^2 + (0.024)^2 + (-0.026)^2 + (0.004)^2) / 4
        expected_var = (0.014**2 + 0.016**2 + 0.024**2 + 0.026**2 + 0.004**2) / 4.0
        expected_std = math.sqrt(expected_var)
        expected_ann_vol = expected_std * math.sqrt(252)
        self.assertAlmostEqual(annualized_volatility(returns, 252), expected_ann_vol, places=10)

        expected_sharpe = (0.006 * 252 - 0.02) / expected_ann_vol
        self.assertAlmostEqual(sharpe_ratio(returns, 0.02, 252), expected_sharpe, places=10)

        # Sortino with Rf = 0.0: downside deviations are [-0.01, -0.02] among 5 observations
        expected_down = math.sqrt((0.01**2 + 0.02**2) / 5.0) * math.sqrt(252)
        expected_sortino = (0.006 * 252) / expected_down
        self.assertAlmostEqual(sortino_ratio(returns, 0.0, 252), expected_sortino, places=10)

    def test_drawdown_and_recovery(self) -> None:
        # Peak=120 (idx 1), Trough=90 (idx 3) -> MDD = -25%, Recovery at idx 5 (125 >= 120) -> 2 bars
        prices = [100.0, 120.0, 108.0, 90.0, 110.0, 125.0]
        dd = drawdown_analysis(prices)
        self.assertAlmostEqual(dd.max_drawdown, -0.25, places=10)
        self.assertEqual(dd.peak_index, 1)
        self.assertEqual(dd.trough_index, 3)
        self.assertEqual(dd.recovery_index, 5)
        self.assertEqual(dd.recovery_bars, 2)


class TestPhase2Indicators(unittest.TestCase):
    def test_sma_and_ema_exact_values(self) -> None:
        prices = [10.0, 12.0, 14.0, 16.0, 18.0]
        s3 = sma(prices, 3)
        self.assertEqual(s3[:2], [None, None])
        self.assertAlmostEqual(s3[2], 12.0, places=10)
        self.assertAlmostEqual(s3[4], 16.0, places=10)

        e3 = ema(prices, 3)
        # alpha = 2/(3+1) = 0.5; seed = 12.0; e3[3] = 0.5*16 + 0.5*12 = 14.0; e3[4] = 0.5*18 + 0.5*14 = 16.0
        self.assertEqual(e3[:2], [None, None])
        self.assertAlmostEqual(e3[2], 12.0, places=10)
        self.assertAlmostEqual(e3[3], 14.0, places=10)
        self.assertAlmostEqual(e3[4], 16.0, places=10)

    def test_rsi_wilder_alignment_and_edge_cases(self) -> None:
        # Strictly increasing prices: avg_loss == 0 -> RSI must be exact 100.0 (not 99 as in old prototype!)
        up_prices = [100.0 + i for i in range(20)]
        rsi_up = rsi_wilder(up_prices, period=14)
        self.assertEqual(len(rsi_up), len(up_prices))  # Exact alignment (no N+1 shift bug!)
        self.assertEqual(rsi_up[:14], [None] * 14)
        self.assertAlmostEqual(rsi_up[14], 100.0, places=10)
        self.assertAlmostEqual(rsi_up[-1], 100.0, places=10)

        # Flat prices: avg_gain == 0 and avg_loss == 0 -> RSI == 50.0
        flat_prices = [50.0] * 18
        rsi_flat = rsi_wilder(flat_prices, period=14)
        self.assertAlmostEqual(rsi_flat[14], 50.0, places=10)

        # Insufficient lookback -> all None without crashing
        self.assertEqual(rsi_wilder([10.0, 11.0, 12.0], period=14), [None, None, None])

    def test_macd_bollinger_roc_and_atr(self) -> None:
        prices = [100.0 + (i * 0.5) + ((-1) ** i) * 1.2 for i in range(45)]
        m = macd(prices)
        self.assertEqual(len(m["macd"]), 45)
        self.assertIsNotNone(m["macd"][-1])
        self.assertIsNotNone(m["signal"][-1])
        self.assertAlmostEqual(m["histogram"][-1], m["macd"][-1] - m["signal"][-1], places=10)

        bb = bollinger_bands(prices, period=20, num_std=2.0, ddof=1)
        self.assertEqual(len(bb["upper"]), 45)
        self.assertGreater(bb["upper"][-1], bb["middle"][-1])
        self.assertLess(bb["lower"][-1], bb["middle"][-1])

        r = rate_of_change([100.0, 105.0, 110.0], period=2)
        self.assertAlmostEqual(r[2], 10.0, places=10)

        highs = [p + 2.0 for p in prices]
        lows = [p - 2.0 for p in prices]
        a = atr(highs, lows, prices, period=14)
        self.assertEqual(len(a), 45)
        self.assertIsNone(a[12])
        self.assertIsNotNone(a[13])
        self.assertGreater(a[-1], 0.0)


class TestPhase2StatisticsAndAPI(unittest.TestCase):
    def test_descriptive_stats_and_correlation_covariance_matrices(self) -> None:
        stats = descriptive_statistics([None, 0.01, 0.02, -0.01, 0.03, -0.02, 0.015])
        self.assertEqual(stats["count"], 6)
        self.assertIsNotNone(stats["skewness"])
        self.assertIsNotNone(stats["excess_kurtosis"])

        # Perfect positive correlation between A and B (B = 2 * A)
        price_maps = {
            "XNAS:A": {"2026-01-02": 100.0, "2026-01-03": 105.0, "2026-01-04": 102.0, "2026-01-05": 110.0},
            "XSTC:B": {"2026-01-02": 200.0, "2026-01-03": 210.0, "2026-01-04": 204.0, "2026-01-05": 220.0},
        }
        syms, count, corr, cov = correlation_and_covariance_matrices(price_maps, periods_per_year=252)
        self.assertEqual(syms, ["XNAS:A", "XSTC:B"])
        self.assertEqual(count, 3)
        self.assertAlmostEqual(corr["XNAS:A"]["XSTC:B"], 1.0, places=10)
        self.assertAlmostEqual(cov["XNAS:A"]["XNAS:A"], cov["XSTC:B"]["XSTC:B"], places=10)

    def test_fastapi_analytics_endpoints(self) -> None:
        settings = Settings(database_path=":memory:", enable_yfinance_fallback=False)
        client = TestClient(create_app(settings=settings))

        base_dt = datetime(2026, 1, 2, tzinfo=timezone.utc)
        bars = []
        p = 100.0
        for i in range(40):
            p = p * (1.0 + (0.012 if i % 3 != 0 else -0.008))
            bars.append(
                {
                    "timestamp": (base_dt + timedelta(days=i)).isoformat(),
                    "open": round(p * 0.995, 4),
                    "high": round(p * 1.01, 4),
                    "low": round(p * 0.99, 4),
                    "close": round(p, 4),
                    "adjusted_close": round(p, 4),
                    "volume": 100000 + i * 1000,
                }
            )

        r = client.post(
            "/api/v1/analytics/single-asset",
            json={"instrument_id": "XNAS:AAPL", "bars": bars, "risk_free_rate_annual": 0.04},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["summary"]["observations"], 40)
        self.assertIsNotNone(body["summary"]["sharpe_ratio"])
        self.assertIsNotNone(body["summary"]["sortino_ratio"])
        self.assertIsNotNone(body["summary"]["latest_rsi_14"])
        self.assertGreaterEqual(len(body["assumptions"]), 4)

        m = client.post(
            "/api/v1/analytics/matrix",
            json={
                "asset_price_maps": {
                    "XNAS:AAPL": {"2026-01-02": 100.0, "2026-01-03": 102.0, "2026-01-04": 101.0, "2026-01-05": 105.0},
                    "XSTC:FPT": {"2026-01-02": 120000.0, "2026-01-03": 121200.0, "2026-01-04": 120600.0, "2026-01-05": 123000.0},
                }
            },
        )
        self.assertEqual(m.status_code, 200)
        m_body = m.json()
        self.assertEqual(m_body["aligned_return_observations"], 3)
        self.assertIn("XNAS:AAPL", m_body["correlation_matrix"])


if __name__ == "__main__":
    unittest.main()
