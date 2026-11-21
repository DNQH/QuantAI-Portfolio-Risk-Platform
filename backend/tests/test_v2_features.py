"""Unit and integration tests for QuantAI v2.0.0 features:
- Vietnam UPCOM (XUPC) symbology, calendar, and exchange coverage
- Crowd Sentiment & Prediction Market ("What People Think?") endpoint
- 4-Stage Corporate Bankruptcy & 12-Month PD Pipeline (Altman Z, Ohlson O, Merton, DSCR, IC, Logistic, XGBoost/GBDT)
- 10-Year Multi-Stock Portfolio Backtesting Engine
"""

from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.backtesting.engine import PortfolioBacktestRequest, run_portfolio_backtest
from app.core.calendar import get_market_session
from app.core.models import OHLCVBar
from app.core.symbology import search_seed_instruments
from app.main import create_app
from app.risk.bankruptcy import BankruptcyRequest, FinancialStatementInputs, run_bankruptcy_pipeline


def _synthetic_bars(start_px: float, drift: float, vol: float, n_days: int = 2520) -> list[OHLCVBar]:
    import numpy as np

    rng = np.random.default_rng(int(start_px * 100))
    px = start_px
    bars = []
    base_dt = datetime(2016, 1, 4, 16, 0, tzinfo=timezone.utc)
    for i in range(n_days):
        dt = base_dt + timedelta(days=i)
        if dt.weekday() >= 5:
            continue
        ret = drift / 252.0 + (vol / math.sqrt(252.0)) * float(rng.normal())
        px = max(1.0, px * (1.0 + ret))
        bars.append(
            OHLCVBar(
                timestamp=dt,
                open=round(px * 0.995, 2),
                high=round(px * 1.01, 2),
                low=round(px * 0.99, 2),
                close=round(px, 2),
                adjusted_close=round(px, 2),
                volume=100000.0,
            )
        )
    return bars


class TestQuantAIV2Features(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_upcom_symbology_calendar_and_coverage(self) -> None:
        upcom_list = search_seed_instruments(exchange="XUPC")
        self.assertGreaterEqual(len(upcom_list), 5)
        self.assertTrue(any(i.ticker == "ACV" and i.exchange_acronym == "UPCOM" for i in upcom_list))

        sess = get_market_session("XUPC", now_utc=datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc))
        self.assertEqual(sess.exchange_mic, "XUPC")

        cov_resp = self.client.get("/api/v1/exchanges/coverage")
        self.assertEqual(cov_resp.status_code, 200)
        mics = {row["exchange_mic"] for row in cov_resp.json()}
        self.assertIn("XUPC", mics)

    def test_crowd_sentiment_endpoint(self) -> None:
        resp = self.client.post(
            "/api/v1/sentiment/crowd",
            json={
                "instrument_id": "XNAS:AAPL",
                "company_name": "Apple Inc.",
                "horizon": "1M",
                "recent_return_20d": 0.06,
                "annualized_volatility": 0.24,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data["verdict"], {"POSITIVE", "NEUTRAL", "NEGATIVE"})
        self.assertGreaterEqual(data["predicted_positive_probability"], 0.0)
        self.assertLessEqual(data["predicted_positive_probability"], 1.0)
        self.assertEqual(data["horizon"], "1M")

    def test_bankruptcy_pipeline_7_models_and_monotonicity(self) -> None:
        healthy = FinancialStatementInputs(
            total_assets=350_000,
            current_assets=150_000,
            current_liabilities=70_000,
            total_liabilities=120_000,
            total_debt=60_000,
            retained_earnings=140_000,
            ebit=80_000,
            ebitda=95_000,
            net_income=62_000,
            prev_net_income=58_000,
            revenue=380_000,
            interest_expense=2_500,
            operating_cash_flow=90_000,
            market_cap=1_200_000,
            equity_volatility_annual=0.22,
        )
        distressed = FinancialStatementInputs(
            total_assets=100_000,
            current_assets=18_000,
            current_liabilities=38_000,
            total_liabilities=92_000,
            total_debt=78_000,
            retained_earnings=-25_000,
            ebit=-8_000,
            ebitda=2_000,
            net_income=-14_000,
            prev_net_income=-11_000,
            revenue=45_000,
            interest_expense=7_500,
            operating_cash_flow=-5_000,
            market_cap=12_000,
            equity_volatility_annual=0.75,
        )

        res_healthy = run_bankruptcy_pipeline(BankruptcyRequest(instrument_id="XNAS:AAPL", override_financials=healthy))
        res_distressed = run_bankruptcy_pipeline(BankruptcyRequest(instrument_id="XNAS:DIST", override_financials=distressed))

        self.assertEqual(len(res_healthy.models), 7)
        self.assertEqual(len(res_healthy.variables), 8)
        self.assertLess(res_healthy.ensemble_pd_12m, 0.05)
        self.assertGreater(res_distressed.ensemble_pd_12m, 0.30)
        self.assertEqual(res_healthy.risk_zone, "SAFE")
        self.assertEqual(res_distressed.risk_zone, "DISTRESS")

        api_resp = self.client.post("/api/v1/risk/bankruptcy", json={"instrument_id": "XNAS:AAPL"})
        self.assertEqual(api_resp.status_code, 200)
        self.assertEqual(len(api_resp.json()["models"]), 7)

    def test_ten_year_portfolio_backtest(self) -> None:
        series = {
            "XNAS:AAPL": _synthetic_bars(100.0, 0.14, 0.24, n_days=3600),
            "XNAS:MSFT": _synthetic_bars(80.0, 0.12, 0.22, n_days=3600),
            "XSTC:FPT": _synthetic_bars(50.0, 0.10, 0.26, n_days=3600),
        }
        req = PortfolioBacktestRequest(
            instrument_ids=["XNAS:AAPL", "XNAS:MSFT", "XSTC:FPT"],
            asset_series=series,
            years=10,
            allocation_method="min_variance",
            rebalance_frequency="quarterly",
            initial_capital=100000.0,
        )
        res = run_portfolio_backtest(req)
        self.assertGreaterEqual(res.years_covered, 9.0)
        self.assertGreater(res.rebalance_count, 20)
        self.assertGreater(len(res.calendar_year_returns), 8)
        self.assertAlmostEqual(sum(res.target_weights.values()), 1.0, places=3)



    def test_v3_ten_iconic_per_exchange_and_10y_simulation(self) -> None:
        from app.portfolio.simulator import PortfolioSimulationRequest, run_portfolio_10y_simulation

        for mic in ("XNYS", "XNAS", "XSTC", "XHAI", "XUPC", "XLON", "XETR", "XTKS", "XHKG", "XSES", "XASX"):
            items = search_seed_instruments(exchange=mic)
            self.assertGreaterEqual(len(items), 10, f"Exchange {mic} has fewer than 10 iconic stocks")

        series = {
            "XNYS:JNJ": _synthetic_bars(120.0, 0.08, 0.16, n_days=3600),
            "XNAS:MSFT": _synthetic_bars(90.0, 0.15, 0.24, n_days=3600),
            "XSTC:FPT": _synthetic_bars(50.0, 0.12, 0.22, n_days=3600),
        }
        res = run_portfolio_10y_simulation(
            PortfolioSimulationRequest(
                instrument_ids=["XNYS:JNJ", "XNAS:MSFT", "XSTC:FPT"],
                capital=500000.0,
                currency="USD",
                allocation_method="min_variance",
                years=10,
                asset_series=series,
            )
        )
        self.assertEqual(len(res.allocations), 3)
        self.assertAlmostEqual(sum(a.weight for a in res.allocations), 1.0, places=3)
        self.assertAlmostEqual(sum(a.allocated_capital for a in res.allocations), 500000.0, delta=50.0)
        self.assertEqual(len(res.forward_scenarios), 3)
        for sc in res.forward_scenarios:
            self.assertLessEqual(sc.bear_value, sc.base_value)
            self.assertLessEqual(sc.base_value, sc.bull_value)



    def test_v31_standalone_assistant_answers_without_analysis(self) -> None:
        resp = self.client.post(
            "/api/v1/portfolio/diverse-risk/ask",
            json={
                "question": "Which 5 stocks across US and Vietnam best minimize crash drawdown?",
                "market_scope": "United States + Vietnam",
                "selected_sectors": ["Healthcare", "Technology", "Utilities"],
                "selected_stocks": ["XNYS:JNJ", "XNAS:MSFT", "XSTC:FPT"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(len(body["answer"]) > 40)
        self.assertIn("engine_used", body)



    def test_v311_conversational_assistant_distinct_replies(self) -> None:
        base_payload = {
            "market_scope": "Vietnam",
            "selected_sectors": ["Technology", "Industrials", "Real Estate"],
            "selected_stocks": ["XSTC:FPT", "XHAI:CEO", "XSTC:SSI", "XUPC:FOX", "XUPC:ACV"],
        }
        r_hi = self.client.post("/api/v1/portfolio/diverse-risk/ask", json={**base_payload, "question": "Good morning!"})
        r_add = self.client.post("/api/v1/portfolio/diverse-risk/ask", json={**base_payload, "question": "Which stock should I add or remove from my current portfolio?"})
        r_rate = self.client.post("/api/v1/portfolio/diverse-risk/ask", json={**base_payload, "question": "How should I hedge against rising interest rates?"})
        self.assertEqual(r_hi.status_code, 200)
        self.assertEqual(r_add.status_code, 200)
        self.assertEqual(r_rate.status_code, 200)
        a_hi, a_add, a_rate = r_hi.json()["answer"], r_add.json()["answer"], r_rate.json()["answer"]
        self.assertIn("Good morning", a_hi)
        self.assertNotEqual(a_hi, a_add)
        self.assertNotEqual(a_add, a_rate)
        self.assertIn("trim or remove", a_add.lower())



    def test_v32_multiturn_chat_and_status(self) -> None:
        st = self.client.get("/api/v1/assistant/status")
        self.assertEqual(st.status_code, 200)
        self.assertIn("gemini_configured", st.json())

        r = self.client.post(
            "/api/v1/portfolio/diverse-risk/ask",
            json={
                "question": "What about adding VNM instead?",
                "market_scope": "Vietnam",
                "selected_stocks": ["XSTC:FPT", "XHAI:CEO", "XSTC:SSI"],
                "conversation_history": [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hi there! How can I help with your Vietnam basket?"},
                ],
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.json()["answer"]) > 20)



    def test_v4_risk_tracker_and_one_billion_capital(self) -> None:
        from app.portfolio.simulator import PortfolioSimulationRequest, run_portfolio_10y_simulation

        resp = self.client.get("/api/v1/risk/tracker?risk_id=tariffs_fx&market=ALL")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["sector_impacts"]), 11)
        # Verify sectors are sorted from most severely impacted -> least impacted
        scores = [s["severity_score"] for s in body["sector_impacts"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertGreaterEqual(len(body["emerging_hypotheses"]), 4)

        # Verify 1 Billion capital accepted
        series = {
            "XSTC:FPT": _synthetic_bars(50.0, 0.12, 0.22, n_days=1200),
            "XSTC:VNM": _synthetic_bars(70.0, 0.06, 0.16, n_days=1200),
        }
        sim = run_portfolio_10y_simulation(
            PortfolioSimulationRequest(
                instrument_ids=["XSTC:FPT", "XSTC:VNM"],
                capital=1_000_000_000.0,
                currency="VND",
                years=5,
                asset_series=series,
            )
        )
        self.assertAlmostEqual(sim.initial_capital, 1_000_000_000.0)


if __name__ == "__main__":
    unittest.main()
