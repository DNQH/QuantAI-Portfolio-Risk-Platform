/**
 * English-only UI string catalog (v1.5.0).
 */
export const en = {
  brand: {
    name: 'QuantAI',
    subtitle: 'Global Quantitative Investment Research & Financial Risk Platform',
    phaseBadge: 'v1.5.0 · Full Suite',
  },
  nav: {
    overview: 'Overview Dashboard',
    marketData: 'Global Market Data',
    quantAnalysis: 'Quantitative Analysis',
    portfolio: 'Portfolio Manager',
    risk: 'Risk Analytics',
    fx: 'FX Converter',
    ml: 'Machine Learning',
    signals: 'Quantitative Signals',
    backtesting: 'Backtesting',
    coverage: 'Market Data Coverage',
    methodology: 'Methodology & Docs',
  },
  status: {
    LIVE: 'LIVE',
    DELAYED: 'DELAYED',
    HISTORICAL: 'HISTORICAL',
    DAILY_REFERENCE: 'DAILY REFERENCE',
    DATA_UNAVAILABLE: 'DATA UNAVAILABLE',
  },
  labels: {
    exchangeTimestamp: 'Exchange Timestamp (UTC)',
    retrievalTimestamp: 'Retrieval Timestamp (UTC)',
    provider: 'Data Provider',
    marketSession: 'Market Session',
    noDataWarning: 'No verified market data available. QuantAI never substitutes synthetic prices.',
    plannedNotice: 'Scheduled for upcoming phase — no simulated placeholders displayed.',
    searchPlaceholder: 'Search or type MIC:TICKER + Enter (e.g. XSTC:TCB)...',
  },
} as const;

export type LocaleDictionary = typeof en;
