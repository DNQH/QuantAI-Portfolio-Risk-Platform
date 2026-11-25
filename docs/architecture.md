# QuantAI Architecture

QuantAI separates external market data acquisition, quantitative finance computation, persistence, and user interface rendering into four decoupled layers.

## Repository Layout
```text
quantai/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI REST & WebSocket routers (OpenAPI / Swagger)
│   │   ├── core/         # Env config, Pydantic schemas, SQLite DB, MIC symbology, market calendars
│   │   ├── data/         # BaseMarketDataProvider, Freshness State Machine, multi-provider router
│   │   │   └── providers/# Finnhub, Vnstock v6, SSI FastConnect Data, yfinance fallback, paid stubs
│   │   ├── fx/           # Frankfurter v2 daily reference FX engine (15 target currencies)
│   │   ├── analytics/    # Phase 2: Returns, indicators, statistics, Sharpe/Sortino, drawdown, matrices
│   │   ├── portfolio/    # Phase 3: MPT Efficient Frontier, Min-Var, Max-Sharpe, CAPM
│   │   ├── risk/         # Phase 4: Historical/Parametric/Monte Carlo VaR, CVaR, Stress Testing
│   │   ├── forecasting/  # Phase 5: Leakage-free ML baselines, RF, GB, ARIMA
│   │   ├── backtesting/  # Phase 6: Event-driven T+1 strategy backtester with fees & slippage
│   │   └── main.py       # FastAPI application factory, structured logging, global error handlers
│   ├── tests/            # Unit & FastAPI integration test suites (unittest & pytest compatible)
│   └── requirements.txt
├── frontend/             # React + TypeScript + Vite + Tailwind CSS + Recharts + Lightweight Charts
├── docs/                 # Architecture, verified data sources, financial formulas, acceptance criteria
├── PROJECT_STATUS.md     # Living continuity tracker for incremental development
├── CONTRIBUTING.md
├── CHANGELOG.md
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Key Architectural Decisions
1. **Server-Side Quantitative Math:** All financial calculations run in Python (`NumPy`, `Pandas`, `SciPy`) so REST clients, unit tests, and the React UI consume identical, reproducible values.
2. **Strict Provenance & Zero Silent Fallback:** Every market payload carries `data_status` (`LIVE`, `DELAYED`, `HISTORICAL`, `DAILY_REFERENCE`, `DATA_UNAVAILABLE`), `market_timestamp`, and `retrieval_timestamp`.
3. **Effective-Dated Symbology:** Securities are keyed by ISO 10383 MIC + ticker (e.g., `XNAS:AAPL`, `XSTC:FPT`, `XHAI:SHS`) with date-aware routing for Vietnam's scheduled December 28, 2026 HNX-to-HOSE consolidation.
4. **Database Portability:** SQLite is used for zero-config local setup with standard SQL schemas designed for straightforward PostgreSQL / SQLAlchemy migration.
