"""Senior Quantitative Portfolio Strategist Advisor & Top-Down Blueprint Engine (v1.6.0).

Workflow:
  1. Market Scope Selection (US, VN, US_VN, GLOBAL) — no hardcoded pre-selected stocks.
  2. Recommended low-correlation Industry / Sector combinations for that market.
  3. Candidate stocks within the chosen industries + AI-proposed minimum-variance portfolio.
  4. Interactive follow-up Q&A to refine the portfolio based on user preferences.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Literal, Optional

import httpx
from pydantic import BaseModel, Field

from app.core.symbology import GLOBAL_INSTRUMENTS
from app.portfolio.optimizer import DiverseRiskResponse

logger = logging.getLogger("quantai.advisor")

MarketScope = Literal["US", "VN", "US_VN", "GLOBAL"]

DEFENSIVE_CORE_SECTORS = [
    "Consumer Defensive",
    "Utilities",
    "Energy",
    "Financial Services",
    "Basic Materials",
    "Industrials",
]


class IndustryBlueprint(BaseModel):
    name: str
    sectors: List[str]
    rationale: str
    suggested_tickers: List[str]


class SectorStockGroup(BaseModel):
    sector: str
    stocks: List[Dict[str, str]]


class MarketBlueprintResponse(BaseModel):
    market_scope: MarketScope
    market_label: str
    recommended_blueprints: List[IndustryBlueprint]
    sectors: List[SectorStockGroup]


class DiverseRiskAdvisorRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    analysis: DiverseRiskResponse
    market_scope: Optional[str] = None
    selected_sectors: List[str] = Field(default_factory=list)


class DiverseRiskAdvisorResponse(BaseModel):
    answer: str
    engine_used: str
    used_llm: bool
    sector_breakdown: Dict[str, float]
    country_breakdown: Dict[str, float]
    missing_defensive_sectors: List[str]
    recommended_actions: List[str]
    disclaimer: str


def _filter_instruments_by_scope(scope: MarketScope):
    if scope == "US":
        return [i for i in GLOBAL_INSTRUMENTS if i.country == "United States"]
    if scope == "VN":
        return [i for i in GLOBAL_INSTRUMENTS if i.country == "Vietnam"]
    if scope == "US_VN":
        return [i for i in GLOBAL_INSTRUMENTS if i.country in {"United States", "Vietnam"}]
    return list(GLOBAL_INSTRUMENTS)


def get_market_sector_blueprints(scope: MarketScope) -> MarketBlueprintResponse:
    scoped = _filter_instruments_by_scope(scope)
    by_sector: Dict[str, List[Dict[str, str]]] = {}
    for inst in scoped:
        by_sector.setdefault(inst.sector, []).append(
            {
                "instrument_id": inst.instrument_id,
                "ticker": inst.ticker,
                "company_name": inst.company_name,
                "country": inst.country,
                "currency": inst.currency,
            }
        )

    sector_groups = [
        SectorStockGroup(sector=sec, stocks=stocks)
        for sec, stocks in sorted(by_sector.items(), key=lambda kv: kv[0])
    ]

    if scope == "US":
        label = "United States Equities (NYSE / NASDAQ)"
        blueprints = [
            IndustryBlueprint(
                name="US Balanced Growth & Financials",
                sectors=["Technology", "Financial Services", "Broad Market"],
                rationale="Pairs high-beta US technology leaders with rate-sensitive financials and broad-market ETF stability.",
                suggested_tickers=["XNAS:AAPL", "XNAS:MSFT", "XNYS:JPM", "XNYS:BRK.B", "XNYS:SPY"],
            ),
            IndustryBlueprint(
                name="US Multi-Sector Core",
                sectors=["Technology", "Communication Services", "Financial Services", "Consumer Cyclical"],
                rationale="Spreads exposure across four distinct US economic sectors to reduce single-industry shock.",
                suggested_tickers=["XNAS:MSFT", "XNAS:GOOGL", "XNYS:JPM", "XNAS:AMZN"],
            ),
        ]
    elif scope == "VN":
        label = "Vietnam Equities (HOSE / HNX)"
        blueprints = [
            IndustryBlueprint(
                name="Vietnam Defensive Risk-Minimizer",
                sectors=["Consumer Defensive", "Energy", "Utilities", "Technology"],
                rationale="Combines stable domestic cash-flow sectors (dairy, gas, power) with FPT to avoid bank/real-estate cyclical concentration.",
                suggested_tickers=["XSTC:VNM", "XSTC:GAS", "XSTC:POW", "XSTC:FPT", "XSTC:REE"],
            ),
            IndustryBlueprint(
                name="Vietnam Core All-Weather",
                sectors=["Financial Services", "Consumer Defensive", "Technology", "Basic Materials", "Industrials"],
                rationale="Balances Vietcombank/Techcombank with defensive staples, IT services, chemicals, and industrial infrastructure.",
                suggested_tickers=["XSTC:VCB", "XSTC:VNM", "XSTC:FPT", "XSTC:DGC", "XSTC:REE"],
            ),
        ]
    elif scope == "US_VN":
        label = "Cross-Market (United States + Vietnam)"
        blueprints = [
            IndustryBlueprint(
                name="US Tech + Vietnam Defensive Hedge",
                sectors=["Technology", "Consumer Defensive", "Energy", "Financial Services"],
                rationale="Exploits low cross-border correlation between US equities and Vietnam domestic defensives (near-zero historical correlation).",
                suggested_tickers=["XNAS:AAPL", "XNYS:JPM", "XSTC:VNM", "XSTC:GAS", "XSTC:FPT"],
            ),
            IndustryBlueprint(
                name="Dual-Market Minimum Variance",
                sectors=["Broad Market", "Financial Services", "Consumer Defensive", "Utilities", "Industrials"],
                rationale="Anchors USD core exposure with low-beta Vietnamese utilities, staples, and industrial cash flows.",
                suggested_tickers=["XNYS:SPY", "XNYS:BRK.B", "XSTC:VNM", "XSTC:POW", "XSTC:REE"],
            ),
        ]
    else:
        label = "Global Multi-Market (US + Vietnam + Europe + Asia + Australia)"
        blueprints = [
            IndustryBlueprint(
                name="Global Defensive Fortress",
                sectors=["Consumer Defensive", "Utilities", "Financial Services", "Technology", "Basic Materials"],
                rationale="Spans 5 currencies (USD, CHF, EUR, VND, AUD/SGD) and defensive sectors to maximize the Diversification Ratio.",
                suggested_tickers=["XSWX:NESN", "XMIL:ENEL", "XSES:D05", "XNAS:MSFT", "XSTC:VNM", "XASX:BHP"],
            ),
            IndustryBlueprint(
                name="Global Four-Region Core",
                sectors=["Technology", "Financial Services", "Consumer Defensive", "Consumer Cyclical", "Energy"],
                rationale="Balances North America, Europe, Japan/ASEAN, and Vietnam across uncorrelated macro cycles.",
                suggested_tickers=["XNAS:AAPL", "XSWX:NESN", "XTKS:7203", "XSES:D05", "XSTC:GAS"],
            ),
        ]

    return MarketBlueprintResponse(
        market_scope=scope,
        market_label=label,
        recommended_blueprints=blueprints,
        sectors=sector_groups,
    )


def _lookup_metadata(symbols: List[str]) -> tuple[Dict[str, float], Dict[str, float]]:
    meta = {inst.instrument_id: inst for inst in GLOBAL_INSTRUMENTS}
    n = max(1, len(symbols))
    sector_counts: Dict[str, float] = {}
    country_counts: Dict[str, float] = {}
    for sym in symbols:
        inst = meta.get(sym)
        sec = inst.sector if inst else "Unclassified"
        ctry = inst.country if inst else "Unclassified"
        sector_counts[sec] = round(sector_counts.get(sec, 0.0) + (100.0 / n), 1)
        country_counts[ctry] = round(country_counts.get(ctry, 0.0) + (100.0 / n), 1)
    return sector_counts, country_counts


def _build_question_aware_analysis(
    question: str,
    analysis: DiverseRiskResponse,
    sector_breakdown: Dict[str, float],
    missing_sectors: List[str],
    market_scope: Optional[str],
) -> tuple[str, List[str]]:
    actions: List[str] = []
    paragraphs: List[str] = []

    top_sector, top_sec_pct = max(sector_breakdown.items(), key=lambda kv: kv[1])
    best_combo = analysis.suggested_combinations[0] if analysis.suggested_combinations else None
    risk_reducers = [c for c in analysis.candidate_additions if c.is_risk_reducing]

    scope_label = market_scope or "Selected Market"
    paragraphs.append(
        f"For your {scope_label} portfolio ({len(analysis.symbols)} stocks), equal-weight annualized volatility is "
        f"{analysis.equal_weight_volatility * 100:.2f}% versus a standalone average of {analysis.standalone_weighted_volatility * 100:.2f}% "
        f"(risk reduction: {analysis.risk_reduction_pct:.1f}%, Diversification Ratio: {analysis.diversification_ratio:.2f}x, "
        f"average pairwise correlation: {analysis.avg_pairwise_correlation:.2f})."
    )

    if best_combo:
        w_str = ", ".join(f"{s} ({w * 100:.0f}%)" for s, w in best_combo.optimal_weights.items())
        paragraphs.append(
            f"Using minimum-variance optimization on your selected industries, the lowest-risk allocation is "
            f"{w_str}, bringing annualized volatility down to {best_combo.portfolio_volatility * 100:.2f}%."
        )
        actions.append(f"Minimum-variance weights: {w_str}.")

    if missing_sectors or risk_reducers:
        extra_secs = ", ".join(missing_sectors[:3]) if missing_sectors else "Healthcare or Fixed Income ETFs"
        cand_txt = (
            ", ".join(f"{c.symbol} ({c.volatility_change_pct:+.2f}% vol)" for c in risk_reducers[:3])
            if risk_reducers
            else "defensive low-beta leaders"
        )
        paragraphs.append(
            f"To refine this portfolio further, consider balancing your {top_sector} weight ({top_sec_pct:.0f}%) "
            f"with underrepresented defensive sectors ({extra_secs}) or adding {cand_txt}."
        )
        actions.append(f"Consider balancing {top_sector} with {extra_secs}.")

    return "\n\n".join(paragraphs), actions


def ask_diverse_risk_advisor(
    req: DiverseRiskAdvisorRequest,
    gemini_api_key: Optional[str] = None,
    gemini_model: str = "gemini-2.5-flash",
    timeout: float = 20.0,
    http_post: Optional[Callable[..., Any]] = None,
) -> DiverseRiskAdvisorResponse:
    sector_breakdown, country_breakdown = _lookup_metadata(req.analysis.symbols)
    missing_sectors = [s for s in DEFENSIVE_CORE_SECTORS if s not in sector_breakdown]

    det_answer, actions = _build_question_aware_analysis(
        req.question, req.analysis, sector_breakdown, missing_sectors, req.market_scope
    )
    disclaimer = (
        "Quantitative diversification analysis is grounded in historical sample correlations and "
        "minimum-variance math. For research and educational use only — not investment advice."
    )

    if gemini_api_key:
        post_fn = http_post or httpx.post
        context_payload = {
            "market_scope": req.market_scope or "CUSTOM",
            "selected_sectors": req.selected_sectors,
            "selected_stocks": req.analysis.symbols,
            "sector_breakdown_pct": sector_breakdown,
            "country_breakdown_pct": country_breakdown,
            "missing_defensive_sectors": missing_sectors,
            "equal_weight_volatility_pct": round(req.analysis.equal_weight_volatility * 100, 2),
            "standalone_avg_volatility_pct": round(req.analysis.standalone_weighted_volatility * 100, 2),
            "diversification_ratio": req.analysis.diversification_ratio,
            "risk_reduction_pct": req.analysis.risk_reduction_pct,
            "gmv_volatility_pct": round(req.analysis.gmv_volatility * 100, 2),
            "avg_pairwise_correlation": req.analysis.avg_pairwise_correlation,
            "highest_correlation_pairs": [p.dict() for p in req.analysis.highest_correlation_pairs[:3]],
            "lowest_correlation_pairs": [p.dict() for p in req.analysis.lowest_correlation_pairs[:3]],
            "top_suggested_combinations": [c.dict() for c in req.analysis.suggested_combinations[:3]],
            "top_candidate_additions": [c.dict() for c in req.analysis.candidate_additions[:5]],
        }
        prompt = (
            "You are a Senior Quantitative Portfolio Strategist & Financial Risk Manager inside QuantAI. "
            "Help the user build and refine a minimum-risk equity portfolio following a top-down workflow "
            "(Market Scope -> Industry Pairing -> Stock Selection -> Weighting & Risk Reduction). "
            "Use the verified quantitative metrics below as the factual anchor, AND proactively recommend "
            "specific NEW stocks, industries, ETFs, or weight adjustments whenever the user asks to refine "
            "or customize their portfolio. Never invent fake live prices or promise guaranteed returns. "
            "Do NOT use raw markdown '**' bold asterisks; write crisp, natural paragraphs and plain '• ' bullets. "
            "Reply in the exact same language as the user's question.\n\n"
            f"VERIFIED PORTFOLIO DATA:\n{json.dumps(context_payload, indent=2)}\n\n"
            f"USER REQUEST:\n{req.question}"
        )

        endpoints: List[tuple[str, str, Dict[str, str], Dict[str, str]]] = []
        models_to_try = list(dict.fromkeys([gemini_model, "gemini-2.0-flash", "gemini-1.5-flash"]))
        for m in models_to_try:
            endpoints.append((
                m,
                f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                {"x-goog-api-key": gemini_api_key},
                {},
            ))
            if gemini_api_key.startswith("AQ."):
                endpoints.append((
                    m,
                    f"https://aiplatform.googleapis.com/v1/publishers/google/models/{m}:generateContent",
                    {},
                    {"key": gemini_api_key},
                ))

        for model_name, url, headers, params in endpoints:
            try:
                resp = post_fn(
                    url,
                    headers=headers,
                    params=params,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=timeout,
                )
                status = getattr(resp, "status_code", 200)
                if status == 200:
                    data = resp.json()
                    text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text")
                    )
                    if isinstance(text, str) and text.strip():
                        clean_text = text.strip().replace("**", "")
                        return DiverseRiskAdvisorResponse(
                            answer=clean_text,
                            engine_used=f"QuantAI Strategist ({model_name})",
                            used_llm=True,
                            sector_breakdown=sector_breakdown,
                            country_breakdown=country_breakdown,
                            missing_defensive_sectors=missing_sectors,
                            recommended_actions=actions,
                            disclaimer=disclaimer,
                        )
                else:
                    logger.warning("Gemini endpoint %s returned HTTP %s: %s", url, status, getattr(resp, "text", "")[:180])
            except Exception as exc:
                logger.warning("Gemini endpoint %s failed: %s", url, exc)

    return DiverseRiskAdvisorResponse(
        answer=det_answer,
        engine_used="QuantAI Quantitative Strategist",
        used_llm=False,
        sector_breakdown=sector_breakdown,
        country_breakdown=country_breakdown,
        missing_defensive_sectors=missing_sectors,
        recommended_actions=actions,
        disclaimer=disclaimer,
    )
