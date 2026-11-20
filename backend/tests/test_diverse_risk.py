"""Automated verification tests for Diverse-Risk Analyzer (up to 10 stocks)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class TestDiverseRisk(unittest.TestCase):
    def setUp(self) -> None:
        settings = Settings(database_path=":memory:", enable_yfinance_fallback=False)
        self.client = TestClient(create_app(settings=settings))
        self.dates = [(datetime(2026, 1, 2) + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(25)]

    def test_rejects_more_than_10_stocks(self) -> None:
        maps = {f"XNAS:S{k}": {d: 100.0 + i for i, d in enumerate(self.dates)} for k in range(11)}
        r = self.client.post("/api/v1/portfolio/diverse-risk", json={"asset_price_maps": maps})
        self.assertEqual(r.status_code, 400)
        self.assertIn("between 2 and 10", r.json()["detail"])

    def test_detects_strong_risk_reduction_and_candidate_suggestions(self) -> None:
        # Stock A and Stock B move inversely -> strong risk reduction; Stock C mirrors A -> redundant
        a_px, b_px, c_px, cand_px = {}, {}, {}, {}
        pa, pb, pc, pd_ = 100.0, 100.0, 50.0, 200.0
        for i, d in enumerate(self.dates):
            r_a = 0.02 if i % 2 == 0 else -0.015
            r_b = -0.018 if i % 2 == 0 else 0.022
            r_cand = -0.012 if i % 2 == 0 else 0.015
            pa *= 1.0 + r_a
            pb *= 1.0 + r_b
            pc *= 1.0 + r_a  # perfectly correlated with A
            pd_ *= 1.0 + r_cand
            a_px[d], b_px[d], c_px[d], cand_px[d] = round(pa, 4), round(pb, 4), round(pc, 4), round(pd_, 4)

        r = self.client.post(
            "/api/v1/portfolio/diverse-risk",
            json={
                "asset_price_maps": {"XNAS:A": a_px, "XSTC:B": b_px, "XNAS:C": c_px},
                "candidate_price_maps": {"XSWX:DEF": cand_px},
            },
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["is_risk_reducing"])
        self.assertGreater(body["diversification_ratio"], 1.1)
        self.assertGreater(body["risk_reduction_pct"], 10.0)
        self.assertEqual(body["highest_correlation_pairs"][0]["correlation"], 1.0)
        self.assertGreaterEqual(len(body["suggested_combinations"]), 1)
        self.assertEqual(len(body["candidate_additions"]), 1)
        self.assertTrue(body["candidate_additions"][0]["is_risk_reducing"])


if __name__ == "__main__":
    unittest.main()
