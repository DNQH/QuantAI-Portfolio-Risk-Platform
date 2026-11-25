"""Public-deployment features: single-origin UI serving and API rate limiting."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.ratelimit import DailyBudget, SlidingWindowLimiter
from app.main import create_app


def _settings(**overrides) -> Settings:
    base = dict(database_path=":memory:", enable_yfinance_fallback=False, gemini_api_key=None)
    base.update(overrides)
    return Settings(**base)


# ------------------------------------------------------------------ limiter units

def test_sliding_window_limiter_blocks_then_recovers() -> None:
    now = [1000.0]
    lim = SlidingWindowLimiter(limit=2, window_seconds=60, clock=lambda: now[0])
    assert lim.hit("a") == (True, 0.0)
    assert lim.hit("a") == (True, 0.0)
    allowed, retry = lim.hit("a")
    assert not allowed and retry == 60.0
    assert lim.hit("b")[0], "limits are per client"
    now[0] += 30
    allowed, retry = lim.hit("a")
    assert not allowed and retry == 30.0
    now[0] += 30.01
    assert lim.hit("a")[0], "window slid past the first hits"


def test_zero_limit_disables_rule() -> None:
    lim = SlidingWindowLimiter(limit=0, window_seconds=60)
    assert all(lim.hit("x")[0] for _ in range(1000))
    assert all(DailyBudget(0).consume() for _ in range(1000))


def test_daily_budget_resets_on_new_utc_day() -> None:
    day = ["2026-11-25"]
    budget = DailyBudget(2, today=lambda: day[0])
    assert budget.consume() and budget.consume()
    assert not budget.consume()
    day[0] = "2026-11-26"
    assert budget.consume()


# ------------------------------------------------------------- middleware wiring

def test_rate_limiting_disabled_outside_production_by_default(monkeypatch) -> None:
    monkeypatch.delenv("QUANTAI_RATE_LIMIT_ENABLED", raising=False)
    monkeypatch.setenv("QUANTAI_ENV", "development")
    assert _settings().rate_limit_enabled is False
    monkeypatch.setenv("QUANTAI_ENV", "production")
    assert _settings().rate_limit_enabled is True


def test_general_limit_returns_429_with_retry_after_and_exempts_health() -> None:
    c = TestClient(create_app(settings=_settings(rate_limit_enabled=True, rate_limit_per_minute=3)))
    codes = [c.get("/api/v1/fx/currencies").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    r = c.get("/api/v1/fx/currencies")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert "detail" in r.json()
    assert all(c.get("/api/v1/health").status_code == 200 for _ in range(10))


def test_heavy_and_assistant_limits() -> None:
    app = create_app(
        settings=_settings(
            rate_limit_enabled=True,
            rate_limit_per_minute=1000,
            rate_limit_heavy_per_minute=2,
            assistant_per_minute=100,
            assistant_daily_budget=1,
        )
    )
    c = TestClient(app)
    # Invalid bodies are fine: the limiter runs before request validation.
    heavy = [c.post("/api/v1/forecasting/run", json={}).status_code for _ in range(3)]
    assert heavy[:2] != [429, 429] and heavy[2] == 429
    first = c.post("/api/v1/portfolio/diverse-risk/ask", json={}).status_code
    second = c.post("/api/v1/portfolio/diverse-risk/ask", json={})
    assert first != 429
    assert second.status_code == 429 and "daily" in second.json()["detail"]
    # Cheap endpoints are unaffected by the heavy / assistant buckets.
    assert c.get("/api/v1/fx/currencies").status_code == 200


# ------------------------------------------------------------------- UI serving

def _fake_dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir(parents=True)
    (tmp_path / "index.html").write_text("<!doctype html><title>QuantAI UI</title>")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log('ui')")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    return tmp_path


def test_frontend_served_from_same_origin(tmp_path: Path) -> None:
    c = TestClient(create_app(settings=_settings(frontend_dist=str(_fake_dist(tmp_path)))))

    root = c.get("/")
    assert root.status_code == 200 and "QuantAI UI" in root.text
    assert root.headers["cache-control"] == "no-cache"

    asset = c.get("/assets/index-abc123.js")
    assert asset.status_code == 200 and "immutable" in asset.headers["cache-control"]

    assert c.get("/favicon.svg").text == "<svg/>"
    assert "QuantAI UI" in c.get("/some/client/route").text  # SPA fallback

    # API routes still win, and unknown API paths stay JSON 404s.
    assert c.get("/api/v1/health").json()["status"]
    missing = c.get("/api/v1/does-not-exist")
    assert missing.status_code == 404 and missing.headers["content-type"].startswith("application/json")
    assert c.get("/assets/missing.js").status_code == 404


def test_frontend_cannot_escape_dist(tmp_path: Path) -> None:
    dist = _fake_dist(tmp_path / "dist")
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    c = TestClient(create_app(settings=_settings(frontend_dist=str(dist))))
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        assert "TOP SECRET" not in c.get(path).text


def test_no_frontend_configured_means_api_only(tmp_path: Path) -> None:
    c = TestClient(create_app(settings=_settings()))
    assert c.get("/").status_code == 404
    c2 = TestClient(create_app(settings=_settings(frontend_dist=str(tmp_path))))  # no index.html
    assert c2.get("/").status_code == 404
