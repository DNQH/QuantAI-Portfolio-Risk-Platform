"""Automated verification tests for Diverse-Risk Analyzer & Grounded AI Advisor."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.portfolio.advisor import DiverseRiskAdvisorRequest, ask_diverse_risk_advisor
from app.portfolio.optimizer import DiverseRiskRequest, analyze_diverse_risk


class _FakeGeminiResp:
    status_code = 200

    def json(self) -> Dict[str, Any]:
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "Combining XNAS:A with XSTC:B and defensive XSWX:DEF reduces volatility."
                            }
                        ]
                    }
                }
            ]
        }


class TestDiverseRisk(unittest.TestCase):
    def setUp(self) -> None:
        settings = Settings(database_path=":memory:", enable_yfinance_fallback=False, gemini_api_key=None)
        self.client = TestClient(create_app(settings=settings))
        self.dates = [(datetime(2026, 1, 2) + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(25)]

    def _sample_maps(self):
        a_px, b_px, c_px, cand_px = {}, {}, {}, {}
        pa, pb, pc, pd_ = 100.0, 100.0, 50.0, 200.0
        for i, d in enumerate(self.dates):
            r_a = 0.02 if i % 2 == 0 else -0.015
            r_b = -0.018 if i % 2 == 0 else 0.022
            r_cand = -0.012 if i % 2 == 0 else 0.015
            pa *= 1.0 + r_a
            pb *= 1.0 + r_b
            pc *= 1.0 + r_a
            pd_ *= 1.0 + r_cand
            a_px[d], b_px[d], c_px[d], cand_px[d] = round(pa, 4), round(pb, 4), round(pc, 4), round(pd_, 4)
        return {"XNAS:AAPL": a_px, "XSTC:FPT": b_px, "XNAS:MSFT": c_px}, {"XSWX:NESN": cand_px}

    def test_rejects_more_than_10_stocks(self) -> None:
        maps = {f"XNAS:S{k}": {d: 100.0 + i for i, d in enumerate(self.dates)} for k in range(11)}
        r = self.client.post("/api/v1/portfolio/diverse-risk", json={"asset_price_maps": maps})
        self.assertEqual(r.status_code, 400)
        self.assertIn("between 2 and 10", r.json()["detail"])

    def test_detects_strong_risk_reduction_and_candidate_suggestions(self) -> None:
        sel, cand = self._sample_maps()
        r = self.client.post(
            "/api/v1/portfolio/diverse-risk",
            json={"asset_price_maps": sel, "candidate_price_maps": cand},
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

    def test_diverse_risk_advisor_deterministic_and_llm_paths(self) -> None:
        sel, cand = self._sample_maps()
        dr_resp = analyze_diverse_risk(DiverseRiskRequest(asset_price_maps=sel, candidate_price_maps=cand))

        # 1. Deterministic path via FastAPI endpoint (no GEMINI_API_KEY)
        api_res = self.client.post(
            "/api/v1/portfolio/diverse-risk/ask",
            json={
                "question": "Which sectors should I combine to minimize risk?",
                "analysis": json.loads(dr_resp.json()),
            },
        )
        self.assertEqual(api_res.status_code, 200)
        det = api_res.json()
        self.assertFalse(det["used_llm"])
        self.assertIn("Technology", det["sector_breakdown"])
        self.assertIn("Consumer Defensive", det["missing_defensive_sectors"])
        self.assertGreaterEqual(len(det["recommended_actions"]), 1)

        # 2. Grounded Gemini LLM path (mocked HTTP)
        llm_res = ask_diverse_risk_advisor(
            DiverseRiskAdvisorRequest(question="Best stocks to combine?", analysis=dr_resp),
            gemini_api_key="test-gemini-key",
            http_post=lambda *args, **kwargs: _FakeGeminiResp(),
        )
        self.assertTrue(llm_res.used_llm)
        self.assertIn("gemini", llm_res.engine_used.lower())
        self.assertIn("XSWX:DEF", llm_res.answer)



    def test_market_sector_blueprints(self) -> None:
        for scope in ("US", "VN", "US_VN", "GLOBAL"):
            r = self.client.get(f"/api/v1/portfolio/diverse-risk/blueprint?market_scope={scope}")
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual(body["market_scope"], scope)
            self.assertGreaterEqual(len(body["recommended_blueprints"]), 2)
            self.assertGreaterEqual(len(body["sectors"]), 2)


if __name__ == "__main__":
    unittest.main()
