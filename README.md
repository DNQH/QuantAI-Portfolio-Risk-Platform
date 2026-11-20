# QuantAI — Global Quantitative Investment Research, Portfolio Optimization & Financial Risk Management Platform

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-3776AB)
![React](https://img.shields.io/badge/react-18%20%2B%20TypeScript-61DAFB)

## Project Overview
**QuantAI** is a full-stack, modular quantitative investment research, portfolio optimization, financial risk management, machine learning forecasting, and strategy backtesting platform for global equity markets. Designed as an institutional-grade technical portfolio project for Finance, Quantitative Finance, and Financial Engineering applications, QuantAI prioritizes **genuine market data provenance**, **verified financial mathematics**, **leakage-free ML validation**, and **bias-free backtesting**.

## Key Features (Phases 1–8 Complete)
1. **Global Market Data Center ($0 Free Stack + Extensible Paid Hooks):**
   - Multi-provider abstraction (`BaseMarketDataProvider`) with Finnhub (US real-time quotes & WebSocket), Vnstock v6 (Vietnam HOSE/HNX), SSI FastConnect V3 (Vietnam live streaming with SSI credentials), Frankfurter v2 (all 15 target FX currencies as `DAILY_REFERENCE`), and explicitly labeled `yfinance` educational historical fallback, plus drop-in hooks for EODHD, Twelve Data, and Massive.
   - Strict provenance tags (`LIVE`, `DELAYED`, `HISTORICAL`, `DAILY_REFERENCE`, `DATA_UNAVAILABLE`) with dual timestamps (`market_timestamp` and `retrieval_timestamp`) and zero silent fallback.
   - Effective-dated ISO 10383 MIC symbology covering US, Vietnam (including the scheduled **December 28, 2026 HNX-to-HOSE consolidation**), Europe, Asia, ASEAN, and Australia.
2. **Quantitative Analysis (`backend/app/analytics/`):** Simple/log/cumulative/annualized returns, rolling & annualized volatility (`ddof=1`), Sharpe & Sortino ratios, Maximum Drawdown + recovery bars, SMA (20/50/100/200), EMA (12/26), canonical Wilder RSI (14), MACD (12/26/9), ROC, Bollinger Bands, ATR (14), unbiased skewness/kurtosis, and aligned correlation & annualized covariance matrices.
3. **Portfolio Optimization & Multi-Currency FX (`backend/app/portfolio/`):** SciPy SLSQP Mean-Variance Optimization, Efficient Frontier, Global Minimum Variance (GMV), Maximum Sharpe Portfolio, marginal/percentage risk contributions, CAPM Beta & Jensen's Alpha, exact FX return decomposition `(1 + r_local)(1 + r_fx) - 1`, and SQLite portfolio persistence.
4. **Financial Risk Management (`backend/app/risk/`):** Historical VaR/CVaR, Parametric Normal VaR/CVaR, deterministic seeded Monte Carlo VaR/CVaR (95% & 99%), Tracking Error, Information Ratio, deterministic Stress Testing scenarios, and currency exposure breakdown.
5. **Machine Learning & Forecasting (`backend/app/forecasting/`):** Chronological train/test split, train-only feature scaling (zero leakage), expanding-window walk-forward CV, and 6 genuinely trained models (`naive_last_price`, `naive_historical_mean`, `ridge_regression`, `arima_ar4_returns`, `random_forest`, `gradient_boosting`) evaluated by MAE, RMSE, MAPE, R², and residuals — zero fabricated confidence scores.
6. **Quantitative Signals & Backtesting (`backend/app/backtesting/`):** Inspectable rules-based signals (RSI, MACD, SMA crossover, Momentum, Volatility) + strict T+1 bias-free historical strategy backtester (SMA Crossover, RSI Mean Reversion, Buy & Hold) with configurable commission and slippage bps.

## Architecture & Technology Stack
- **Backend:** Python 3.11+, FastAPI, Pydantic, Uvicorn, httpx, SQLite, NumPy, Pandas, SciPy
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TradingView Lightweight Charts, Recharts
- **CI & Testing:** GitHub Actions (`.github/workflows/ci.yml`), `unittest` / `pytest` (25 automated unit & API tests)
- **Documentation:** [`docs/architecture.md`](docs/architecture.md), [`docs/data_sources.md`](docs/data_sources.md), [`docs/financial_formulas.md`](docs/financial_formulas.md), [`docs/phase1_acceptance.md`](docs/phase1_acceptance.md), [`PROJECT_STATUS.md`](PROJECT_STATUS.md), [`CHANGELOG.md`](CHANGELOG.md)

## Quick Start (Local Development)

```bash
# 1. Configure environment variables (NEVER commit .env)
cp .env.example .env

# 2. Run Backend API & Swagger Docs (Terminal 1)
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install "vnstock>=6.0" yfinance websockets scikit-learn statsmodels
uvicorn app.main:app --reload --port 8000
```
Interactive OpenAPI / Swagger docs: `http://127.0.0.1:8000/docs`

```bash
# 3. Run All 25 Automated Tests
cd backend
python3 -m unittest discover -s tests -v
```

```bash
# 4. Run Frontend Dashboard (Terminal 2)
cd frontend
npm install
npm run dev
```
Dashboard URL: `http://localhost:5173`

## Known Limitations & Disclaimer
- Free-tier APIs do not grant unrestricted commercial real-time global equity redistribution; see [`docs/data_sources.md`](docs/data_sources.md) for exact permissions and paid upgrade paths.
- All analytics, forecasts, and backtests are for quantitative research and education only and do **not** constitute investment advice or guarantee future returns.
