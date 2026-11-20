import type {
  ExchangeCoverageEntry,
  FXRatesResponse,
  Instrument,
  OHLCVBar,
  OHLCVResponse,
  QuoteResponse,
} from '../types/market';

export interface SingleAssetSummaryMetrics {
  observations: number;
  total_return: number | null;
  annualized_return: number | null;
  annualized_volatility: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number | null;
  max_drawdown_recovery_bars: number | null;
  latest_sma_20: number | null;
  latest_sma_50: number | null;
  latest_rsi_14: number | null;
  latest_macd: number | null;
  latest_atr_14: number | null;
  skewness: number | null;
  excess_kurtosis: number | null;
}

export interface SingleAssetAnalyticsResponse {
  instrument_id: string;
  interval: string;
  computed_at_utc: string;
  summary: SingleAssetSummaryMetrics;
  timestamps: string[];
  cumulative_returns: Array<number | null>;
  drawdown_series: number[];
  rsi_14: Array<number | null>;
  assumptions: string[];
}

const API_BASE = '/api/v1';

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    throw new Error(`API request failed (${response.status}): ${path}`);
  }
  return response.json() as Promise<T>;
}

export const quantApi = {
  searchInstruments: (params: { q?: string; exchange?: string; country?: string }) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set('q', params.q);
    if (params.exchange) qs.set('exchange', params.exchange);
    if (params.country) qs.set('country', params.country);
    return fetchJson<Instrument[]>(`/instruments/search?${qs.toString()}`);
  },

  getQuote: (instrumentId: string, requireLive = false, allowEducationalFallback = false) => {
    const qs = new URLSearchParams({
      require_live: String(requireLive),
      allow_educational_fallback: String(allowEducationalFallback),
    });
    return fetchJson<QuoteResponse>(
      `/market/quote/${encodeURIComponent(instrumentId)}?${qs.toString()}`
    );
  },

  getOhlcv: (instrumentId: string, interval = '1d', allowEducationalFallback = true) => {
    const qs = new URLSearchParams({
      interval,
      allow_educational_fallback: String(allowEducationalFallback),
    });
    return fetchJson<OHLCVResponse>(
      `/market/ohlcv/${encodeURIComponent(instrumentId)}?${qs.toString()}`
    );
  },

  analyzeSingleAsset: (instrumentId: string, bars: OHLCVBar[], riskFreeRateAnnual = 0.0) =>
    fetchJson<SingleAssetAnalyticsResponse>('/analytics/single-asset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instrument_id: instrumentId,
        bars,
        risk_free_rate_annual: riskFreeRateAnnual,
      }),
    }),

  getExchangeCoverage: () => fetchJson<ExchangeCoverageEntry[]>('/exchanges/coverage'),

  getFxRates: (base = 'USD') =>
    fetchJson<FXRatesResponse>(`/fx/rates?base=${encodeURIComponent(base)}`),
};
