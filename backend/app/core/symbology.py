"""ISO 10383 MIC registry and effective-dated exchange/ticker mapping (v3.0.0).

Includes 10 iconic flagship stocks per major exchange across all 11 GICS sectors:
  - Technology, Financial Services, Healthcare, Consumer Defensive, Consumer Cyclical,
    Energy, Industrials, Basic Materials, Utilities, Real Estate, Communication Services.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from app.core.models import AssetType, Instrument

HNX_LAST_TRADING_DATE = date(2026, 12, 23)
HNX_MIGRATION_SUSPENSION_DATES = frozenset({date(2026, 12, 24), date(2026, 12, 25)})
HNX_TO_HOSE_EFFECTIVE_DATE = date(2026, 12, 28)

ALL_GICS_SECTORS: Tuple[str, ...] = (
    "Technology",
    "Financial Services",
    "Healthcare",
    "Consumer Defensive",
    "Consumer Cyclical",
    "Energy",
    "Industrials",
    "Basic Materials",
    "Utilities",
    "Real Estate",
    "Communication Services",
)


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
    "XUPC": "UPCOM",
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
    "XUPC": ".VN",
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


def _inst(
    mic: str, ticker: str, name: str, country: str, ccy: str, sector: str, tz: str,
    asset_type: AssetType = AssetType.EQUITY, note: Optional[str] = None
) -> Instrument:
    return Instrument(
        instrument_id=f"{mic}:{ticker}",
        ticker=ticker,
        exchange_mic=mic,
        exchange_acronym=MIC_TO_ACRONYM.get(mic, mic),
        company_name=name,
        country=country,
        currency=ccy,
        sector=sector,
        industry=sector,
        asset_type=asset_type,
        timezone=tz,
        migration_note=note,
    )


def _vn_hose(ticker: str, name: str, sector: str) -> Instrument:
    return _inst("XSTC", ticker, name, "Vietnam", "VND", sector, "Asia/Ho_Chi_Minh")


def _vn_hnx(ticker: str, name: str, sector: str) -> Instrument:
    return _inst(
        "XHAI", ticker, name, "Vietnam", "VND", sector, "Asia/Ho_Chi_Minh",
        note="Scheduled transfer from HNX (XHAI) to HOSE (XSTC) effective 2026-12-28.",
    )


def _vn_upcom(ticker: str, name: str, sector: str) -> Instrument:
    return _inst("XUPC", ticker, name, "Vietnam", "VND", sector, "Asia/Ho_Chi_Minh")


GLOBAL_INSTRUMENTS: List[Instrument] = [
    # --- United States: NASDAQ (10 Iconic Flagships) ---
    _inst("XNAS", "AAPL", "Apple Inc.", "United States", "USD", "Technology", "America/New_York"),
    _inst("XNAS", "MSFT", "Microsoft Corporation", "United States", "USD", "Technology", "America/New_York"),
    _inst("XNAS", "NVDA", "NVIDIA Corporation", "United States", "USD", "Technology", "America/New_York"),
    _inst("XNAS", "AMZN", "Amazon.com, Inc.", "United States", "USD", "Consumer Cyclical", "America/New_York"),
    _inst("XNAS", "GOOGL", "Alphabet Inc. Class A", "United States", "USD", "Communication Services", "America/New_York"),
    _inst("XNAS", "META", "Meta Platforms, Inc.", "United States", "USD", "Communication Services", "America/New_York"),
    _inst("XNAS", "TSLA", "Tesla, Inc.", "United States", "USD", "Consumer Cyclical", "America/New_York"),
    _inst("XNAS", "AVGO", "Broadcom Inc.", "United States", "USD", "Technology", "America/New_York"),
    _inst("XNAS", "COST", "Costco Wholesale Corporation", "United States", "USD", "Consumer Defensive", "America/New_York"),
    _inst("XNAS", "NFLX", "Netflix, Inc.", "United States", "USD", "Communication Services", "America/New_York"),
    # --- United States: NYSE (10 Iconic Flagships + ETFs) ---
    _inst("XNYS", "JPM", "JPMorgan Chase & Co.", "United States", "USD", "Financial Services", "America/New_York"),
    _inst("XNYS", "BRK.B", "Berkshire Hathaway Inc. Class B", "United States", "USD", "Financial Services", "America/New_York"),
    _inst("XNYS", "JNJ", "Johnson & Johnson", "United States", "USD", "Healthcare", "America/New_York"),
    _inst("XNYS", "XOM", "Exxon Mobil Corporation", "United States", "USD", "Energy", "America/New_York"),
    _inst("XNYS", "WMT", "Walmart Inc.", "United States", "USD", "Consumer Defensive", "America/New_York"),
    _inst("XNYS", "V", "Visa Inc.", "United States", "USD", "Financial Services", "America/New_York"),
    _inst("XNYS", "UNH", "UnitedHealth Group Incorporated", "United States", "USD", "Healthcare", "America/New_York"),
    _inst("XNYS", "CAT", "Caterpillar Inc.", "United States", "USD", "Industrials", "America/New_York"),
    _inst("XNYS", "NEE", "NextEra Energy, Inc.", "United States", "USD", "Utilities", "America/New_York"),
    _inst("XNYS", "PLD", "Prologis, Inc.", "United States", "USD", "Real Estate", "America/New_York"),
    _inst("XNYS", "LIN", "Linde plc", "United States", "USD", "Basic Materials", "America/New_York"),
    _inst("XNYS", "SPY", "SPDR S&P 500 ETF Trust", "United States", "USD", "Broad Market", "America/New_York", AssetType.ETF),
    _inst("XNYS", "VNM", "VanEck Vietnam ETF", "United States", "USD", "International Equity", "America/New_York", AssetType.ETF),

    # --- Vietnam: HOSE (Top 10 Iconic + Full VN30) ---
    _vn_hose("FPT", "FPT Corporation", "Technology"),
    _vn_hose("VCB", "Vietcombank", "Financial Services"),
    _vn_hose("VNM", "Vietnam Dairy Products JSC (Vinamilk)", "Consumer Defensive"),
    _vn_hose("HPG", "Hoa Phat Group JSC", "Basic Materials"),
    _vn_hose("TCB", "Techcombank", "Financial Services"),
    _vn_hose("MWG", "Mobile World Investment Corp", "Consumer Cyclical"),
    _vn_hose("GAS", "PetroVietnam Gas JSC (PV GAS)", "Energy"),
    _vn_hose("VIC", "Vingroup JSC", "Real Estate"),
    _vn_hose("REE", "Refrigeration Electrical Engineering Corp", "Industrials"),
    _vn_hose("POW", "PetroVietnam Power Corporation", "Utilities"),
    _vn_hose("VHM", "Vinhomes JSC", "Real Estate"),
    _vn_hose("VRE", "Vincom Retail JSC", "Real Estate"),
    _vn_hose("MBB", "MBBank", "Financial Services"),
    _vn_hose("ACB", "Asia Commercial JSB", "Financial Services"),
    _vn_hose("CTG", "VietinBank", "Financial Services"),
    _vn_hose("BID", "BIDV", "Financial Services"),
    _vn_hose("VPB", "VPBank", "Financial Services"),
    _vn_hose("STB", "Sacombank", "Financial Services"),
    _vn_hose("HDB", "HDBank", "Financial Services"),
    _vn_hose("SSI", "SSI Securities Corporation", "Financial Services"),
    _vn_hose("MSN", "Masan Group Corporation", "Consumer Defensive"),
    _vn_hose("SAB", "Sabeco", "Consumer Defensive"),
    _vn_hose("PLX", "Petrolimex", "Energy"),
    _vn_hose("DGC", "Duc Giang Chemicals Group JSC", "Basic Materials"),
    _vn_hose("DHG", "DHG Pharmaceutical JSC", "Healthcare"),
    _vn_hose("PNJ", "Phu Nhuan Jewelry JSC", "Consumer Cyclical"),
    _vn_hose("GVR", "Vietnam Rubber Group JSC", "Basic Materials"),
    _vn_hose("BCM", "Becamex IDC Corporation", "Real Estate"),
    _vn_hose("BVH", "Bao Viet Holdings", "Financial Services"),
    _vn_hose("VCI", "Vietcap Securities JSC", "Financial Services"),

    # --- Vietnam: HNX (10 Iconic) ---
    _vn_hnx("SHS", "Saigon - Hanoi Securities JSC", "Financial Services"),
    _vn_hnx("PVS", "PetroVietnam Technical Services Corp", "Energy"),
    _vn_hnx("IDC", "IDICO Corporation - JSC", "Industrials"),
    _vn_hnx("CEO", "C.E.O Group JSC", "Real Estate"),
    _vn_hnx("MBS", "MB Securities JSC", "Financial Services"),
    _vn_hnx("NTP", "Tien Phong Plastic JSC", "Basic Materials"),
    _vn_hnx("VCS", "Vicostone JSC", "Basic Materials"),
    _vn_hnx("HUT", "Tasco JSC", "Industrials"),
    _vn_hnx("TNG", "TNG Investment and Trading JSC", "Consumer Cyclical"),
    _vn_hnx("LAS", "Lam Thao Fertilizers & Chemicals JSC", "Basic Materials"),

    # --- Vietnam: UPCOM (10 Iconic) ---
    _vn_upcom("ACV", "Airports Corporation of Vietnam JSC", "Industrials"),
    _vn_upcom("MCH", "Masan Consumer Corporation", "Consumer Defensive"),
    _vn_upcom("VEA", "Vietnam Engine & Agricultural Machinery", "Industrials"),
    _vn_upcom("QNS", "Quang Ngai Sugar JSC", "Consumer Defensive"),
    _vn_upcom("FOX", "FPT Telecom JSC", "Communication Services"),
    _vn_upcom("VGI", "Viettel Global Investment JSC", "Communication Services"),
    _vn_upcom("BSR", "Binh Son Refining & Petrochemical JSC", "Energy"),
    _vn_upcom("OIL", "PetroVietnam Oil Corporation (PVOIL)", "Energy"),
    _vn_upcom("MVN", "Vietnam Maritime Corporation (VIMC)", "Industrials"),
    _vn_upcom("PHP", "Port of Hai Phong JSC", "Industrials"),

    # --- United Kingdom: LSE (10 Iconic) ---
    _inst("XLON", "HSBA", "HSBC Holdings plc", "United Kingdom", "GBP", "Financial Services", "Europe/London"),
    _inst("XLON", "SHEL", "Shell plc", "United Kingdom", "GBP", "Energy", "Europe/London"),
    _inst("XLON", "AZN", "AstraZeneca PLC", "United Kingdom", "GBP", "Healthcare", "Europe/London"),
    _inst("XLON", "ULVR", "Unilever PLC", "United Kingdom", "GBP", "Consumer Defensive", "Europe/London"),
    _inst("XLON", "BP", "BP p.l.c.", "United Kingdom", "GBP", "Energy", "Europe/London"),
    _inst("XLON", "GSK", "GSK plc", "United Kingdom", "GBP", "Healthcare", "Europe/London"),
    _inst("XLON", "RIO", "Rio Tinto Group", "United Kingdom", "GBP", "Basic Materials", "Europe/London"),
    _inst("XLON", "DGE", "Diageo plc", "United Kingdom", "GBP", "Consumer Defensive", "Europe/London"),
    _inst("XLON", "BARC", "Barclays PLC", "United Kingdom", "GBP", "Financial Services", "Europe/London"),
    _inst("XLON", "NG", "National Grid plc", "United Kingdom", "GBP", "Utilities", "Europe/London"),

    # --- Germany: Xetra (10 Iconic) ---
    _inst("XETR", "SAP", "SAP SE", "Germany", "EUR", "Technology", "Europe/Berlin"),
    _inst("XETR", "SIE", "Siemens AG", "Germany", "EUR", "Industrials", "Europe/Berlin"),
    _inst("XETR", "ALV", "Allianz SE", "Germany", "EUR", "Financial Services", "Europe/Berlin"),
    _inst("XETR", "DTE", "Deutsche Telekom AG", "Germany", "EUR", "Communication Services", "Europe/Berlin"),
    _inst("XETR", "MBG", "Mercedes-Benz Group AG", "Germany", "EUR", "Consumer Cyclical", "Europe/Berlin"),
    _inst("XETR", "BMW", "Bayerische Motoren Werke AG", "Germany", "EUR", "Consumer Cyclical", "Europe/Berlin"),
    _inst("XETR", "BAS", "BASF SE", "Germany", "EUR", "Basic Materials", "Europe/Berlin"),
    _inst("XETR", "ADS", "adidas AG", "Germany", "EUR", "Consumer Cyclical", "Europe/Berlin"),
    _inst("XETR", "MUV2", "Munich Re", "Germany", "EUR", "Financial Services", "Europe/Berlin"),
    _inst("XETR", "IFX", "Infineon Technologies AG", "Germany", "EUR", "Technology", "Europe/Berlin"),

    # --- Japan: TSE (10 Iconic) ---
    _inst("XTKS", "7203", "Toyota Motor Corporation", "Japan", "JPY", "Consumer Cyclical", "Asia/Tokyo"),
    _inst("XTKS", "6758", "Sony Group Corporation", "Japan", "JPY", "Technology", "Asia/Tokyo"),
    _inst("XTKS", "9984", "SoftBank Group Corp.", "Japan", "JPY", "Communication Services", "Asia/Tokyo"),
    _inst("XTKS", "8306", "Mitsubishi UFJ Financial Group", "Japan", "JPY", "Financial Services", "Asia/Tokyo"),
    _inst("XTKS", "6861", "Keyence Corporation", "Japan", "JPY", "Technology", "Asia/Tokyo"),
    _inst("XTKS", "7974", "Nintendo Co., Ltd.", "Japan", "JPY", "Communication Services", "Asia/Tokyo"),
    _inst("XTKS", "9432", "Nippon Telegraph and Telephone", "Japan", "JPY", "Communication Services", "Asia/Tokyo"),
    _inst("XTKS", "8035", "Tokyo Electron Limited", "Japan", "JPY", "Technology", "Asia/Tokyo"),
    _inst("XTKS", "4502", "Takeda Pharmaceutical Company", "Japan", "JPY", "Healthcare", "Asia/Tokyo"),
    _inst("XTKS", "6501", "Hitachi, Ltd.", "Japan", "JPY", "Industrials", "Asia/Tokyo"),

    # --- Hong Kong: HKEX (10 Iconic) ---
    _inst("XHKG", "0700", "Tencent Holdings Limited", "Hong Kong", "HKD", "Communication Services", "Asia/Hong_Kong"),
    _inst("XHKG", "9988", "Alibaba Group Holding Limited", "Hong Kong", "HKD", "Consumer Cyclical", "Asia/Hong_Kong"),
    _inst("XHKG", "3690", "Meituan", "Hong Kong", "HKD", "Consumer Cyclical", "Asia/Hong_Kong"),
    _inst("XHKG", "0939", "China Construction Bank Corp", "Hong Kong", "HKD", "Financial Services", "Asia/Hong_Kong"),
    _inst("XHKG", "1299", "AIA Group Limited", "Hong Kong", "HKD", "Financial Services", "Asia/Hong_Kong"),
    _inst("XHKG", "0005", "HSBC Holdings plc (HK)", "Hong Kong", "HKD", "Financial Services", "Asia/Hong_Kong"),
    _inst("XHKG", "0941", "China Mobile Limited", "Hong Kong", "HKD", "Communication Services", "Asia/Hong_Kong"),
    _inst("XHKG", "1211", "BYD Company Limited", "Hong Kong", "HKD", "Consumer Cyclical", "Asia/Hong_Kong"),
    _inst("XHKG", "0388", "Hong Kong Exchanges and Clearing", "Hong Kong", "HKD", "Financial Services", "Asia/Hong_Kong"),
    _inst("XHKG", "0883", "CNOOC Limited", "Hong Kong", "HKD", "Energy", "Asia/Hong_Kong"),

    # --- Singapore: SGX (10 Iconic) ---
    _inst("XSES", "D05", "DBS Group Holdings Ltd", "Singapore", "SGD", "Financial Services", "Asia/Singapore"),
    _inst("XSES", "O39", "Oversea-Chinese Banking Corp", "Singapore", "SGD", "Financial Services", "Asia/Singapore"),
    _inst("XSES", "U11", "United Overseas Bank Limited", "Singapore", "SGD", "Financial Services", "Asia/Singapore"),
    _inst("XSES", "Z74", "Singapore Telecommunications", "Singapore", "SGD", "Communication Services", "Asia/Singapore"),
    _inst("XSES", "C6L", "Singapore Airlines Limited", "Singapore", "SGD", "Industrials", "Asia/Singapore"),
    _inst("XSES", "BN4", "Keppel Ltd.", "Singapore", "SGD", "Industrials", "Asia/Singapore"),
    _inst("XSES", "F34", "Wilmar International Limited", "Singapore", "SGD", "Consumer Defensive", "Asia/Singapore"),
    _inst("XSES", "C38U", "CapitaLand Integrated Commercial Trust", "Singapore", "SGD", "Real Estate", "Asia/Singapore"),
    _inst("XSES", "A17U", "CapitaLand Ascendas REIT", "Singapore", "SGD", "Real Estate", "Asia/Singapore"),
    _inst("XSES", "S68", "Singapore Exchange Limited", "Singapore", "SGD", "Financial Services", "Asia/Singapore"),

    # --- Australia: ASX (10 Iconic) ---
    _inst("XASX", "BHP", "BHP Group Limited", "Australia", "AUD", "Basic Materials", "Australia/Sydney"),
    _inst("XASX", "CBA", "Commonwealth Bank of Australia", "Australia", "AUD", "Financial Services", "Australia/Sydney"),
    _inst("XASX", "CSL", "CSL Limited", "Australia", "AUD", "Healthcare", "Australia/Sydney"),
    _inst("XASX", "NAB", "National Australia Bank", "Australia", "AUD", "Financial Services", "Australia/Sydney"),
    _inst("XASX", "WBC", "Westpac Banking Corporation", "Australia", "AUD", "Financial Services", "Australia/Sydney"),
    _inst("XASX", "ANZ", "ANZ Group Holdings Limited", "Australia", "AUD", "Financial Services", "Australia/Sydney"),
    _inst("XASX", "FMG", "Fortescue Ltd", "Australia", "AUD", "Basic Materials", "Australia/Sydney"),
    _inst("XASX", "WDS", "Woodside Energy Group Ltd", "Australia", "AUD", "Energy", "Australia/Sydney"),
    _inst("XASX", "WES", "Wesfarmers Limited", "Australia", "AUD", "Consumer Cyclical", "Australia/Sydney"),
    _inst("XASX", "MQG", "Macquarie Group Limited", "Australia", "AUD", "Financial Services", "Australia/Sydney"),

    # --- Additional Europe & Asia ---
    _inst("XPAR", "MC", "LVMH Moet Hennessy Louis Vuitton", "France", "EUR", "Consumer Cyclical", "Europe/Paris"),
    _inst("XSWX", "NESN", "Nestle S.A.", "Switzerland", "CHF", "Consumer Defensive", "Europe/Zurich"),
    _inst("XMIL", "ENEL", "Enel S.p.A.", "Italy", "EUR", "Utilities", "Europe/Rome"),
    _inst("XKRX", "005930", "Samsung Electronics Co., Ltd.", "South Korea", "KRW", "Technology", "Asia/Seoul"),
    _inst("XIDX", "BBCA", "PT Bank Central Asia Tbk", "Indonesia", "IDR", "Financial Services", "Asia/Jakarta"),
    _inst("XBKK", "PTT", "PTT Public Company Limited", "Thailand", "THB", "Energy", "Asia/Bangkok"),
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
        eff_mic, eff_acronym, _, note = resolve_effective_exchange(
            inst.ticker, inst.exchange_mic, as_of=as_of
        )
        effective_inst = inst.copy(
            update={
                "instrument_id": f"{eff_mic}:{inst.ticker}",
                "exchange_mic": eff_mic,
                "exchange_acronym": eff_acronym,
                "migration_note": note or inst.migration_note,
            }
        )
        if ex_filter and effective_inst.exchange_mic != ex_filter and effective_inst.exchange_acronym.upper() != ex_filter:
            continue
        if country_filter and country_filter not in effective_inst.country.lower():
            continue
        if sector_filter and (not effective_inst.sector or sector_filter not in effective_inst.sector.lower()):
            continue
        if q:
            haystack = f"{effective_inst.ticker} {effective_inst.instrument_id} {effective_inst.company_name} {effective_inst.sector or ''}".lower()
            if q not in haystack:
                continue
        results.append(effective_inst)
    return results
