# Changelog

All notable changes to **QuantAI** are documented in this file.

## [Unreleased]
### Fixed
- **SSI FastConnect adapter rewritten for the real FC Data API v2.** The previous adapter
  called endpoints that do not exist (`/api/v3/auth/token` with `apiKey`/`apiSecret`,
  `/market/quote`), so Vietnam quotes could never be LIVE even with valid credentials. It now:
  authenticates via `POST api/v2/Market/AccessToken` (`consumerID`/`consumerSecret`) with JWT
  expiry-aware token caching and one re-auth on HTTP 401; takes the last matched trade from
  `Market/IntradayOhlc` (LIVE only if the trade is <= 3 min old during the session, otherwise
  DELAYED with its real age); and serves daily history from `Market/DailyOhlc` (yearly windows,
  paginated). HOSE, HNX and UPCOM are covered; SSI is now the first source for Vietnam daily
  history when configured. Verified against SSI's documentation and the official `ssi-fc-data`
  SDK with 11 fake-server tests; not yet exercised against SSI with real credentials.
- **Misleading LIVE badges in Market Data Coverage:** a Twelve Data or EODHD API key alone
  flipped LSE, Xetra, TSE, HKEX, SGX and ASX to **LIVE** ("Twelve Data (Live Global)"), although
  quotes for those exchanges are always served by yfinance (delayed) and the paid quote
  adapters are placeholders. LIVE now requires a configured provider whose real-time quote
  adapter is implemented (`live_quotes_implemented`); otherwise the row shows
  `yfinance (Delayed)` and notes that Twelve Data is used only as a historical-bars backup.
  US (Finnhub) and Vietnam (SSI) labelling is unchanged.
- **Hermetic tests:** the suite now ignores the developer's `.env` and inherited provider keys
  (`QUANTAI_DISABLE_DOTENV`), so local API keys can no longer change results or be spent by
  tests (a real Gemini call previously ran from the assistant test).

### Changed
- SSI credentials are now `SSI_CONSUMER_ID` / `SSI_CONSUMER_SECRET` (legacy `SSI_API_KEY` /
  `SSI_API_SECRET` still accepted). Provider id `ssi_fastconnect_v3` renamed to
  `ssi_fastconnect_data` (also the key in `/api/v1/health` `configured_providers`).
- **Market Data Coverage UI:** the "Feed Status" column is now "Best Available Feed", with an
  explainer that LIVE applies while the exchange is open (other pages show each quote's real
  age, e.g. `DELAYED (968m)` before the US open); provider notes appear as a tooltip.
- `render.yaml` / `docs/deployment.md`: `TWELVEDATA_API_KEY` documented as a historical-data
  backup and `EODHD_API_KEY` as reserved; neither makes non-US markets LIVE.

## [4.1.0] - 2026-11-25
Quant-correctness, robustness, UI and public-deployment release. Public API shapes are
backward compatible (only optional fields were added; `key_prefix` was removed from
`/assistant/status`). Release notes:
https://github.com/DNQH/QuantAI-Portfolio-Risk-Platform/releases/tag/v4.1.0

### Added — public web deployment
- **Single-container deployment:** multi-stage `Dockerfile` builds the React UI and serves it
  from FastAPI on one port (`QUANTAI_FRONTEND_DIST`), with immutable caching for hashed
  assets, SPA fallback, JSON 404s for unknown `/api` paths, non-root user, `$PORT` support,
  proxy-header handling and a Docker `HEALTHCHECK`.
- **Render Blueprint** (`render.yaml`) and `docs/deployment.md` step-by-step guide.
- **Per-client-IP rate limiting** (`app/core/ratelimit.py`), on by default when
  `QUANTAI_ENV=production`: general API, heavy analytics endpoints, and the Gemini assistant
  (per-minute plus a global daily budget). Returns `429` with `Retry-After`.
- `backend/requirements-deploy.txt` (runtime + yfinance) and a CI job that builds the image.

### Fixed — user interface
- **Narrow screens:** the fixed 256 px sidebar left ~150 px for content on phone-width
  viewports. Below the `md` breakpoint it now collapses into a top bar with a horizontally
  scrollable tab strip that keeps the active tab in view; the desktop sidebar is sticky.
- **Tab lost on refresh:** the active tab lived only in React state, so every reload jumped
  back to Overview. It is now mirrored to the URL hash (e.g. `#risk-analytics`), enabling
  refresh persistence, browser Back/Forward and deep links; the page title follows the tab.

### Fixed — quantitative correctness
- **Portfolio backtest look-ahead bias:** optimised weights were calibrated on the first
  252 returns and then applied from day 0. Weights are now estimated walk-forward from
  returns known at each formation/rebalance close, after an estimation-only warm-up.
- **Portfolio transaction costs** were charged on half the traded notional and the initial
  purchase was free; costs now apply to the full buy + sell notional, including entry, for
  both portfolio and benchmark.
- **Calendar-year returns** omitted the first trading day of every year (base was the first
  close of the year instead of the last close of the previous year).
- **Annualisation:** portfolio backtests hard-coded 252 bars/year and `n/252` years; they now
  use calendar years and the empirical bar frequency. Single-asset analytics default the
  factor by interval (`1wk` = 52, `1mo` = 12) instead of always 252.
- **Rebalancing** is calendar-based (first trading day of each quarter/year) instead of
  every 63/252 bars.
- **Forward Monte Carlo** double-counted volatility drag (`CAGR - sigma^2/2` used as GBM drift
  on an already-geometric CAGR); the median path now compounds at the shrunk CAGR.
- **Efficient frontier** targeted `max(mu)`, unattainable when `max_weight < 1` (8 of 12 points
  were silently dropped in a reference case); the upper bound is now solved as a linear program.
- **Historical VaR horizon scaling** scaled the mean by `sqrt(T)` (parametric used `T`);
  CVaR now uses the Acerbi-Tasche tail-mass estimator.
- **Sharpe/Sortino** returned ~1e16 for constant series (float std ~1e-19 passed an `== 0` guard).
- **ATR** mixed raw highs/lows with adjusted closes (spikes at splits/dividends).
- **Ohlson O-Score** size term depended on the reporting currency (VND vs USD shifted O by ~4.1);
  it now uses USD-normalised assets deflated by the GNP price index.
- **Merton DD** treated debt as riskless; now the naive Bharath-Shumway asset volatility.
- **Credit ratios** with zero denominators divided by "one currency unit"; debt-free firms
  crashed the bankruptcy endpoint with `OverflowError` (HTTP 500).
- **Diverse-risk candidate additions** computed candidate returns on the candidate's own
  calendar before joining (mixed 1-day and multi-day returns); prices are now aligned first.
- **Single-asset backtest benchmark** was filled one bar before any strategy could trade.
- **Rolling volatility** skipped the first full window; **drawdown** crashed on missing prices.
- **Crowd-sentiment momentum** (frontend) received the ~2-year total return as the 20-day return.

### Added
- Ledoit-Wolf covariance shrinkage (`covariance_method`: `auto` | `sample` | `ledoit_wolf`) with
  automatic fallback for singular / ill-conditioned covariance; `covariance_estimator`,
  `shrinkage_intensity`, `optimizer_warnings` response fields.
- Portfolio backtest fields `periods_per_year`, `warmup_observations`,
  `asset_annualized_volatility`.
- Shared OHLCV input hygiene (`app/analytics/bars.py`) for all bar-based endpoints
  (dedupe, sort, drop NaN/inf/non-positive bars).
- 31 regression tests (`backend/tests/test_v41_quant_regressions.py`) with closed-form answers.

### Security & operations
- `/assistant/status` no longer leaks the first characters of `GEMINI_API_KEY`.
- CORS: `allow_credentials=False`, explicit methods/headers (credentials + wildcard origin
  would reflect any origin).
- `.env` no longer overrides non-empty real environment variables.
- Gemini advisor calls bounded by a 30 s total budget (worst case was minutes per message).
- yfinance financial statements bounded by a 15 s timeout; boosted-tree PD model trained once
  per process instead of per request.
- WebSocket quote refreshes run in the threadpool (blocking HTTP no longer stalls the event loop).
- SQLite: busy timeout, WAL, rollback on error; in-memory connection guarded by a lock.
- Validation: FX attribution returns >= -100 %, CAPM finite inputs, VaR confidence levels,
  constant-price series rejected with 400 instead of NaN JSON.

### Engineering
- `requirements.txt` (bounded runtime ranges) split from `requirements-dev.txt` (pytest, ruff).
- CI: Python 3.11 + 3.13 matrix, pip/npm caching, `ruff check`, `pytest`, `npm ci`.
- `backend/pyproject.toml` with ruff and pytest configuration; tests use a temp SQLite DB.
- Frontend: `React.lazy` code-splitting of heavy panels + vendor chunks; largest chunk
  437 kB (was a single 833 kB chunk); typed `ApiError` with server `detail`, request
  timeouts, stale-response guards on instrument switches; removed `any` casts.
- Single version source: `backend/app/__init__.py` / `frontend/src/version.ts` = 4.1.0.

## [0.2.0-phase2] - 2026-11-20
### Added
- **Phase 2 — Quantitative Analysis Engine (`backend/app/analytics/`):**
  - Return analysis: simple, log, cumulative, and annualized returns.
  - Technical & volatility indicators: SMA (20/50/100/200), EMA (12/26), Wilder RSI (14), MACD (12/26/9), Rate of Change (ROC), Bollinger Bands (20, 2σ), Average True Range (ATR 14), and rolling/annualized historical volatility.
  - Statistical & risk-adjusted metrics: mean, median, variance, standard deviation, skewness, kurtosis, Sharpe ratio, Sortino ratio, and maximum drawdown (with drawdown series and recovery days).
  - Multi-asset analysis: aligned Pearson correlation matrix and annualized sample covariance matrix.
  - FastAPI endpoints: `POST /api/v1/analytics/single-asset` and `POST /api/v1/analytics/matrix`.
- **Frontend Quantitative Research Module & Theme Toggle:**
  - Added Quantitative Research view with Recharts cumulative return & drawdown charts, indicator summary cards, and correlation matrix table.
  - Added institutional Dark / Light theme toggle.
- **GitHub Release & Governance Docs:** Added `PROJECT_STATUS.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/architecture.md`, and `docs/financial_formulas.md`.
- **Automated Tests:** Added `backend/tests/test_phase2_analytics.py` validating all formulas against independently computed test cases.

## [0.1.0-phase1] - 2026-11-20
### Added
- **Phase 1 — Core Foundation:** Modular FastAPI backend, SQLite persistence, ISO 10383 MIC symbology with effective-dated HNX-to-HOSE (Dec 28, 2026) mapping, global exchange calendar, Data Freshness State Machine, $0 free-stack providers (Finnhub, Vnstock v6, SSI FastConnect V3, Frankfurter v2, yfinance educational fallback, paid extension stubs), English-only React/TypeScript/Tailwind terminal UI, and 12 automated tests.
