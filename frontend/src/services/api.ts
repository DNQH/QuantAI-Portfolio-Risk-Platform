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
  simple_returns: Array<number | null>;
  cumulative_returns: Array<number | null>;
  drawdown_series: number[];
  rsi_14: Array<number | null>;
  assumptions: string[];
}

export interface PortfolioPoint {
  expected_return: number;
  volatility: number;
  sharpe_ratio: number;
  weights: Record<string, number>;
  risk_contributions_pct: Record<string, number>;
}

export interface PortfolioOptimizeResponse {
  symbols: string[];
  aligned_return_observations: number;
  min_variance_portfolio: PortfolioPoint;
  max_sharpe_portfolio: PortfolioPoint;
  equal_weight_portfolio: PortfolioPoint;
  efficient_frontier: PortfolioPoint[];
  assumptions: string[];
}

export interface RiskAnalysisResponse {
  observations: number;
  portfolio_value: number;
  annualized_volatility: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number;
  var_results: Array<{
    method: string;
    confidence_level: number;
    horizon_days: number;
    var_pct: number;
    cvar_pct: number;
    var_amount: number;
    cvar_amount: number;
  }>;
  stress_scenarios: Array<{
    scenario_name: string;
    shock_pct: number;
    estimated_pnl: number;
    post_shock_value: number;
    rationale: string;
  }>;
  assumptions: string[];
}

export interface ForecastResponse {
  instrument_id: string;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  train_samples: number;
  test_samples: number;
  test_timestamps: string[];
  models: Array<{
    model_name: string;
    model_family: string;
    mae: number;
    rmse: number;
    mape_pct: number | null;
    r_squared: number;
    walk_forward_rmse: number;
    next_step_predicted_price: number;
    next_step_predicted_return: number;
    actual_prices: number[];
    predicted_prices: number[];
  }>;
  disclaimer: string;
}

export interface SignalsResponse {
  instrument_id: string;
  composite_signal: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  rules: Array<{
    rule_name: string;
    direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    observed_value: number | null;
    condition: string;
    rationale: string;
  }>;
  disclaimer: string;
}

export interface BacktestResponse {
  instrument_id: string;
  strategy: string;
  initial_capital: number;
  final_portfolio_value: number;
  total_return: number;
  annualized_return: number | null;
  max_drawdown: number;
  sharpe_ratio: number | null;
  number_of_trades: number;
  win_rate: number | null;
  total_transaction_costs: number;
  benchmark_final_value: number;
  benchmark_total_return: number;
  timestamps: string[];
  equity_curve: number[];
  benchmark_curve: number[];
  execution_assumptions: string[];
}


export interface DiverseRiskResponse {
  symbols: string[];
  aligned_return_observations: number;
  is_risk_reducing: boolean;
  verdict: string;
  verdict_summary: string;
  equal_weight_volatility: number;
  standalone_weighted_volatility: number;
  diversification_ratio: number;
  risk_reduction_pct: number;
  gmv_volatility: number;
  gmv_risk_reduction_pct: number;
  avg_pairwise_correlation: number;
  effective_num_bets: number;
  highest_correlation_pairs: Array<{ asset_a: string; asset_b: string; correlation: number }>;
  lowest_correlation_pairs: Array<{ asset_a: string; asset_b: string; correlation: number }>;
  suggested_combinations: Array<{
    symbols: string[];
    portfolio_volatility: number;
    standalone_avg_volatility: number;
    diversification_ratio: number;
    risk_reduction_pct: number;
    avg_pairwise_correlation: number;
    optimal_weights: Record<string, number>;
  }>;
  candidate_additions: Array<{
    symbol: string;
    standalone_volatility: number;
    avg_correlation_with_portfolio: number;
    new_portfolio_volatility: number;
    volatility_change_pct: number;
    is_risk_reducing: boolean;
  }>;
  assumptions: string[];
}


export interface DiverseRiskAdvisorResponse {
  answer: string;
  engine_used: string;
  used_llm: boolean;
  sector_breakdown: Record<string, number>;
  country_breakdown: Record<string, number>;
  missing_defensive_sectors: string[];
  recommended_actions: string[];
  disclaimer: string;
}


export interface MarketBlueprintResponse {
  market_scope: 'US' | 'VN' | 'US_VN' | 'GLOBAL';
  market_label: string;
  recommended_blueprints: Array<{
    name: string;
    sectors: string[];
    rationale: string;
    suggested_tickers: string[];
  }>;
  sectors: Array<{
    sector: string;
    stocks: Array<{
      instrument_id: string;
      ticker: string;
      company_name: string;
      country: string;
      currency: string;
    }>;
  }>;
}

const API_BASE = '/api/v1';

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error (${response.status}): ${text}`);
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

  getQuote: (instrumentId: string, requireLive = false, allowEducationalFallback = true) => {
    const qs = new URLSearchParams({
      require_live: String(requireLive),
      allow_educational_fallback: String(allowEducationalFallback),
    });
    return fetchJson<QuoteResponse>(
      `/market/quote/${encodeURIComponent(instrumentId)}?${qs.toString()}`
    );
  },

  getOhlcv: (
    instrumentId: string,
    options: { startDate?: string; period?: string; interval?: string; allowEducationalFallback?: boolean } = {}
  ) => {
    const qs = new URLSearchParams({
      interval: options.interval ?? '1d',
      allow_educational_fallback: String(options.allowEducationalFallback ?? true),
    });
    if (options.period) qs.set('period', options.period);
    else if (options.startDate) qs.set('start_date', options.startDate);
    return fetchJson<OHLCVResponse>(
      `/market/ohlcv/${encodeURIComponent(instrumentId)}?${qs.toString()}`
    );
  },

  analyzeSingleAsset: (instrumentId: string, bars: OHLCVBar[], riskFreeRateAnnual = 0.04) =>
    fetchJson<SingleAssetAnalyticsResponse>('/analytics/single-asset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instrument_id: instrumentId, bars, risk_free_rate_annual: riskFreeRateAnnual }),
    }),

  getMarketBlueprint: (marketScope: 'US' | 'VN' | 'US_VN' | 'GLOBAL') =>
    fetchJson<MarketBlueprintResponse>(`/portfolio/diverse-risk/blueprint?market_scope=${marketScope}`),

  askDiverseRiskAdvisor: (
    question: string,
    analysis: DiverseRiskResponse,
    marketScope?: string,
    selectedSectors: string[] = []
  ) =>
    fetchJson<DiverseRiskAdvisorResponse>('/portfolio/diverse-risk/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        analysis,
        market_scope: marketScope,
        selected_sectors: selectedSectors,
      }),
    }),

  analyzeDiverseRisk: (
    assetPriceMaps: Record<string, Record<string, number>>,
    candidatePriceMaps: Record<string, Record<string, number>> = {}
  ) =>
    fetchJson<DiverseRiskResponse>('/portfolio/diverse-risk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        asset_price_maps: assetPriceMaps,
        candidate_price_maps: candidatePriceMaps,
      }),
    }),

  optimizePortfolio: (assetPriceMaps: Record<string, Record<string, number>>, rf = 0.04) =>
    fetchJson<PortfolioOptimizeResponse>('/portfolio/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_price_maps: assetPriceMaps, risk_free_rate_annual: rf, frontier_points: 15 }),
    }),

  analyzeRisk: (returns: number[], portfolioValue = 100000) =>
    fetchJson<RiskAnalysisResponse>('/risk/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ returns, portfolio_value: portfolioValue }),
    }),

  runForecast: (instrumentId: string, bars: OHLCVBar[]) =>
    fetchJson<ForecastResponse>('/forecasting/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instrument_id: instrumentId, bars, test_ratio: 0.2 }),
    }),

  evaluateSignals: (instrumentId: string, bars: OHLCVBar[]) =>
    fetchJson<SignalsResponse>('/signals/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instrument_id: instrumentId, bars }),
    }),

  runBacktest: (
    instrumentId: string,
    bars: OHLCVBar[],
    strategy: 'sma_crossover' | 'rsi_mean_reversion' | 'buy_and_hold',
    commissionBps = 10,
    slippageBps = 5
  ) =>
    fetchJson<BacktestResponse>('/backtesting/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instrument_id: instrumentId,
        bars,
        strategy,
        commission_bps: commissionBps,
        slippage_bps: slippageBps,
      }),
    }),

  getExchangeCoverage: () => fetchJson<ExchangeCoverageEntry[]>('/exchanges/coverage'),

  convertFx: (base: string, quote: string, amount: number) =>
    fetchJson<{
      base: string;
      quote: string;
      amount: number;
      converted_amount: number | null;
      rate: number | null;
      reference_date: string | null;
      provider: string;
      data_status: string;
    }>(`/fx/convert?base=${encodeURIComponent(base)}&quote=${encodeURIComponent(quote)}&amount=${amount}`),

  getFxRates: (base = 'USD') =>
    fetchJson<FXRatesResponse>(`/fx/rates?base=${encodeURIComponent(base)}`),
};
