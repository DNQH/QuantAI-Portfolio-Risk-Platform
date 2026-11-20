# Changelog

All notable changes to **QuantAI** are documented in this file.

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
