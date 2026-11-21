"""FastAPI REST and WebSocket endpoints for QuantAI v1.3.0."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.analytics.engine import (
    MatrixAnalyticsRequest,
    MatrixAnalyticsResponse,
    SingleAssetAnalyticsRequest,
    SingleAssetAnalyticsResponse,
    run_matrix_analytics,
    run_single_asset_analytics,
)
from app.backtesting.engine import (
    PortfolioBacktestRequest,
    PortfolioBacktestResponse,
    run_portfolio_backtest,
    BacktestRequest,
    BacktestResponse,
    SignalsResponse,
    evaluate_quantitative_signals,
    run_backtest,
)
from app.core.calendar import get_market_session
from app.core.models import (
    ExchangeCoverageEntry,
    FXConversionResponse,
    FXRatesResponse,
    HealthResponse,
    Instrument,
    MarketSessionInfo,
    OHLCVBar,
    OHLCVResponse,
    QuoteResponse,
)
from app.core.symbology import parse_instrument_id, resolve_effective_exchange
from app.data.registry import MarketDataRegistry
from app.forecasting.models import ForecastRequest, ForecastResponse, run_forecasting_suite
from app.fx.frankfurter import TARGET_CURRENCIES
from app.portfolio.simulator import (
    PortfolioSimulationRequest,
    PortfolioSimulationResponse,
    run_portfolio_10y_simulation,
)
from app.portfolio.advisor import (
    DiverseRiskAdvisorRequest,
    DiverseRiskAdvisorResponse,
    MarketBlueprintResponse,
    MarketScope,
    ask_diverse_risk_advisor,
    get_market_sector_blueprints,
)
from app.portfolio.optimizer import (
    CAPMRequest,
    CAPMResponse,
    DiverseRiskRequest,
    DiverseRiskResponse,
    FXAttributionRequest,
    FXAttributionResponse,
    PortfolioCreateRequest,
    PortfolioOptimizeRequest,
    PortfolioOptimizeResponse,
    PortfolioStore,
    analyze_diverse_risk,
    compute_capm,
    fx_return_attribution,
    optimize_portfolio,
)
from app.risk.engine import RiskAnalysisRequest, RiskAnalysisResponse, run_risk_analysis
from app.risk.bankruptcy import BankruptcyPipelineResponse, BankruptcyRequest, run_bankruptcy_pipeline
from app.risk.tracker import RiskTrackerResponse, build_risk_tracker_report
from app.sentiment.crowd_engine import CrowdSentimentRequest, CrowdSentimentResponse, analyze_crowd_sentiment

router = APIRouter(prefix="/api/v1", tags=["quantai"])


class SignalsRequest(BaseModel):
    instrument_id: str
    bars: List[OHLCVBar] = Field(..., min_items=15)


def get_registry(request: Request) -> MarketDataRegistry:
    return request.app.state.registry


def get_portfolio_store(request: Request) -> PortfolioStore:
    return request.app.state.portfolio_store


@router.get("/health", response_model=HealthResponse)
def health(request: Request, registry: MarketDataRegistry = Depends(get_registry)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=request.app.version,
        timestamp_utc=datetime.now(timezone.utc),
        configured_providers=registry.configured_provider_map(),
        database_ready=request.app.state.db.health_check(),
    )


@router.get("/instruments/search", response_model=List[Instrument])
def search_instruments(
    q: str = Query(default=""),
    exchange: Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
    sector: Optional[str] = Query(default=None),
    as_of: Optional[date] = Query(default=None),
    registry: MarketDataRegistry = Depends(get_registry),
) -> List[Instrument]:
    return registry.search_instruments(
        query=q, exchange=exchange, country=country, sector=sector, as_of=as_of
    )


@router.get("/exchanges/coverage", response_model=List[ExchangeCoverageEntry])
def exchange_coverage(registry: MarketDataRegistry = Depends(get_registry)) -> List[ExchangeCoverageEntry]:
    return registry.get_exchange_coverage()


@router.get("/exchanges/{exchange_mic}/status", response_model=MarketSessionInfo)
def exchange_status(
    exchange_mic: str,
    ticker: Optional[str] = Query(default=None),
    as_of_utc: Optional[datetime] = Query(default=None),
) -> MarketSessionInfo:
    now_dt = as_of_utc or datetime.now(timezone.utc)
    is_suspended = False
    eff_mic = exchange_mic.upper().strip()
    if ticker:
        eff_mic, _, is_suspended, _ = resolve_effective_exchange(ticker, eff_mic, as_of=now_dt.date())
    return get_market_session(eff_mic, now_utc=now_dt, is_migration_suspended=is_suspended)


@router.get("/market/quote/{instrument_id}", response_model=QuoteResponse)
def get_quote(
    instrument_id: str,
    require_live: bool = Query(default=False),
    allow_educational_fallback: bool = Query(default=False),
    as_of: Optional[date] = Query(default=None),
    registry: MarketDataRegistry = Depends(get_registry),
) -> QuoteResponse:
    try:
        parse_instrument_id(instrument_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return registry.get_quote(
        instrument_id=instrument_id,
        require_live=require_live,
        allow_educational_fallback=allow_educational_fallback,
        as_of=as_of,
    )


@router.get("/market/ohlcv/{instrument_id}", response_model=OHLCVResponse)
def get_ohlcv(
    instrument_id: str,
    interval: str = Query(default="1d"),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    period: Optional[str] = Query(default=None),
    allow_educational_fallback: bool = Query(default=True),
    registry: MarketDataRegistry = Depends(get_registry),
) -> OHLCVResponse:
    try:
        parse_instrument_id(instrument_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return registry.get_ohlcv(
        instrument_id=instrument_id,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        period=period,
        allow_educational_fallback=allow_educational_fallback,
    )


@router.get("/fx/currencies", response_model=List[str])
def list_target_currencies() -> List[str]:
    return list(TARGET_CURRENCIES)


@router.get("/fx/rates", response_model=FXRatesResponse)
def get_fx_rates(
    base: str = Query(default="USD"),
    quotes: Optional[str] = Query(default=None),
    as_of: Optional[date] = Query(default=None),
    registry: MarketDataRegistry = Depends(get_registry),
) -> FXRatesResponse:
    quote_list = [q.strip().upper() for q in quotes.split(",") if q.strip()] if quotes else None
    return registry.frankfurter.get_latest_rates(base=base, quotes=quote_list, as_of=as_of)


@router.get("/fx/convert", response_model=FXConversionResponse)
def convert_fx(
    base: str = Query(...),
    quote: str = Query(...),
    amount: float = Query(..., gt=0.0),
    as_of: Optional[date] = Query(default=None),
    registry: MarketDataRegistry = Depends(get_registry),
) -> FXConversionResponse:
    return registry.frankfurter.convert(base=base, quote=quote, amount=amount, as_of=as_of)


@router.post("/analytics/single-asset", response_model=SingleAssetAnalyticsResponse)
def analyze_single_asset(payload: SingleAssetAnalyticsRequest) -> SingleAssetAnalyticsResponse:
    return run_single_asset_analytics(payload)


@router.post("/analytics/matrix", response_model=MatrixAnalyticsResponse)
def analyze_multi_asset_matrix(payload: MatrixAnalyticsRequest) -> MatrixAnalyticsResponse:
    return run_matrix_analytics(payload)


@router.post("/portfolio/optimize", response_model=PortfolioOptimizeResponse)
def optimize_portfolio_endpoint(payload: PortfolioOptimizeRequest) -> PortfolioOptimizeResponse:
    return optimize_portfolio(payload)



@router.get("/portfolio/diverse-risk/blueprint", response_model=MarketBlueprintResponse)
def diverse_risk_blueprint_endpoint(
    market_scope: MarketScope = Query(default="VN", description="US, VN, US_VN, or GLOBAL"),
) -> MarketBlueprintResponse:
    return get_market_sector_blueprints(market_scope)


@router.post("/portfolio/diverse-risk", response_model=DiverseRiskResponse)
def diverse_risk_endpoint(payload: DiverseRiskRequest) -> DiverseRiskResponse:
    """Evaluate diversification risk reduction for up to 10 stocks and suggest risk-reducing combinations."""
    return analyze_diverse_risk(payload)



@router.get("/assistant/status")
def assistant_status_endpoint(
    registry: MarketDataRegistry = Depends(get_registry),
) -> Dict[str, object]:
    key = registry.settings.gemini_api_key
    return {
        "gemini_configured": bool(key),
        "key_prefix": (key[:6] + "...") if key and len(key) >= 6 else None,
        "gemini_model": registry.settings.gemini_model,
    }


@router.post("/portfolio/diverse-risk/ask", response_model=DiverseRiskAdvisorResponse)
def diverse_risk_advisor_endpoint(
    payload: DiverseRiskAdvisorRequest,
    request: Request,
) -> DiverseRiskAdvisorResponse:
    cfg = request.app.state.settings
    return ask_diverse_risk_advisor(
        payload,
        gemini_api_key=cfg.gemini_api_key,
        gemini_model=cfg.gemini_model,
        timeout=cfg.http_timeout_seconds,
    )


@router.post("/portfolio/capm", response_model=CAPMResponse)
def capm_endpoint(payload: CAPMRequest) -> CAPMResponse:
    return compute_capm(payload)


@router.post("/portfolio/fx-attribution", response_model=FXAttributionResponse)
def fx_attribution_endpoint(payload: FXAttributionRequest) -> FXAttributionResponse:
    return fx_return_attribution(payload)


@router.post("/portfolio/save")
def save_portfolio_endpoint(
    payload: PortfolioCreateRequest,
    store: PortfolioStore = Depends(get_portfolio_store),
) -> Dict[str, object]:
    return store.save_portfolio(payload)


@router.get("/portfolio/list")
def list_portfolios_endpoint(
    store: PortfolioStore = Depends(get_portfolio_store),
) -> List[Dict[str, object]]:
    return store.list_portfolios()


@router.post("/risk/analyze", response_model=RiskAnalysisResponse)
def risk_analysis_endpoint(payload: RiskAnalysisRequest) -> RiskAnalysisResponse:
    return run_risk_analysis(payload)


@router.post("/forecasting/run", response_model=ForecastResponse)
def forecasting_endpoint(payload: ForecastRequest) -> ForecastResponse:
    return run_forecasting_suite(payload)


@router.post("/signals/evaluate", response_model=SignalsResponse)
def signals_endpoint(payload: SignalsRequest) -> SignalsResponse:
    return evaluate_quantitative_signals(payload.instrument_id, payload.bars)


@router.post("/backtesting/run", response_model=BacktestResponse)
def backtest_endpoint(payload: BacktestRequest) -> BacktestResponse:
    return run_backtest(payload)


@router.post("/sentiment/crowd", response_model=CrowdSentimentResponse)
def crowd_sentiment_endpoint(
    payload: CrowdSentimentRequest,
    registry: MarketDataRegistry = Depends(get_registry),
) -> CrowdSentimentResponse:
    return analyze_crowd_sentiment(payload, finnhub_api_key=registry.settings.finnhub_api_key)


@router.get("/risk/tracker", response_model=RiskTrackerResponse)
def risk_tracker_endpoint(
    risk_id: str = Query(default="rates_tightening"),
    market: str = Query(default="ALL"),
) -> RiskTrackerResponse:
    return build_risk_tracker_report(risk_id=risk_id, market_filter=market)


@router.post("/risk/bankruptcy", response_model=BankruptcyPipelineResponse)
def bankruptcy_pipeline_endpoint(
    payload: BankruptcyRequest,
    registry: MarketDataRegistry = Depends(get_registry),
) -> BankruptcyPipelineResponse:
    mic, ticker = parse_instrument_id(payload.instrument_id) if ":" in payload.instrument_id else ("XNAS", payload.instrument_id)
    matches = registry.search_instruments(query=ticker)
    matched = next((m for m in matches if m.instrument_id.upper() == payload.instrument_id.upper()), matches[0] if matches else None)
    return run_bankruptcy_pipeline(
        payload,
        company_name_hint=matched.company_name if matched else ticker,
        currency_hint=matched.currency if matched else "USD",
    )


@router.post("/portfolio/simulate-10y-forecast", response_model=PortfolioSimulationResponse)
def portfolio_simulate_10y_endpoint(
    payload: PortfolioSimulationRequest,
    registry: MarketDataRegistry = Depends(get_registry),
) -> PortfolioSimulationResponse:
    meta_map: Dict[str, Dict[str, str]] = {}
    for iid in payload.instrument_ids:
        _, tkr = parse_instrument_id(iid) if ":" in iid else ("XNAS", iid)
        matches = registry.search_instruments(query=tkr)
        m = next((x for x in matches if x.instrument_id.upper() == iid.upper()), matches[0] if matches else None)
        meta_map[iid] = {
            "company_name": m.company_name if m else tkr,
            "sector": (m.sector or "Equity") if m else "Equity",
        }
    if payload.asset_series is None:
        fetched: Dict[str, List[OHLCVBar]] = {}
        excluded_list: List[Dict[str, str]] = []
        period_str = "10y" if payload.years >= 10 else ("5y" if payload.years >= 5 else "2y")
        for iid in payload.instrument_ids:
            ohlcv = registry.get_ohlcv(
                instrument_id=iid,
                interval="1d",
                period=period_str,
                allow_educational_fallback=True,
            )
            if ohlcv.bars and len(ohlcv.bars) >= 20:
                fetched[iid] = ohlcv.bars
            else:
                tkr = iid.split(":", 1)[1] if ":" in iid else iid
                excluded_list.append({"ticker": tkr, "reason": ohlcv.unavailable_reason or "Insufficient historical bars returned by data providers."})
        if len(fetched) < 2:
            raise HTTPException(
                status_code=422,
                detail="Insufficient historical data for at least 2 selected stocks. Verify network access or pick liquid tickers.",
            )
        payload = payload.copy(update={"asset_series": fetched})
    try:
        res = run_portfolio_10y_simulation(payload, metadata_map=meta_map)
        if 'excluded_list' in locals() and excluded_list:
            res = res.copy(update={'excluded_tickers': excluded_list})
        return res
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/backtesting/portfolio", response_model=PortfolioBacktestResponse)
def portfolio_backtest_endpoint(
    payload: PortfolioBacktestRequest,
    registry: MarketDataRegistry = Depends(get_registry),
) -> PortfolioBacktestResponse:
    if payload.asset_series is None:
        fetched: Dict[str, List[OHLCVBar]] = {}
        period_str = "10y" if payload.years >= 10 else ("5y" if payload.years >= 5 else "2y")
        for iid in payload.instrument_ids:
            ohlcv = registry.get_ohlcv(
                instrument_id=iid,
                interval="1d",
                period=period_str,
                allow_educational_fallback=True,
            )
            if ohlcv.bars and len(ohlcv.bars) >= 20:
                fetched[iid] = ohlcv.bars
        if len(fetched) < 2:
            raise HTTPException(
                status_code=422,
                detail="Could not fetch sufficient 10-year historical bars for at least 2 selected stocks. Verify network access or select liquid tickers.",
            )
        payload = payload.copy(update={"asset_series": fetched})
    try:
        return run_portfolio_backtest(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.websocket("/ws/quotes/{instrument_id}")
async def quote_stream_ws(websocket: WebSocket, instrument_id: str) -> None:
    await websocket.accept()
    registry: MarketDataRegistry = websocket.app.state.registry
    try:
        parse_instrument_id(instrument_id)
        snapshot = registry.get_quote(
            instrument_id=instrument_id,
            require_live=True,
            allow_educational_fallback=False,
        )
        await websocket.send_text(snapshot.json())
        while True:
            msg = await websocket.receive_text()
            if msg.strip().lower() == "refresh":
                refreshed = registry.get_quote(
                    instrument_id=instrument_id,
                    require_live=True,
                    allow_educational_fallback=False,
                )
                await websocket.send_text(refreshed.json())
    except ValueError as exc:
        await websocket.send_json({"error": str(exc), "data_status": "DATA_UNAVAILABLE"})
        await websocket.close(code=1008)
    except WebSocketDisconnect:
        return
