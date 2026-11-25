# QuantAI — Global Portfolio Risk Optimization & Financial Risk Management Platform

[[https://img.shields.io/badge/version-4.1.0-2563EB](https://img.shields.io/badge/version-4.1.0-2563EB)]
[[https://img.shields.io/badge/license-MIT-10B981](https://img.shields.io/badge/license-MIT-10B981)]
[[https://img.shields.io/badge/python-3.11%2B-3776AB](https://img.shields.io/badge/python-3.11%2B-3776AB)]
[[https://img.shields.io/badge/react-18%20%2B%20TypeScript-61DAFB](https://img.shields.io/badge/react-18%20%2B%20TypeScript-61DAFB)]

## Project Overview

**QuantAI** is a full-stack, institutional-grade **portfolio risk optimization, systemic macro-risk tracking, and corporate credit risk management platform** for global equity markets. Built as a technical portfolio project for Master's applications in **Finance, Quantitative Finance, Financial Engineering, and Financial Risk Management**, QuantAI combines verified financial mathematics (SciPy SLSQP, Black-Scholes-Merton, Altman Z-Score, Ohlson O-Score, VaR/CVaR, Monte Carlo simulation) with transparent market data provenance and a live multi-turn AI strategist.

## Core Capabilities (v4.1.0)

1. **Global Portfolio Risk Workbench (`backend/app/portfolio/`):**
   - Multi-market portfolio construction across the United States, Vietnam and Italy covering **all 11 GICS sectors**, with pre-built low-correlation sector pairings and full custom ticker selection.
   - Hypothetical capital deployment simulator supporting up to **1,000,000,000** across 8 currencies (`USD`, `VND`, `EUR`, `GBP`, `JPY`, `SGD`, `AUD`, `HKD`).
   - SciPy SLSQP **Minimum Variance (GMV)**, **Maximum Sharpe**, and **Equal-Weight** optimization visualized via an interactive allocation Pie Chart, exact per-stock capital weights, Diversification Ratio, and Volatility Reduction %.
   - Integrated **10-Year Historical Performance Proof** (equity curve vs. Equal-Weight Buy & Hold, CAGR, Sharpe, Max Drawdown, calendar-year breakdown) plus **5,000-path seeded Monte Carlo Forward Scenario Forecasts** (1Y / 3Y / 5Y Bear, Base, and Bull regimes).
   - **Multi-Turn Conversational AI Assistant** powered by **Gemini 3.1 Flash Lite**, grounded in live portfolio weights, sector exposure, and 10-year risk metrics.

2. **Macro & Systemic Risk Tracker (`backend/app/risk/tracker.py`):**
   - Tracks 5 active systemic risk regimes (Higher-for-Longer Rates, Trade Tariffs & FX Volatility, Energy/Inflation Shocks, Credit & Refinancing Stress, and AI Valuation Cycles) across all **11 GICS sectors**.
   - Ranks sectors and individual stocks from **Most Severely Impacted (`SEVERE`) to Most Resilient (`LOW / RESILIENT`)**, documenting **10-year historical impact episodes (2016-2026)**, 12-36 month forward outlook, and **5 Emerging Future Risk Hypotheses** with defensive hedging guidance.

3. **Financial Risk Analytics & 4-Stage Corporate Bankruptcy Pipeline (`backend/app/risk/`):**
   - Plain-English **Market Downside Risk**: Historical, Parametric Normal, and deterministic seeded Monte Carlo **VaR & CVaR (Expected Shortfall)** at 95% and 99% confidence, plus historical crisis Stress Testing (2008 GFC, 2020 Liquidity Shock, Rate Shock, EM FX Depreciation).
   - **4-Stage Corporate Bankruptcy & 12-Month Default Probability (PD) Pipeline**: Corporate Financial Statements -> Liquidity/Leverage/Profitability/Cash-Flow Ratios -> **7 Credit Models** (*Altman Z-Score*, *Ohlson O-Score*, *Merton Structural Distance-to-Default*, *DSCR*, *Interest Coverage*, *Logistic Regression PD*, and *XGBoost / Gradient Boosted Trees PD*) -> **Ensemble 12M PD %** & Credit Risk Grade.

4. **Crowd Sentiment & Prediction Markets — "What People Think?" (`backend/app/sentiment/`):**
   - Aggregates live prediction-market probabilities from **Polymarket (Gamma API)** alongside social/news discussions from **Reddit** and **Finnhub Company News**.
   - Computes a transparent **Bayesian-Logistic Horizon Sentiment Model** (`1W`, `1M`, `3M`) outputting a directional verdict (`POSITIVE` / `NEUTRAL` / `NEGATIVE`) and implied positive outlook probability.

5. **Global Market Data Explorer & FX Converter (`backend/app/data/`, `backend/app/fx/`):**
   - Cascading Country -> Exchange selector (**NYSE, NASDAQ, HOSE, HNX, UPCOM, Borsa Italiana**) with flagship stocks per exchange and **live global autocomplete search** across tens of thousands of listed equities.
   - Multi-provider architecture (`Finnhub`, `Twelve Data`, `SSI FastConnect Data`, `VNDirect dchart`, `TCBS`, `Vnstock v6`, `yfinance` educational fallback, and `Frankfurter v2` FX rates) with strict provenance tags (`LIVE`, `DELAYED`, `HISTORICAL`, `DAILY_REFERENCE`, `DATA_UNAVAILABLE`) and effective-dated ISO 10383 MIC symbology (including the scheduled **December 28, 2026 HNX-to-HOSE consolidation**).
   - Full IPO-to-present interactive candlestick charts (`1m` to `1mo`) with Volume Histogram and direct navigation to `Risk Analytics`.

## Architecture & Technology Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic, Uvicorn, httpx, SQLite, NumPy, Pandas, SciPy, scikit-learn / XGBoost *(also includes tested modular `analytics/`, `forecasting/`, and `backtesting/` REST APIs)*
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TradingView Lightweight Charts, Recharts
- **CI & Automated Testing:** GitHub Actions (`.github/workflows/ci.yml`) — Python 3.11 & 3.13 matrix with `ruff` lint and **78 pytest unit, regression & API tests** + Docker build smoke test + strict TypeScript & Vite production build (code-split, no chunk > 500 kB)
- **Documentation:** `docs/architecture.md`, `docs/data_sources.md`, `docs/financial_formulas.md`, `CHANGELOG.md`

## Quick Start (Local)

1. **Backend:** `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python -m uvicorn app.main:app --reload --port 8000`
2. **Frontend (new terminal):** `cd frontend && npm install && npm run dev`
3. Open `http://localhost:5173`. Run tests anytime via `cd backend && pip install -r requirements-dev.txt && python -m pytest -q && ruff check .`.

### Run as a single container (production mode)

```bash
docker build -t quantai . && docker run --rm -p 8000:8000 quantai
```

Open `http://localhost:8000`: the API also serves the built UI, with per-IP rate limits on.

## Deploy to the Web

The repository includes a `Dockerfile` (API + UI on one port) and a Render Blueprint
(`render.yaml`). On Render: **New → Blueprint → select this repo → Apply**. Full guide,
configuration table and known limitations: [`docs/deployment.md`](docs/deployment.md).
