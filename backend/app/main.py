"""FastAPI application entry point for QuantAI v1.0.0."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as v1_router
from app.core.config import Settings, get_settings
from app.core.database import DatabaseManager
from app.data.registry import MarketDataRegistry
from app.portfolio.optimizer import PortfolioStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("quantai")


def create_app(
    settings: Optional[Settings] = None,
    registry: Optional[MarketDataRegistry] = None,
) -> FastAPI:
    cfg = settings or get_settings()
    db = DatabaseManager(cfg.database_path)
    db.init_db()

    app = FastAPI(
        title="QuantAI — Global Quantitative Investment Research, Portfolio & Risk API",
        version="1.0.0",
        description=(
            "Full-stack quantitative finance platform: verified global market data, "
            "quantitative analysis, MPT portfolio optimization, VaR/CVaR risk management, "
            "leakage-free ML forecasting, and bias-free strategy backtesting."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        logger.warning("Validation error: %s", exc)
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Inspect backend logs for diagnostics."},
        )

    app.state.settings = cfg
    app.state.db = db
    app.state.registry = registry or MarketDataRegistry(settings=cfg)
    app.state.portfolio_store = PortfolioStore(db)

    app.include_router(v1_router)
    logger.info("QuantAI API initialized (version=%s, env=%s)", app.version, cfg.environment)
    return app


app = create_app()
