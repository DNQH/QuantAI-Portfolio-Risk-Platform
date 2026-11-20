/**
 * English-only UI string catalog (Phase 1).
 * Structured as a typed dictionary so additional locales (e.g. vi.ts)
 * can be added later without modifying component logic.
 */
export const en = {
  brand: {
    name: 'QuantAI',
    subtitle: 'Global Quantitative Investment Research & Financial Risk Platform',
    phaseBadge: 'Phase 1 · Core Foundation',
  },
  nav: {
    overview: 'Overview Dashboard',
    marketData: 'Global Market Data',
    quantAnalysis: 'Quantitative Analysis',
    portfolio: 'Portfolio Manager',
    risk: 'Risk Analytics',
    fx: 'FX Analytics',
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
    searchPlaceholder: 'Search by ticker, company, exchange MIC, country, or sector (e.g. AAPL, FPT, VNM)...',
  },
} as const;

export type LocaleDictionary = typeof en;
