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


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class DiverseRiskAdvisorRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1500)
    analysis: Optional[DiverseRiskResponse] = None
    market_scope: Optional[str] = None
    selected_sectors: List[str] = Field(default_factory=list)
    selected_stocks: List[str] = Field(default_factory=list)
    portfolio_summary: Optional[str] = None
    conversation_history: List[ChatTurn] = Field(default_factory=list)


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
        label = "Global Multi-Market (United States + Vietnam + Italy)"
        blueprints = [
            IndustryBlueprint(
                name="Global Defensive Fortress",
                sectors=["Consumer Defensive", "Utilities", "Financial Services", "Technology", "Basic Materials"],
                rationale="Spans three currencies (USD, EUR, VND) and defensive sectors to maximize the Diversification Ratio.",
                suggested_tickers=["XNAS:MSFT", "XMIL:ENEL", "XMIL:CPR", "XMIL:G", "XSTC:VNM", "XSTC:GAS"],
            ),
            IndustryBlueprint(
                name="Global Three-Market Core",
                sectors=["Technology", "Financial Services", "Consumer Defensive", "Consumer Cyclical", "Energy"],
                rationale="Balances North America, Southern Europe (Italy) and Vietnam across less correlated macro and currency cycles.",
                suggested_tickers=["XNAS:AAPL", "XNYS:JPM", "XMIL:RACE", "XMIL:ENI", "XSTC:FPT", "XSTC:VCB"],
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



def _build_standalone_conversational_reply(
    question: str,
    active_symbols: List[str],
    sector_breakdown: Dict[str, float],
    missing_sectors: List[str],
    market_scope: Optional[str],
    portfolio_summary: Optional[str],
    llm_configured: bool = True,
) -> tuple[str, List[str]]:
    q = question.strip().lower()
    clean_syms = [s.split(":", 1)[1] if ":" in s else s for s in active_symbols]
    basket_str = ", ".join(clean_syms) if clean_syms else "your portfolio"
    is_vn_focus = (
        any(tok in q for tok in ("vietnam", "vietnamese", "vn30", "hose", "hnx", "upcom", "việt nam"))
        or (market_scope and "vietnam" in market_scope.lower() and "united states" not in market_scope.lower())
        or (active_symbols and all(s.startswith(("XSTC:", "XHAI:", "XUPC:")) for s in active_symbols))
    )

    # 1. Natural greetings & casual check-ins
    greeting_tokens = ("hi", "hello", "hey", "good morning", "good afternoon", "good evening", "chào", "xin chào", "alo")
    if len(q.split()) <= 5 and any(q == g or q.startswith(g + " ") or q.startswith(g + "!") or q.startswith(g + ",") for g in greeting_tokens):
        greeting_lead = "Good morning!" if "morning" in q else ("Chào bạn!" if ("chào" in q or "alo" in q) else "Hi there!")
        if clean_syms:
            return (
                f"{greeting_lead} I'm looking at your current {len(clean_syms)}-stock basket ({basket_str}). "
                f"What would you like to explore today — trimming high-volatility names, adding defensive sectors, or stress-testing a specific scenario?",
                [],
            )
        return (
            f"{greeting_lead} I'm ready to help you design a low-risk portfolio. Tell me which markets, capital size, or risk goals you have in mind.",
            [],
        )

    # Identify high-beta / cyclical candidates inside current basket to trim/remove
    high_beta_sectors = {"Real Estate", "Consumer Cyclical", "Financial Services", "Industrials"}
    from app.core.symbology import GLOBAL_INSTRUMENTS
    meta_by_id = {i.instrument_id.upper(): i for i in GLOBAL_INSTRUMENTS}
    meta_by_tkr = {i.ticker.upper(): i for i in GLOBAL_INSTRUMENTS}

    cyclical_in_basket: List[str] = []
    defensive_in_basket: List[str] = []
    for s in active_symbols:
        tkr = s.split(":", 1)[1] if ":" in s else s
        inst = meta_by_id.get(s.upper()) or meta_by_tkr.get(tkr.upper())
        sec = inst.sector if inst else None
        if sec in {"Healthcare", "Consumer Defensive", "Utilities"}:
            defensive_in_basket.append(f"{tkr} ({sec})")
        elif sec in high_beta_sectors or tkr in {"CEO", "SSI", "HUT", "TSLA", "NVDA"}:
            cyclical_in_basket.append(f"{tkr} ({sec or 'Cyclical'})")

    # Market-appropriate defensive additions not already in basket
    add_candidates = (
        [
            ("Consumer Defensive", "VNM or MCH"),
            ("Utilities", "POW or GAS"),
            ("Financial Services (Low-Beta Bank)", "VCB or ACB"),
            ("Healthcare", "DHG"),
        ]
        if is_vn_focus
        else [
            ("Healthcare", "JNJ or UNH"),
            ("Consumer Defensive", "WMT or COST"),
            ("Utilities", "NEE"),
            ("Energy", "XOM"),
        ]
    )
    suggested_adds = [
        f"{sec}: {tkrs}"
        for sec, tkrs in add_candidates
        if not any(t.strip() in clean_syms for t in tkrs.replace(" or ", ",").split(","))
    ][:3]

    # 2. Add / Remove / Trim / Replace stock questions
    if any(k in q for k in ("add", "remove", "drop", "trim", "cut", "sell", "buy", "replace", "swap", "thêm", "bỏ", "xóa", "thay")):
        trim_part = (
            f"Candidates to trim or remove first: {', '.join(cyclical_in_basket[:3])}. "
            f"These names carry higher beta and cyclical drawdown sensitivity, which disproportionately expands tail risk during market sell-offs."
            if cyclical_in_basket
            else f"Your current basket ({basket_str}) has no extreme single-sector overlap, so trim whichever holding exceeds 20–25% weight."
        )
        add_part = (
            f"Best additions to lower portfolio volatility: {'; '.join(suggested_adds)}."
            if suggested_adds
            else "Your defensive sector coverage is already solid; consider adding a cross-market hedge from another country to reduce domestic macro risk."
        )
        keep_part = (
            f"Core defensive anchors worth keeping: {', '.join(defensive_in_basket[:3])}."
            if defensive_in_basket
            else "You currently lack dedicated Healthcare/Consumer Defensive/Utilities anchors."
        )
        return (
            f"{trim_part}\n\n{add_part}\n\n{keep_part}",
            [f"Trim cyclical overlap ({', '.join(cyclical_in_basket[:2])})" if cyclical_in_basket else "Rebalance weights quarterly", add_part],
        )

    # 3. Interest rate / inflation / macro hedge questions
    if any(k in q for k in ("rate", "inflation", "fed", "macro", "recession", "crash", "hedge", "lãi suất", "lạm phát", "khủng hoảng")):
        sec_list = ", ".join(f"{k} ({v:.0f}%)" for k, v in list(sector_breakdown.items())[:4]) or "your current sectors"
        hedge_picks = "GAS/BSR (Energy) and VCB/MBB (Banks) paired with VNM/DHG (Defensive)" if is_vn_focus else "XOM (Energy), JPM (Financials), and JNJ/WMT (Defensive Cash Flow)"
        return (
            f"To hedge rising interest rates and inflation across {basket_str} (current mix: {sec_list}), reduce exposure to rate-sensitive Real Estate and long-duration growth names, "
            f"and tilt 25–35% toward cash-generative inflation beneficiaries such as {hedge_picks}. "
            f"Keep single-stock weights capped near 15–20% and rebalance quarterly to lock in gains during rate spikes.",
            ["Reduce Real Estate / high-duration exposure", f"Add inflation-resilient anchors: {hedge_picks}"],
        )

    # 4. Sector / correlation / diversification questions
    if any(k in q for k in ("sector", "industry", "correlat", "defensive", "diversif", "ngành", "tương quan")):
        sec_str = ", ".join(f"{k}: {v:.0f}%" for k, v in sector_breakdown.items()) if sector_breakdown else "unclassified"
        miss_str = ", ".join(missing_sectors) if missing_sectors else "none (core defensive sectors are covered)"
        return (
            f"Your current sector exposure across {len(clean_syms)} stocks is: {sec_str}.\n\n"
            f"Missing defensive sectors: {miss_str}. Adding low-correlation holdings in {'; '.join(suggested_adds) if suggested_adds else 'cross-market defensive leaders'} "
            f"typically cuts portfolio drawdown more effectively than adding another stock inside an already-crowded sector.",
            [f"Fill missing defensive sectors: {miss_str}"],
        )

    # 5. General / non-portfolio casual message when Gemini is temporarily unavailable (503)
    finance_keywords = ("stock", "portfolio", "risk", "weight", "return", "drawdown", "volatil", "market", "invest", "buy", "sell", "cổ phiếu", "danh mục", "rủi ro", "đầu tư", "tỷ trọng", "lợi nhuận")
    if not any(k in q for k in finance_keywords):
        if not llm_configured:
            return (
                "Free-form conversation needs the optional Gemini integration (GEMINI_API_KEY is not configured on this server). "
                "I can still answer questions about your stocks, sectors, weights, correlation, hedging and risk — try asking about one of those!",
                [],
            )
        return (
            "Gemini is briefly experiencing a temporary high-demand spike right now, so my full conversational mode couldn't connect on that turn. "
            "Hit Send again in a couple of seconds and I'll be right with you!",
            [],
        )

    sec_str = ", ".join(f"{k} ({v:.0f}%)" for k, v in list(sector_breakdown.items())[:4]) if sector_breakdown else "mixed sectors"
    return (
        f"Looking at your {len(clean_syms)}-stock basket ({basket_str} — {sec_str}), the fastest way to improve risk-adjusted returns is to pair your growth/cyclical names "
        f"with uncorrelated defensive cash-flow anchors ({'; '.join(suggested_adds) if suggested_adds else 'Healthcare, Consumer Defensive & Utilities'}) "
        f"and keep individual weights balanced under 20–25%. Ask me specifically about any ticker to add, remove, or stress-test!",
        [f"Consider adding: {'; '.join(suggested_adds)}" if suggested_adds else "Maintain quarterly rebalancing"],
    )


def ask_diverse_risk_advisor(
    req: DiverseRiskAdvisorRequest,
    gemini_api_key: Optional[str] = None,
    gemini_model: str = "gemini-3.1-flash-lite",
    timeout: float = 20.0,
    http_post: Optional[Callable[..., Any]] = None,
    total_budget_seconds: float = 30.0,
) -> DiverseRiskAdvisorResponse:
    active_symbols = req.analysis.symbols if req.analysis is not None else req.selected_stocks
    sector_breakdown, country_breakdown = _lookup_metadata(active_symbols)
    missing_sectors = [s for s in DEFENSIVE_CORE_SECTORS if s not in sector_breakdown]

    if req.analysis is not None:
        det_answer, actions = _build_question_aware_analysis(
            req.question, req.analysis, sector_breakdown, missing_sectors, req.market_scope
        )
    else:
        det_answer, actions = _build_standalone_conversational_reply(
            req.question,
            active_symbols,
            sector_breakdown,
            missing_sectors,
            req.market_scope,
            req.portfolio_summary,
            llm_configured=bool(gemini_api_key),
        )

    disclaimer = (
        "Quantitative diversification analysis is grounded in historical sample correlations and "
        "minimum-variance math. For research and educational use only — not investment advice."
    )

    if gemini_api_key:
        post_fn = http_post or httpx.post
        if req.analysis is not None:
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
        else:
            context_payload = {
                "market_scope": req.market_scope or "Global",
                "selected_sectors": req.selected_sectors,
                "selected_stocks": active_symbols,
                "sector_breakdown_pct": sector_breakdown,
                "country_breakdown_pct": country_breakdown,
                "missing_defensive_sectors": missing_sectors,
                "portfolio_10y_summary": req.portfolio_summary or "Not yet simulated",
            }
        system_text = (
            "You are a warm, sharp, down-to-earth senior portfolio manager chatting directly with the user like a real human colleague. "
            "Keep the conversation completely natural:\n"
            "- If the user greets you ('Hi', 'Good morning', 'Chào bạn') or makes small talk, respond warmly in 1-2 short natural sentences without lecturing or dumping stats.\n"
            "- Remember what was said earlier in the conversation so follow-up questions ('what about the second one?', 'what if I drop CEO?') flow naturally.\n"
            "- When the user asks about stocks, sectors, weights, or risk, give direct, opinionated, practical answers referencing their live portfolio context below — never sound like a stiff template or say 'As a Senior Portfolio Manager reviewing...'.\n"
            "- Reply in the exact language the user writes in (Vietnamese or English). Do NOT use raw '**' markdown asterisks; write clean natural text.\n"
            "- Never fabricate live prices or promise guaranteed returns.\n\n"
            f"CURRENT LIVE PORTFOLIO CONTEXT (use only when relevant to the user's message):\n{json.dumps(context_payload, indent=2)}"
        )

        contents_turns: List[Dict[str, Any]] = []
        for turn in req.conversation_history[-16:]:
            g_role = "model" if turn.role == "assistant" else "user"
            contents_turns.append({"role": g_role, "parts": [{"text": turn.content}]})
        contents_turns.append({"role": "user", "parts": [{"text": req.question}]})

        gemini_payload: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": contents_turns,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 700},
        }

        endpoints: List[tuple[str, str, Dict[str, str], Dict[str, str]]] = []
        models_to_try = list(dict.fromkeys(["gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-flash-latest", "gemini-3.1-flash-lite-preview", gemini_model]))
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

        import time as _time

        # Hard wall-clock budget across ALL model/endpoint/retry attempts. Without it the worst
        # case was len(endpoints) x 2 attempts x timeout (several minutes) per user message.
        deadline = _time.monotonic() + max(1.0, total_budget_seconds)
        for model_name, url, headers, params in endpoints:
            if _time.monotonic() >= deadline - 0.5:
                logger.warning("Gemini time budget (%.0fs) exhausted; using deterministic strategist.", total_budget_seconds)
                break
            for attempt in range(2):
                remaining = deadline - _time.monotonic()
                if remaining <= 0.5:
                    break
                try:
                    resp = post_fn(
                        url,
                        headers=headers,
                        params=params,
                        json=gemini_payload,
                        timeout=min(timeout, remaining),
                    )
                    status = getattr(resp, "status_code", 200)
                    if status == 200:
                        data = resp.json()
                        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        text_chunks = [
                            p.get("text", "")
                            for p in parts
                            if isinstance(p, dict) and isinstance(p.get("text"), str) and not p.get("thought")
                        ]
                        text = "\n".join(c.strip() for c in text_chunks if c.strip())
                        if not text and parts and isinstance(parts[-1], dict):
                            text = str(parts[-1].get("text") or "").strip()
                        if text:
                            clean_text = text.replace("**", "")
                            return DiverseRiskAdvisorResponse(
                                answer=clean_text,
                                engine_used=f"Gemini ({model_name})",
                                used_llm=True,
                                sector_breakdown=sector_breakdown,
                                country_breakdown=country_breakdown,
                                missing_defensive_sectors=missing_sectors,
                                recommended_actions=actions,
                                disclaimer=disclaimer,
                            )
                        break
                    elif status in (503, 429) and attempt == 0:
                        logger.warning("Gemini %s busy (HTTP %s), retrying once...", model_name, status)
                        _time.sleep(0.9)
                        continue
                    else:
                        logger.warning("Gemini endpoint %s returned HTTP %s", url, status)
                        break
                except Exception as exc:
                    logger.warning("Gemini endpoint %s failed: %s", url, exc)
                    break

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
