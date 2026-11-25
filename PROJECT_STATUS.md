# QuantAI Project Status & Continuity Log

**Last Updated:** 2026-11-25  
**Current Version:** `v4.1.0` (quant-correctness & hardening release, see `CHANGELOG.md`)  
**Test Suite Status:** 78/78 backend unit, regression & FastAPI integration tests passing under `pytest`; `ruff check` clean; frontend `npm run build` clean (no chunk > 500 kB).

## Completed Phases
- **Phase 0:** Prototype audit & global market data provider evaluation.
- **Phase 1:** Modular FastAPI + React + SQLite core foundation, $0 free stack providers, Data Freshness State Machine, effective-dated HNX-to-HOSE (Dec 28, 2026) mapping, and Market Data Coverage registry.
- **Phase 2:** Quantitative Analysis Engine (`backend/app/analytics/`) — returns, volatility, Sharpe, Sortino, drawdown, SMA/EMA, Wilder RSI, MACD, ROC, Bollinger Bands, ATR, skewness/kurtosis, correlation & covariance matrices.
- **Phase 3:** Portfolio Optimization (`backend/app/portfolio/optimizer.py`) — SciPy SLSQP GMV, Max-Sharpe, Efficient Frontier, risk contributions, CAPM Beta/Alpha, FX return attribution, SQLite CRUD.
- **Phase 4:** Risk Management (`backend/app/risk/engine.py`) — Historical, Parametric Normal, and Seeded Monte Carlo VaR/CVaR (95%/99%), Tracking Error, Information Ratio, Stress Testing, Currency Exposure.
- **Phase 5:** Machine Learning & Forecasting (`backend/app/forecasting/models.py`) — chronological split, train-only scaling, walk-forward CV, Naive/Ridge/ARIMA-AR4/Random Forest/Gradient Boosting with MAE/RMSE/MAPE/R² and zero fake confidence scores.
- **Phase 6:** Quantitative Signals & Bias-Free Strategy Backtesting (`backend/app/backtesting/engine.py`) — inspectable rules-based signals + T+1 execution backtester with commission, slippage, and Buy-and-Hold benchmark.
- **Phase 7:** Global Expansion (`backend/app/core/symbology.py`) — Market coverage focused on the United States (NYSE, NASDAQ), Vietnam (HOSE, HNX, UPCOM) and Italy (Borsa Italiana / Euronext Milan) with ISO 10383 MIC codes and yfinance suffixes.
- **Phase 8:** GitHub Release Preparation — `.github/workflows/ci.yml`, `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`, `.env.example`, `.gitignore`, complete `docs/`, local Git repository initialized on `main` branch with zero secrets.
