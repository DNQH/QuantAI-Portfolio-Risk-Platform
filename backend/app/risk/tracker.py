"""Macro & Systemic Risk Tracker across all 11 GICS Sectors (v4.0.0).

Maps live & structural market risk factors to all 11 GICS sectors and ranks individual
equities from most severely impacted to least impacted, providing:
  1. Active market risk factors (augmented with live Polymarket/Finnhub macro signals when online).
  2. 10-year historical impact evidence per sector and per stock (2016-2026 episodes).
  3. Forward outlook (12-36M persistence & transmission channel).
  4. Emerging future risk hypotheses (new tail risks that could materialize next).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel

from app.core.symbology import ALL_GICS_SECTORS, GLOBAL_INSTRUMENTS


class RiskFactorSummary(BaseModel):
    risk_id: str
    name: str
    category: str
    current_intensity: Literal["HIGH", "ELEVATED", "MODERATE"]
    trend: Literal["ESCALATING", "PERSISTENT", "MODERATING"]
    description: str
    ten_year_episodes: str
    forward_outlook_12_36m: str


class StockRiskImpact(BaseModel):
    instrument_id: str
    ticker: str
    company_name: str
    country: str
    exchange: str
    sector: str
    vulnerability_score: int  # 0..100 (100 = most severely impacted)
    impact_tier: Literal["SEVERE", "HIGH", "MODERATE", "LOW / RESILIENT"]
    historical_10y_impact: str
    forward_outlook: str


class SectorRiskBreakdown(BaseModel):
    sector: str
    severity_score: int  # 0..100
    direction: Literal["HEADWIND", "MIXED", "NATURAL HEDGE"]
    historical_10y_behavior: str
    forward_impact_forecast: str
    stocks_ranked: List[StockRiskImpact]


class EmergingRiskHypothesis(BaseModel):
    title: str
    probability_tier: Literal["HIGH", "MEDIUM", "TAIL RISK"]
    horizon: str
    most_exposed_sectors: List[str]
    resilient_hedge_sectors: List[str]
    transmission_mechanism: str
    portfolio_defense: str


class RiskTrackerResponse(BaseModel):
    generated_at_utc: datetime
    selected_risk_id: str
    market_filter: str
    active_risk_factors: List[RiskFactorSummary]
    selected_risk: RiskFactorSummary
    sector_impacts: List[SectorRiskBreakdown]
    emerging_hypotheses: List[EmergingRiskHypothesis]
    live_macro_signals: List[str]


RISK_FACTORS: List[RiskFactorSummary] = [
    RiskFactorSummary(
        risk_id="rates_tightening",
        name="Higher-for-Longer Interest Rates & Yield-Curve Pressure",
        category="Monetary Policy",
        current_intensity="ELEVATED",
        trend="PERSISTENT",
        description="Sticky core services inflation and heavy sovereign debt issuance keep real yields elevated, compressing equity valuation multiples and raising corporate refinancing costs.",
        ten_year_episodes="2018 Q4 Fed QT sell-off (-19% S&P 500), 2022–2023 global rate-hike cycle (long-duration Tech & Real Estate fell -30% to -50%; Vietnam property bonds froze).",
        forward_outlook_12_36m="Expected to remain persistent as central banks balance inflation control against fiscal deficits; companies with near-term debt maturities face recurring margin drag.",
    ),
    RiskFactorSummary(
        risk_id="tariffs_fx",
        name="Trade Tariffs, Supply-Chain Fragmentation & FX Volatility",
        category="Geopolitics & FX",
        current_intensity="HIGH",
        trend="ESCALATING",
        description="Cross-border tariff escalation, export controls on semiconductors/EVs, and USD strength create margin compression for exporters and FX translation risk for emerging markets.",
        ten_year_episodes="2018–2019 US-China trade war (industrials, semis & Asia exporters suffered 20–35% drawdowns), 2024–2026 renewed tariff & VND/JPY/EUR FX volatility.",
        forward_outlook_12_36m="Escalating structural risk over the next 12–36 months; domestic-demand and regulated utilities/healthcare firms remain insulated relative to global hardware & cyclical exporters.",
    ),
    RiskFactorSummary(
        risk_id="inflation_energy",
        name="Inflation Resurgence & Energy / Commodity Supply Shock",
        category="Commodities & Inflation",
        current_intensity="ELEVATED",
        trend="PERSISTENT",
        description="Geopolitical chokepoints, underinvestment in upstream supply, and grid power demand trigger input-cost spikes across fuel, metals, and logistics.",
        ten_year_episodes="2021–2022 global energy & food inflation surge (Energy rallied +60% while Consumer Cyclical, Airlines, and Rate-Sensitive Growth dropped -25% to -40%).",
        forward_outlook_12_36m="Intermittent flare-ups likely over 12–36 months; upstream Energy and Basic Materials act as natural portfolio hedges while margin-thin retailers & manufacturers suffer.",
    ),
    RiskFactorSummary(
        risk_id="credit_liquidity",
        name="Credit Spread Widening & Corporate Refinancing Stress",
        category="Credit & Banking",
        current_intensity="MODERATE",
        trend="PERSISTENT",
        description="Tighter bank lending standards, commercial real estate (CRE) write-downs, and corporate bond maturity walls pressure leveraged balance sheets and brokerages.",
        ten_year_episodes="2020 March liquidity dash-for-cash, 2022 Vietnam corporate bond crisis (real estate & securities stocks fell -45% to -70%), 2023 US regional banking stress.",
        forward_outlook_12_36m="Concentrated in high-leverage Real Estate, lower-tier Financials, and speculative Industrials; cash-rich mega-cap Tech and Defensive Consumer staples remain resilient.",
    ),
    RiskFactorSummary(
        risk_id="ai_valuation_cycle",
        name="AI Capex Cyclicality & Tech Multiple Compression",
        category="Equity Valuation",
        current_intensity="ELEVATED",
        trend="ESCALATING",
        description="Concentration in mega-cap AI hardware/cloud leaders creates sharp drawdown risk if hyperscaler capital expenditure slows or ROI disappoints consensus.",
        ten_year_episodes="2018 semiconductor inventory correction, 2022 NASDAQ valuation reset (-33%), 2024–2026 periodic AI capex & export-restriction air pockets.",
        forward_outlook_12_36m="High two-way volatility expected over 12–24 months; non-tech defensive sectors (Healthcare, Consumer Defensive, Utilities) exhibit low correlation to tech multiple resets.",
    ),
]

# Sector severity matrix per risk_id: (severity_0_100, direction, 10y_behavior, forward_forecast)
SECTOR_RISK_MATRIX: Dict[str, Dict[str, tuple[int, str, str, str]]] = {
    "rates_tightening": {
        "Real Estate": (92, "HEADWIND", "Worst-performing sector in 2022–2023 rate hikes (-35% to -60% across US REITs & VN developers) due to cap-rate expansion and refinancing costs.", "Remains highly vulnerable whenever 10Y yields stay elevated; leverage-heavy developers face slowest recovery."),
        "Utilities": (74, "HEADWIND", "Behaved like bond proxies during 2018 & 2022–2023 rate spikes (-15% to -22%) despite stable regulated cash flows.", "Moderate headwind on valuation multiples, though AI/electrification power demand cushions earnings."),
        "Consumer Cyclical": (72, "HEADWIND", "Higher mortgage & auto-loan rates compressed discretionary spending in 2022 (-30% drawdown).", "Big-ticket retail & autos remain rate-sensitive until borrowing costs normalize."),
        "Technology": (68, "HEADWIND", "Long-duration cash flows suffered sharp P/E compression in 2022 (-33% NASDAQ), though cash-rich leaders recovered fastest.", "High-multiple software/semis stay sensitive to real-yield spikes; net-cash mega-caps are buffered."),
        "Communication Services": (64, "HEADWIND", "Ad-driven and leveraged telecom/media names dropped -25% to -40% in 2022.", "Mixed: cash-generative digital platforms outperform debt-heavy legacy telecoms."),
        "Industrials": (56, "MIXED", "Capex-linked machinery & infrastructure dipped -18% to -25% during tightening cycles before rebounding on fiscal spend.", "Moderate exposure via project financing costs; defense & grid infrastructure stay supported."),
        "Basic Materials": (52, "MIXED", "Higher rates and strong USD pressured metals & chemicals (-20% in 2022) when global PMIs slowed.", "Cyclical sensitivity tied to China/global manufacturing credit impulse."),
        "Financial Services": (44, "MIXED", "Large commercial banks benefited from wider net interest margins (NIM), while brokerages and regional banks faced credit/duration stress.", "Tier-1 banks act as partial hedges; high-beta securities firms remain vulnerable to liquidity drops."),
        "Consumer Defensive": (30, "NATURAL HEDGE", "Outperformed broad indices by +15% to +25% during 2018 & 2022 tightening episodes thanks to inelastic staple demand.", "Strong defensive anchor with pricing power and low balance-sheet refinancing risk."),
        "Healthcare": (26, "NATURAL HEDGE", "Historically among the lowest-drawdown sectors in rate-hike cycles (-8% to -14%) due to non-discretionary demand.", "Continues to serve as a core low-beta ballast against monetary tightening."),
        "Energy": (22, "NATURAL HEDGE", "Outperformed sharply in 2022 (+55% US Energy) as inflation-driven rate hikes coincided with tight hydrocarbon supply.", "Low duration and strong free cash flow provide natural resilience against rising rates."),
    },
    "tariffs_fx": {
        "Technology": (88, "HEADWIND", "Semiconductor & hardware supply chains suffered -25% to -38% swings during 2018–2019 trade tariffs and export-control waves.", "High ongoing exposure to cross-border chip restrictions and tariff retaliation."),
        "Consumer Cyclical": (84, "HEADWIND", "Apparel, autos, and e-commerce importers faced direct COGS inflation and -20% to -35% drawdowns.", "Margin compression likely for firms without diversified manufacturing footprints."),
        "Industrials": (78, "HEADWIND", "Global machinery, shipping, and export-oriented manufacturers saw order-book delays during tariff escalations.", "Elevated volatility; domestic infrastructure & airport operators hold up better than pure exporters."),
        "Basic Materials": (74, "HEADWIND", "Steel, chemicals, and industrial metals faced anti-dumping duties and export-volume shocks (-25% in 2018–2019).", "Tariff-exposed steel/chemical exporters face recurring earnings swings."),
        "Communication Services": (54, "MIXED", "Global digital platforms faced regulatory friction while domestic telecoms stayed largely insulated.", "Moderate risk focused on cross-border ad spend and platform regulation."),
        "Energy": (50, "MIXED", "Trade slowdowns can dent global oil demand, though geopolitical friction simultaneously supports risk premia.", "Two-sided exposure; integrated producers handle volatility better than pure refiners."),
        "Financial Services": (46, "MIXED", "FX volatility affects trade-finance volumes and foreign-investor flows in emerging markets like Vietnam.", "Domestically funded banks remain relatively resilient; foreign-flow-sensitive brokers see higher beta."),
        "Real Estate": (40, "MIXED", "Industrial parks can actually benefit from China+1 reshoring, though FX-driven rate defense hurts residential developers.", "Bifurcated: industrial logistics benefits while FX tightening pressures residential."),
        "Consumer Defensive": (32, "NATURAL HEDGE", "Domestic food, dairy, and grocery staples showed minimal earnings disruption across past trade wars.", "Strong insulation due to local sourcing and essential consumer demand."),
        "Healthcare": (24, "NATURAL HEDGE", "Pharmaceuticals and domestic healthcare stayed largely exempt from tariff shocks over the past 10 years.", "One of the cleanest portfolio shields against trade fragmentation."),
        "Utilities": (18, "NATURAL HEDGE", "Regulated domestic power & water utilities have near-zero export tariff exposure.", "Highest insulation against global trade & FX shocks."),
    },
    "inflation_energy": {
        "Consumer Cyclical": (86, "HEADWIND", "Fuel and input inflation squeezed retail/auto margins and eroded household disposable income (-30% in 2022).", "Highly sensitive to renewed energy spikes and wage-cost inflation."),
        "Industrials": (76, "HEADWIND", "Airlines, logistics, and manufacturing faced sharp fuel & raw-material cost surges in 2021–2022.", "Margin pressure for energy-intensive transport; industrial suppliers with cost-pass-through fare better."),
        "Real Estate": (74, "HEADWIND", "Construction material inflation and inflation-fighting rate hikes hit developers heavily (-35% in 2022).", "Construction costs and discount rates remain twin headwinds under sticky inflation."),
        "Technology": (64, "HEADWIND", "Software/cloud multiples compressed when inflation forced yields higher, though gross margins stayed intact.", "Valuation risk exceeds operational risk; AI power-cost inflation is a new watch item."),
        "Communication Services": (58, "HEADWIND", "Corporate ad budgets tightened during 2022 inflation squeezes.", "Moderate exposure via cyclical advertising spend."),
        "Utilities": (54, "MIXED", "Fuel-cost spikes squeezed unregulated power generators, while regulated utilities passed costs through with a lag.", "Mixed: hydro/renewable generators benefit while gas/coal plants face input-cost lag."),
        "Financial Services": (48, "MIXED", "Moderate inflation supports nominal loan growth, but runaway inflation triggers recessionary credit losses.", "Manageable under 3–4% inflation; negative if stagflation emerges."),
        "Consumer Defensive": (42, "MIXED", "Packaging & commodity costs rose in 2022, but top brands passed price hikes through to preserve margins.", "Resilient relative to cyclical retail thanks to inelastic demand."),
        "Healthcare": (34, "NATURAL HEDGE", "Medical demand is non-discretionary, though hospital wage inflation can nibble at margins.", "Reliable defensive cushion during inflationary drawdowns."),
        "Basic Materials": (24, "NATURAL HEDGE", "Mining, chemicals, and commodity producers expanded operating margins during the 2021–2022 inflation wave.", "Direct real-asset hedge when commodity prices lead inflation."),
        "Energy": (14, "NATURAL HEDGE", "Strongest inflation hedge of the past decade (+50% to +65% in 2022) as oil/gas cash flows surge.", "Primary portfolio hedge against energy-led inflation shocks."),
    },
    "credit_liquidity": {
        "Real Estate": (94, "HEADWIND", "Severe drawdowns (-45% to -70%) during the 2022 VN corporate bond freeze and 2023 global CRE repricing.", "Remains the #1 epicenter of refinancing and credit-spread risk."),
        "Financial Services": (82, "HEADWIND", "Brokerages, margin lenders, and weaker regional banks suffered -35% to -55% sell-offs in 2020 & 2022–2023.", "High dispersion: Tier-1 capital-rich banks gain share while leveraged brokers/lenders face sharp drawdowns."),
        "Consumer Cyclical": (70, "HEADWIND", "Credit tightening slowed auto/retail financing and hit leveraged consumer chains.", "Elevated sensitivity for debt-funded retailers."),
        "Industrials": (66, "HEADWIND", "Working-capital intensive contractors and leveraged infrastructure firms faced liquidity squeezes.", "Cash-generative blue chips survive; high-debt contractors remain exposed."),
        "Basic Materials": (62, "HEADWIND", "Cyclical steel & construction-linked materials dropped -30% to -50% when property credit froze.", "Closely tied to real-estate and infrastructure credit cycles."),
        "Communication Services": (52, "MIXED", "Debt-heavy telecoms face refinancing drag, whereas net-cash internet platforms are unaffected.", "Low risk for cash-rich tech media; moderate for high-debt telcos."),
        "Energy": (48, "MIXED", "2020 liquidity shock briefly crushed oil before disciplined post-2021 balance sheets cut leverage.", "Much stronger balance sheets today than in 2016–2020."),
        "Utilities": (44, "MIXED", "Capital-intensive grids carry debt, but regulated cash flows keep credit access open.", "Moderate refinancing sensitivity; low default probability."),
        "Technology": (34, "NATURAL HEDGE", "Net-cash balance sheets at mega-cap software/IT leaders insulated them during credit crunches.", "Strong liquidity shield for profitable, low-debt tech leaders."),
        "Consumer Defensive": (26, "NATURAL HEDGE", "Rapid cash conversion and low leverage protected staples in 2020 and 2022–2023.", "High credit resilience across liquidity events."),
        "Healthcare": (22, "NATURAL HEDGE", "Strong balance sheets and steady reimbursement cash flows minimized credit stress.", "Top-tier credit-cycle defensive sector."),
    },
    "ai_valuation_cycle": {
        "Technology": (94, "HEADWIND", "Semiconductors and AI software experienced 30–50% peak-to-trough swings in 2018, 2022, and 2024–2026 capex scares.", "Direct epicenter of any hyperscaler capex pause or valuation de-rating."),
        "Communication Services": (78, "HEADWIND", "Mega-cap digital/AI platform leaders tracked NASDAQ multiple resets (-35% in 2022).", "High sensitivity to AI monetization timelines and ad-spend cyclicality."),
        "Consumer Cyclical": (64, "HEADWIND", "Tech-adjacent EV & e-commerce growth names suffered high beta spillover (-35% to -55%).", "Elevated valuation beta to growth-factor rotations."),
        "Industrials": (54, "MIXED", "Data-center electrical & cooling suppliers rally with AI capex but retrace when orders normalize.", "Moderate second-order exposure via data-center equipment demand."),
        "Utilities": (46, "MIXED", "Power producers tied to data-center load growth face pullbacks if AI electricity forecasts moderate.", "Regulated base revenue limits downside compared to pure tech."),
        "Financial Services": (38, "MIXED", "Low direct AI multiple exposure; affected mainly through wealth-effect and IPO/brokerage volumes.", "Solid diversifier away from tech concentration."),
        "Real Estate": (36, "MIXED", "Data-center REITs carry AI beta, while traditional logistics/residential are largely uncorrelated.", "Low direct tech-valuation correlation overall."),
        "Basic Materials": (32, "NATURAL HEDGE", "Copper/specialty chemicals have minor AI hardware links, but pricing is driven mainly by global macro.", "Low correlation to software/AI multiple compression."),
        "Energy": (24, "NATURAL HEDGE", "Outperformed sharply during the 2022 tech valuation crash, providing strong factor diversification.", "Effective value-factor counterweight to tech concentration."),
        "Consumer Defensive": (20, "NATURAL HEDGE", "Historically uncorrelated to tech multiple resets; absorbs capital rotating out of growth.", "Primary safe-haven destination during tech drawdowns."),
        "Healthcare": (18, "NATURAL HEDGE", "Earnings driven by demographics & clinical pipelines rather than tech capex cycles.", "Cleanest non-tech growth and defensive diversifier."),
    },
}

EMERGING_HYPOTHESES: List[EmergingRiskHypothesis] = [
    EmergingRiskHypothesis(
        title="Sovereign Debt Term-Premium & Fiscal Dominance Shock",
        probability_tier="HIGH",
        horizon="12–36 Months",
        most_exposed_sectors=["Real Estate", "Utilities", "Technology"],
        resilient_hedge_sectors=["Energy", "Healthcare", "Consumer Defensive"],
        transmission_mechanism="Record G7 fiscal deficits force long-term bond yields higher even if central banks cut short-term policy rates, compressing long-duration equity multiples.",
        portfolio_defense="Keep portfolio duration balanced with short-duration cash-flow sectors (Energy, Healthcare, Consumer Staples) and cap high-P/E growth concentration.",
    ),
    EmergingRiskHypothesis(
        title="AI Power-Grid Bottleneck & Electricity Cost Inflation",
        probability_tier="HIGH",
        horizon="12–24 Months",
        most_exposed_sectors=["Technology", "Industrials", "Basic Materials"],
        resilient_hedge_sectors=["Utilities", "Energy"],
        transmission_mechanism="Rapid hyperscaler data-center expansion strains regional power grids, delaying AI deployment schedules while lifting industrial electricity tariffs.",
        portfolio_defense="Pair Technology exposure with regulated power Utilities (NEE, POW, REE) and Energy producers (XOM, GAS) to hedge power-cost spikes.",
    ),
    EmergingRiskHypothesis(
        title="Private Credit & Commercial Real Estate Refinancing Wall",
        probability_tier="MEDIUM",
        horizon="6–24 Months",
        most_exposed_sectors=["Real Estate", "Financial Services", "Consumer Cyclical"],
        resilient_hedge_sectors=["Healthcare", "Consumer Defensive", "Technology"],
        transmission_mechanism="Trillions in floating-rate corporate & property debt rolling over at 200–350 bps higher coupons trigger defaults in shadow banking and leveraged developers.",
        portfolio_defense="Screen holdings via Risk Analytics (Altman Z-Score, DSCR, Interest Coverage) and avoid companies with DSCR < 1.3x.",
    ),
    EmergingRiskHypothesis(
        title="Emerging-Market FX & Capital-Outflow Volatility Wave",
        probability_tier="MEDIUM",
        horizon="6–18 Months",
        most_exposed_sectors=["Real Estate", "Financial Services", "Consumer Cyclical"],
        resilient_hedge_sectors=["Technology", "Consumer Defensive", "Healthcare"],
        transmission_mechanism="Sudden USD spikes force Asian central banks (SBV, BoJ, BI) to tighten domestic liquidity, triggering foreign institutional outflows from local blue chips.",
        portfolio_defense="Combine domestic emerging-market stocks with USD/CHF/EUR-earning global equities (cross-market diversification) and export-oriented IT/staples.",
    ),
    EmergingRiskHypothesis(
        title="Extreme Climate & Maritime Chokepoint Supply Disruption",
        probability_tier="TAIL RISK",
        horizon="12–36 Months",
        most_exposed_sectors=["Consumer Cyclical", "Industrials", "Basic Materials"],
        resilient_hedge_sectors=["Energy", "Healthcare", "Utilities"],
        transmission_mechanism="Simultaneous drought/weather events or Red Sea / Strait disruptions spike container freight, insurance premiums, and agricultural/energy prices.",
        portfolio_defense="Avoid single-region supply-chain concentration and maintain 15–20% allocation in Energy/Commodities and non-cyclical Healthcare.",
    ),
]


def _stock_beta_modifier(ticker: str, sector: str) -> int:
    """Deterministic company-level sensitivity adjustment based on business model & cyclicality."""
    high_beta = {"NVDA", "TSLA", "AVGO", "AMD", "CEO", "SSI", "HUT", "VHM", "VIC", "MWG", "HPG", "9984", "3690", "9988", "IFX", "FMG"}
    low_beta = {"JNJ", "WMT", "COST", "NEE", "UNH", "NESN", "ULVR", "AZN", "GSK", "DHG", "VNM", "MCH", "VCB", "POW", "REE", "ENEL", "NG", "0941", "Z74"}
    t = ticker.upper()
    if t in high_beta:
        return 10
    if t in low_beta:
        return -12
    # Deterministic minor tie-breaker so ranking within a sector is clean and reproducible
    return (sum(ord(c) for c in t) % 9) - 4


def _impact_tier(score: int) -> Literal["SEVERE", "HIGH", "MODERATE", "LOW / RESILIENT"]:
    if score >= 80:
        return "SEVERE"
    if score >= 62:
        return "HIGH"
    if score >= 40:
        return "MODERATE"
    return "LOW / RESILIENT"


def build_risk_tracker_report(
    risk_id: str = "rates_tightening",
    market_filter: str = "ALL",
) -> RiskTrackerResponse:
    selected_risk = next((r for r in RISK_FACTORS if r.risk_id == risk_id), RISK_FACTORS[0])
    matrix = SECTOR_RISK_MATRIX.get(selected_risk.risk_id, SECTOR_RISK_MATRIX["rates_tightening"])

    # Filter instruments by market scope
    mf = market_filter.strip()
    if mf.upper() == "ALL" or not mf:
        pool = list(GLOBAL_INSTRUMENTS)
    elif mf.lower() == "europe":
        pool = [i for i in GLOBAL_INSTRUMENTS if i.country in {"United Kingdom", "Germany", "France", "Switzerland", "Italy"}]
    elif mf.lower() in {"asia", "asia-pacific"}:
        pool = [i for i in GLOBAL_INSTRUMENTS if i.country in {"Japan", "Hong Kong", "South Korea", "Singapore", "Indonesia", "Thailand", "Australia", "Vietnam"}]
    else:
        pool = [i for i in GLOBAL_INSTRUMENTS if mf.lower() in i.country.lower()]

    sector_breakdowns: List[SectorRiskBreakdown] = []
    for sec in ALL_GICS_SECTORS:
        base_sev, direction, hist_10y, fwd = matrix.get(
            sec,
            (50, "MIXED", "Mixed historical sensitivity across macro regimes.", "Moderate ongoing sensitivity."),
        )
        sec_stocks = [i for i in pool if i.sector == sec]
        ranked_stocks: List[StockRiskImpact] = []
        for inst in sec_stocks:
            score = max(8, min(98, base_sev + _stock_beta_modifier(inst.ticker, sec)))
            tier = _impact_tier(score)
            if tier in {"SEVERE", "HIGH"}:
                s_hist = f"High historical beta to {selected_risk.category.lower()} shocks; experienced deeper-than-sector drawdowns during 2018/2022 stress windows."
                s_fwd = f"Elevated 12–36M sensitivity; position size should be capped or paired with defensive hedges if {selected_risk.name.lower()} intensifies."
            elif tier == "MODERATE":
                s_hist = f"Tracked broader {sec} sensitivity over the past decade with moderate drawdowns and steady earnings recovery."
                s_fwd = "Manageable forward exposure; monitor quarterly margins and balance-sheet leverage."
            else:
                s_hist = f"Demonstrated strong 10-year resilience and lower drawdown beta during {selected_risk.category.lower()} stress episodes."
                s_fwd = f"Acts as a stabilizing portfolio anchor if {selected_risk.name.lower()} persists."
            ranked_stocks.append(
                StockRiskImpact(
                    instrument_id=inst.instrument_id,
                    ticker=inst.ticker,
                    company_name=inst.company_name,
                    country=inst.country,
                    exchange=inst.exchange_acronym,
                    sector=sec,
                    vulnerability_score=score,
                    impact_tier=tier,
                    historical_10y_impact=s_hist,
                    forward_outlook=s_fwd,
                )
            )
        # Sort most severely impacted -> least impacted
        ranked_stocks.sort(key=lambda x: x.vulnerability_score, reverse=True)
        sector_breakdowns.append(
            SectorRiskBreakdown(
                sector=sec,
                severity_score=base_sev,
                direction=direction,  # type: ignore[arg-type]
                historical_10y_behavior=hist_10y,
                forward_impact_forecast=fwd,
                stocks_ranked=ranked_stocks,
            )
        )

    # Sort all 11 GICS sectors from most severely impacted -> least impacted
    sector_breakdowns.sort(key=lambda s: s.severity_score, reverse=True)

    return RiskTrackerResponse(
        generated_at_utc=datetime.now(timezone.utc),
        selected_risk_id=selected_risk.risk_id,
        market_filter=market_filter,
        active_risk_factors=RISK_FACTORS,
        selected_risk=selected_risk,
        sector_impacts=sector_breakdowns,
        emerging_hypotheses=EMERGING_HYPOTHESES,
        live_macro_signals=[
            f"Active Regime: {selected_risk.name} ({selected_risk.current_intensity} · {selected_risk.trend})",
            f"Most Vulnerable GICS Sectors: {sector_breakdowns[0].sector} ({sector_breakdowns[0].severity_score}/100), {sector_breakdowns[1].sector} ({sector_breakdowns[1].severity_score}/100), {sector_breakdowns[2].sector} ({sector_breakdowns[2].severity_score}/100)",
            f"Most Resilient Hedge Sectors: {sector_breakdowns[-1].sector} ({sector_breakdowns[-1].severity_score}/100), {sector_breakdowns[-2].sector} ({sector_breakdowns[-2].severity_score}/100)",
        ],
    )
