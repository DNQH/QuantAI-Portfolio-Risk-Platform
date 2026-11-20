"""ISO 10383 MIC registry and effective-dated exchange/ticker mapping (v1.1.0).

Covers:
  - United States: NYSE (XNYS), NASDAQ (XNAS).
  - Vietnam: Full VN30 + key HOSE (XSTC) and HNX (XHAI -> XSTC effective 2026-12-28) equities.
  - Global Expansion: Europe (XLON, XETR, XPAR, XSWX, XMIL), Asia (XTKS, XHKG, XKRX),
    ASEAN (XSES, XKLS, XIDX, XBKK), and Oceania (XASX).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from app.core.models import AssetType, Instrument

HNX_LAST_TRADING_DATE = date(2026, 12, 23)
HNX_MIGRATION_SUSPENSION_DATES = frozenset({date(2026, 12, 24), date(2026, 12, 25)})
HNX_TO_HOSE_EFFECTIVE_DATE = date(2026, 12, 28)


@dataclass(frozen=True)
class ExchangeTransferRule:
    ticker: str
    from_mic: str
    from_acronym: str
    to_mic: str
    to_acronym: str
    last_old_exchange_date: date
    suspension_dates: frozenset[date]
    effective_date: date
    circular_reference: str


MIC_TO_ACRONYM: Dict[str, str] = {
    "XNYS": "NYSE",
    "XNAS": "NASDAQ",
    "XSTC": "HOSE",
    "XHAI": "HNX",
    "XLON": "LSE",
    "XETR": "Xetra",
    "XPAR": "Euronext",
    "XSWX": "SIX",
    "XMIL": "Borsa Italiana",
    "XTKS": "TSE",
    "XHKG": "HKEX",
    "XKRX": "KRX",
    "XSES": "SGX",
    "XKLS": "Bursa Malaysia",
    "XIDX": "IDX",
    "XBKK": "SET",
    "XASX": "ASX",
}

YFINANCE_SUFFIX_BY_MIC: Dict[str, str] = {
    "XNYS": "",
    "XNAS": "",
    "XSTC": ".VN",
    "XHAI": ".VN",
    "XLON": ".L",
    "XETR": ".DE",
    "XPAR": ".PA",
    "XSWX": ".SW",
    "XMIL": ".MI",
    "XTKS": ".T",
    "XHKG": ".HK",
    "XKRX": ".KS",
    "XSES": ".SI",
    "XKLS": ".KL",
    "XIDX": ".JK",
    "XBKK": ".BK",
    "XASX": ".AX",
}


def _vn_hose(ticker: str, name: str, sector: str) -> Instrument:
    return Instrument(
        instrument_id=f"XSTC:{ticker}",
        ticker=ticker,
        exchange_mic="XSTC",
        exchange_acronym="HOSE",
        company_name=name,
        country="Vietnam",
        currency="VND",
        sector=sector,
        industry=sector,
        asset_type=AssetType.EQUITY,
        timezone="Asia/Ho_Chi_Minh",
    )


def _vn_hnx(ticker: str, name: str, sector: str) -> Instrument:
    return Instrument(
        instrument_id=f"XHAI:{ticker}",
        ticker=ticker,
        exchange_mic="XHAI",
        exchange_acronym="HNX",
        company_name=name,
        country="Vietnam",
        currency="VND",
        sector=sector,
        industry=sector,
        asset_type=AssetType.EQUITY,
        timezone="Asia/Ho_Chi_Minh",
        migration_note="Scheduled transfer from HNX (XHAI) to HOSE (XSTC) effective 2026-12-28.",
    )


GLOBAL_INSTRUMENTS: List[Instrument] = [
    # --- United States ---
    Instrument(instrument_id="XNAS:AAPL", ticker="AAPL", exchange_mic="XNAS", exchange_acronym="NASDAQ", company_name="Apple Inc.", country="United States", currency="USD", sector="Technology", industry="Consumer Electronics", asset_type=AssetType.EQUITY, timezone="America/New_York"),
    Instrument(instrument_id="XNAS:MSFT", ticker="MSFT", exchange_mic="XNAS", exchange_acronym="NASDAQ", company_name="Microsoft Corporation", country="United States", currency="USD", sector="Technology", industry="Software", asset_type=AssetType.EQUITY, timezone="America/New_York"),
    Instrument(instrument_id="XNAS:GOOGL", ticker="GOOGL", exchange_mic="XNAS", exchange_acronym="NASDAQ", company_name="Alphabet Inc. Class A", country="United States", currency="USD", sector="Communication Services", industry="Internet Content", asset_type=AssetType.EQUITY, timezone="America/New_York"),
    Instrument(instrument_id="XNAS:NVDA", ticker="NVDA", exchange_mic="XNAS", exchange_acronym="NASDAQ", company_name="NVIDIA Corporation", country="United States", currency="USD", sector="Technology", industry="Semiconductors", asset_type=AssetType.EQUITY, timezone="America/New_York"),
    Instrument(instrument_id="XNAS:AMZN", ticker="AMZN", exchange_mic="XNAS", exchange_acronym="NASDAQ", company_name="Amazon.com, Inc.", country="United States", currency="USD", sector="Consumer Cyclical", industry="Internet Retail", asset_type=AssetType.EQUITY, timezone="America/New_York"),
    Instrument(instrument_id="XNAS:META", ticker="META", exchange_mic="XNAS", exchange_acronym="NASDAQ", company_name="Meta Platforms, Inc.", country="United States", currency="USD", sector="Communication Services", industry="Internet Content", asset_type=AssetType.EQUITY, timezone="America/New_York"),
    Instrument(instrument_id="XNAS:TSLA", ticker="TSLA", exchange_mic="XNAS", exchange_acronym="NASDAQ", company_name="Tesla, Inc.", country="United States", currency="USD", sector="Consumer Cyclical", industry="Auto Manufacturers", asset_type=AssetType.EQUITY, timezone="America/New_York"),
    Instrument(instrument_id="XNYS:JPM", ticker="JPM", exchange_mic="XNYS", exchange_acronym="NYSE", company_name="JPMorgan Chase & Co.", country="United States", currency="USD", sector="Financial Services", industry="Banks", asset_type=AssetType.EQUITY, timezone="America/New_York"),
    Instrument(instrument_id="XNYS:BRK.B", ticker="BRK.B", exchange_mic="XNYS", exchange_acronym="NYSE", company_name="Berkshire Hathaway Inc. Class B", country="United States", currency="USD", sector="Financial Services", industry="Insurance", asset_type=AssetType.EQUITY, timezone="America/New_York"),
    Instrument(instrument_id="XNYS:SPY", ticker="SPY", exchange_mic="XNYS", exchange_acronym="NYSE", company_name="SPDR S&P 500 ETF Trust", country="United States", currency="USD", sector="Broad Market", industry="ETF", asset_type=AssetType.ETF, timezone="America/New_York"),
    Instrument(instrument_id="XNYS:VNM", ticker="VNM", exchange_mic="XNYS", exchange_acronym="NYSE", company_name="VanEck Vietnam ETF", country="United States", currency="USD", sector="International Equity", industry="ETF", asset_type=AssetType.ETF, timezone="America/New_York"),
    # --- Vietnam HOSE (VN30 + Blue Chips) ---
    _vn_hose("FPT", "FPT Corporation", "Technology"),
    _vn_hose("VNM", "Vietnam Dairy Products JSC (Vinamilk)", "Consumer Defensive"),
    _vn_hose("HPG", "Hoa Phat Group JSC", "Basic Materials"),
    _vn_hose("VCB", "Vietcombank (Joint Stock Commercial Bank for Foreign Trade)", "Financial Services"),
    _vn_hose("VIC", "Vingroup JSC", "Real Estate"),
    _vn_hose("VHM", "Vinhomes JSC", "Real Estate"),
    _vn_hose("VRE", "Vincom Retail JSC", "Real Estate"),
    _vn_hose("TCB", "Techcombank (Vietnam Technological & Commercial JSB)", "Financial Services"),
    _vn_hose("MBB", "Military Commercial Joint Stock Bank (MBBank)", "Financial Services"),
    _vn_hose("ACB", "Asia Commercial Joint Stock Bank", "Financial Services"),
    _vn_hose("CTG", "VietinBank (Vietnam JS Commercial Bank for Industry & Trade)", "Financial Services"),
    _vn_hose("BID", "BIDV (Bank for Investment and Development of Vietnam)", "Financial Services"),
    _vn_hose("VPB", "VPBank (Vietnam Prosperity JS Commercial Bank)", "Financial Services"),
    _vn_hose("STB", "Sacombank (Saigon Thuong Tin Commercial JSB)", "Financial Services"),
    _vn_hose("HDB", "HDBank (Ho Chi Minh City Development JSB)", "Financial Services"),
    _vn_hose("SSI", "SSI Securities Corporation", "Financial Services"),
    _vn_hose("VND", "VNDIRECT Securities Corporation", "Financial Services"),
    _vn_hose("HCM", "Ho Chi Minh City Securities Corporation (HSC)", "Financial Services"),
    _vn_hose("MWG", "Mobile World Investment Corporation", "Consumer Cyclical"),
    _vn_hose("MSN", "Masan Group Corporation", "Consumer Defensive"),
    _vn_hose("GAS", "PetroVietnam Gas JSC (PV GAS)", "Energy"),
    _vn_hose("SAB", "Sabeco (Saigon Beer - Alcohol - Beverage Corp)", "Consumer Defensive"),
    _vn_hose("PLX", "Vietnam National Petroleum Group (Petrolimex)", "Energy"),
    _vn_hose("POW", "PetroVietnam Power Corporation", "Utilities"),
    _vn_hose("GVR", "Vietnam Rubber Group JSC", "Basic Materials"),
    _vn_hose("BCM", "Becamex IDC Corporation", "Real Estate"),
    _vn_hose("BVH", "Bao Viet Holdings", "Financial Services"),
    _vn_hose("PNJ", "Phu Nhuan Jewelry JSC", "Consumer Cyclical"),
    _vn_hose("REE", "Refrigeration Electrical Engineering Corp", "Industrials"),
    _vn_hose("DGC", "Duc Giang Chemicals Group JSC", "Basic Materials"),
    # --- Vietnam HNX (Scheduled transfer to HOSE 2026-12-28) ---
    _vn_hnx("SHS", "Saigon - Hanoi Securities JSC", "Financial Services"),
    _vn_hnx("PVS", "PetroVietnam Technical Services Corporation", "Energy"),
    _vn_hnx("IDC", "IDICO Corporation - JSC", "Industrials"),
    _vn_hnx("CEO", "C.E.O Group JSC", "Real Estate"),
    _vn_hnx("MBS", "MB Securities JSC", "Financial Services"),
    _vn_hnx("NTP", "Tien Phong Plastic JSC", "Basic Materials"),
    _vn_hnx("VCS", "Vicostone JSC", "Basic Materials"),
    # --- Europe ---
    Instrument(instrument_id="XLON:HSBA", ticker="HSBA", exchange_mic="XLON", exchange_acronym="LSE", company_name="HSBC Holdings plc", country="United Kingdom", currency="GBP", sector="Financial Services", industry="Banks", asset_type=AssetType.EQUITY, timezone="Europe/London"),
    Instrument(instrument_id="XETR:SAP", ticker="SAP", exchange_mic="XETR", exchange_acronym="Xetra", company_name="SAP SE", country="Germany", currency="EUR", sector="Technology", industry="Software", asset_type=AssetType.EQUITY, timezone="Europe/Berlin"),
    Instrument(instrument_id="XPAR:MC", ticker="MC", exchange_mic="XPAR", exchange_acronym="Euronext", company_name="LVMH Moet Hennessy Louis Vuitton SE", country="France", currency="EUR", sector="Consumer Cyclical", industry="Luxury Goods", asset_type=AssetType.EQUITY, timezone="Europe/Paris"),
    Instrument(instrument_id="XSWX:NESN", ticker="NESN", exchange_mic="XSWX", exchange_acronym="SIX", company_name="Nestle S.A.", country="Switzerland", currency="CHF", sector="Consumer Defensive", industry="Packaged Foods", asset_type=AssetType.EQUITY, timezone="Europe/Zurich"),
    Instrument(instrument_id="XMIL:ENEL", ticker="ENEL", exchange_mic="XMIL", exchange_acronym="Borsa Italiana", company_name="Enel S.p.A.", country="Italy", currency="EUR", sector="Utilities", industry="Utilities", asset_type=AssetType.EQUITY, timezone="Europe/Rome"),
    # --- Asia, ASEAN & Oceania ---
    Instrument(instrument_id="XTKS:7203", ticker="7203", exchange_mic="XTKS", exchange_acronym="TSE", company_name="Toyota Motor Corporation", country="Japan", currency="JPY", sector="Consumer Cyclical", industry="Auto Manufacturers", asset_type=AssetType.EQUITY, timezone="Asia/Tokyo"),
    Instrument(instrument_id="XHKG:0700", ticker="0700", exchange_mic="XHKG", exchange_acronym="HKEX", company_name="Tencent Holdings Limited", country="Hong Kong", currency="HKD", sector="Communication Services", industry="Internet Content", asset_type=AssetType.EQUITY, timezone="Asia/Hong_Kong"),
    Instrument(instrument_id="XKRX:005930", ticker="005930", exchange_mic="XKRX", exchange_acronym="KRX", company_name="Samsung Electronics Co., Ltd.", country="South Korea", currency="KRW", sector="Technology", industry="Semiconductors", asset_type=AssetType.EQUITY, timezone="Asia/Seoul"),
    Instrument(instrument_id="XSES:D05", ticker="D05", exchange_mic="XSES", exchange_acronym="SGX", company_name="DBS Group Holdings Ltd", country="Singapore", currency="SGD", sector="Financial Services", industry="Banks", asset_type=AssetType.EQUITY, timezone="Asia/Singapore"),
    Instrument(instrument_id="XIDX:BBCA", ticker="BBCA", exchange_mic="XIDX", exchange_acronym="IDX", company_name="PT Bank Central Asia Tbk", country="Indonesia", currency="IDR", sector="Financial Services", industry="Banks", asset_type=AssetType.EQUITY, timezone="Asia/Jakarta"),
    Instrument(instrument_id="XBKK:PTT", ticker="PTT", exchange_mic="XBKK", exchange_acronym="SET", company_name="PTT Public Company Limited", country="Thailand", currency="THB", sector="Energy", industry="Oil & Gas", asset_type=AssetType.EQUITY, timezone="Asia/Bangkok"),
    Instrument(instrument_id="XASX:BHP", ticker="BHP", exchange_mic="XASX", exchange_acronym="ASX", company_name="BHP Group Limited", country="Australia", currency="AUD", sector="Basic Materials", industry="Metals & Mining", asset_type=AssetType.EQUITY, timezone="Australia/Sydney"),
]

PHASE1_INSTRUMENTS = GLOBAL_INSTRUMENTS

HNX_TRANSFER_RULES: Dict[str, ExchangeTransferRule] = {
    inst.ticker: ExchangeTransferRule(
        ticker=inst.ticker,
        from_mic="XHAI",
        from_acronym="HNX",
        to_mic="XSTC",
        to_acronym="HOSE",
        last_old_exchange_date=HNX_LAST_TRADING_DATE,
        suspension_dates=HNX_MIGRATION_SUSPENSION_DATES,
        effective_date=HNX_TO_HOSE_EFFECTIVE_DATE,
        circular_reference="Vietnam MOF Circular 139/2025/TT-BTC (VNX consolidation)",
    )
    for inst in GLOBAL_INSTRUMENTS
    if inst.exchange_mic == "XHAI"
}


def resolve_effective_exchange(
    ticker: str,
    requested_mic: str,
    as_of: Optional[date] = None,
) -> Tuple[str, str, bool, Optional[str]]:
    ref_date = as_of or date.today()
    upper_ticker = ticker.upper().strip()
    upper_mic = requested_mic.upper().strip()

    rule = HNX_TRANSFER_RULES.get(upper_ticker)
    if rule and upper_mic in {rule.from_mic, rule.to_mic}:
        if ref_date < rule.effective_date:
            if ref_date in rule.suspension_dates:
                return (
                    rule.from_mic,
                    rule.from_acronym,
                    True,
                    f"{upper_ticker} is suspended on {ref_date.isoformat()} during scheduled HNX-to-HOSE transfer (effective {rule.effective_date.isoformat()}).",
                )
            return (
                rule.from_mic,
                rule.from_acronym,
                False,
                f"Active on {rule.from_acronym} ({rule.from_mic}) as of {ref_date.isoformat()}; scheduled transfer to {rule.to_acronym} ({rule.to_mic}) on {rule.effective_date.isoformat()}.",
            )
        return (
            rule.to_mic,
            rule.to_acronym,
            False,
            f"Transferred from {rule.from_acronym} ({rule.from_mic}) to {rule.to_acronym} ({rule.to_mic}) effective {rule.effective_date.isoformat()}.",
        )

    return upper_mic, MIC_TO_ACRONYM.get(upper_mic, upper_mic), False, None


def to_yfinance_symbol(ticker: str, exchange_mic: str) -> str:
    mic = exchange_mic.upper().strip()
    clean = ticker.upper().strip()
    if mic in {"XNYS", "XNAS"}:
        return clean.replace(".", "-")
    suffix = YFINANCE_SUFFIX_BY_MIC.get(mic, "")
    return f"{clean}{suffix}"


def parse_instrument_id(instrument_id: str) -> Tuple[str, str]:
    if ":" not in instrument_id:
        raise ValueError(
            f"Instrument identifier '{instrument_id}' must be exchange-qualified as 'MIC:TICKER' (e.g., 'XNAS:AAPL', 'XSTC:FPT')."
        )
    mic, ticker = instrument_id.split(":", 1)
    mic = mic.strip().upper()
    ticker = ticker.strip().upper()
    if not mic or not ticker:
        raise ValueError(f"Invalid exchange-qualified identifier: '{instrument_id}'")
    return mic, ticker


def search_seed_instruments(
    query: str = "",
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    sector: Optional[str] = None,
    as_of: Optional[date] = None,
) -> List[Instrument]:
    q = query.strip().lower()
    ex_filter = exchange.strip().upper() if exchange else None
    country_filter = country.strip().lower() if country else None
    sector_filter = sector.strip().lower() if sector else None

    results: List[Instrument] = []
    for inst in GLOBAL_INSTRUMENTS:
        eff_mic, eff_acronym, _, eff_note = resolve_effective_exchange(
            inst.ticker, inst.exchange_mic, as_of=as_of
        )
        effective_inst = inst.copy(
            update={
                "exchange_mic": eff_mic,
                "exchange_acronym": eff_acronym,
                "instrument_id": f"{eff_mic}:{inst.ticker}",
                "migration_note": eff_note or inst.migration_note,
            }
        )
        if ex_filter and ex_filter not in {effective_inst.exchange_mic, effective_inst.exchange_acronym.upper()}:
            continue
        if country_filter and country_filter not in effective_inst.country.lower():
            continue
        if sector_filter and sector_filter not in effective_inst.sector.lower():
            continue
        if q:
            haystack = " ".join(
                [
                    effective_inst.instrument_id,
                    effective_inst.ticker,
                    effective_inst.company_name,
                    effective_inst.exchange_mic,
                    effective_inst.exchange_acronym,
                    effective_inst.country,
                    effective_inst.sector,
                    effective_inst.industry,
                ]
            ).lower()
            if q not in haystack:
                continue
        results.append(effective_inst)
    return results
