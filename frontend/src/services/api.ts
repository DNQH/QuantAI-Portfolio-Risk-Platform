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


export interface PredictionMarketContract {
  platform: string;
  title: string;
  yes_probability: number;
  no_probability: number;
  volume_usd: number;
  end_date: string | null;
  url: string;
  relevance: 'direct_company' | 'macro_sector';
  sentiment_tilt: number;
}

export interface SocialSignalPost {
  platform: string;
  source_channel: string;
  title: string;
  published_at: string;
  url: string;
  engagement: number;
  polarity_score: number;
  label: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
}

export interface CrowdSentimentResponse {
  instrument_id: string;
  ticker: string;
  company_name: string;
  horizon: '1W' | '1M' | '3M';
  evaluated_at_utc: string;
  verdict: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  crowd_score: number;
  predicted_positive_probability: number;
  model_name: string;
  model_summary: string;
  component_scores: {
    polymarket_tilt_pct: number;
    social_news_polarity_pct: number;
    price_momentum_confirmation_pct: number;
  };
  live_sources_connected: string[];
  polymarket_contracts: PredictionMarketContract[];
  social_posts: SocialSignalPost[];
  methodology_notes: string[];
}

export interface BankruptcyPipelineResponse {
  instrument_id: string;
  ticker: string;
  company_name: string;
  currency: string;
  data_source: string;
  computed_at_utc: string;
  financials: {
    total_assets: number;
    current_assets: number;
    current_liabilities: number;
    total_liabilities: number;
    total_debt: number;
    retained_earnings: number;
    ebit: number;
    ebitda: number;
    net_income: number;
    revenue: number;
    interest_expense: number;
    operating_cash_flow: number;
    market_cap: number;
  };
  variables: Array<{
    category: 'Liquidity' | 'Leverage' | 'Profitability' | 'Cash Flow';
    name: string;
    value: number;
    formatted: string;
    interpretation: string;
  }>;
  models: Array<{
    model_name: string;
    raw_score: number;
    raw_score_formatted: string;
    implied_pd_12m: number;
    zone: 'SAFE' | 'WATCH' | 'DISTRESS';
    formula_summary: string;
    plain_english: string;
  }>;
  ensemble_pd_12m: number;
  ensemble_pd_pct: number;
  risk_grade: string;
  risk_zone: 'SAFE' | 'WATCH' | 'DISTRESS';
  executive_summary: string;
  notes: string[];
}

export interface PortfolioBacktestResponse {
  instrument_ids: string[];
  allocation_method: string;
  rebalance_frequency: string;
  executed_at_utc: string;
  start_date: string;
  end_date: string;
  years_covered: number;
  observations: number;
  initial_capital: number;
  final_portfolio_value: number;
  total_return: number;
  cagr: number;
  annualized_volatility: number;
  sharpe_ratio: number | null;
  max_drawdown: number;
  rebalance_count: number;
  total_transaction_costs: number;
  benchmark_final_value: number;
  benchmark_total_return: number;
  benchmark_cagr: number;
  target_weights: Record<string, number>;
  timestamps: string[];
  equity_curve: number[];
  benchmark_curve: number[];
  calendar_year_returns: Array<{
    year: number;
    portfolio_return: number;
    benchmark_return: number;
  }>;
  assumptions: string[];
}


export interface StockAllocationItem {
  instrument_id: string;
  ticker: string;
  company_name: string;
  sector: string;
  weight: number;
  allocated_capital: number;
  annualized_volatility: number;
}

export interface ForwardScenarioHorizon {
  horizon_years: number;
  bear_value: number;
  base_value: number;
  bull_value: number;
  bear_cagr: number;
  base_cagr: number;
  bull_cagr: number;
  prob_positive: number;
}

export interface PortfolioSimulationResponse {
  executed_at_utc: string;
  currency: string;
  initial_capital: number;
  allocation_method: string;
  rebalance_frequency: string;
  start_date: string;
  end_date: string;
  years_covered: number;
  observations: number;
  allocations: StockAllocationItem[];
  portfolio_volatility: number;
  weighted_avg_stock_volatility: number;
  risk_reduction_pct: number;
  diversification_ratio: number;
  final_portfolio_value: number;
  total_return: number;
  cagr: number;
  sharpe_ratio: number | null;
  max_drawdown: number;
  benchmark_final_value: number;
  benchmark_cagr: number;
  timestamps: string[];
  equity_curve: number[];
  benchmark_curve: number[];
  calendar_year_returns: Array<{
    year: number;
    portfolio_return: number;
    benchmark_return: number;
  }>;
  forward_scenarios: ForwardScenarioHorizon[];
  excluded_tickers?: Array<{ ticker: string; reason: string }>;
  pm_verdict: string;
  assumptions: string[];
}


export interface RiskFactorSummary {
  risk_id: string;
  name: string;
  category: string;
  current_intensity: 'HIGH' | 'ELEVATED' | 'MODERATE';
  trend: 'ESCALATING' | 'PERSISTENT' | 'MODERATING';
  description: string;
  ten_year_episodes: string;
  forward_outlook_12_36m: string;
}

export interface StockRiskImpact {
  instrument_id: string;
  ticker: string;
  company_name: string;
  country: string;
  exchange: string;
  sector: string;
  vulnerability_score: number;
  impact_tier: 'SEVERE' | 'HIGH' | 'MODERATE' | 'LOW / RESILIENT';
  historical_10y_impact: string;
  forward_outlook: string;
}

export interface SectorRiskBreakdown {
  sector: string;
  severity_score: number;
  direction: 'HEADWIND' | 'MIXED' | 'NATURAL HEDGE';
  historical_10y_behavior: string;
  forward_impact_forecast: string;
  stocks_ranked: StockRiskImpact[];
}

export interface EmergingRiskHypothesis {
  title: string;
  probability_tier: 'HIGH' | 'MEDIUM' | 'TAIL RISK';
  horizon: string;
  most_exposed_sectors: string[];
  resilient_hedge_sectors: string[];
  transmission_mechanism: string;
  portfolio_defense: string;
}

export interface RiskTrackerResponse {
  generated_at_utc: string;
  selected_risk_id: string;
  market_filter: string;
  active_risk_factors: RiskFactorSummary[];
  selected_risk: RiskFactorSummary;
  sector_impacts: SectorRiskBreakdown[];
  emerging_hypotheses: EmergingRiskHypothesis[];
  live_macro_signals: string[];
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


  getAssistantStatus: () =>
    fetchJson<{ gemini_configured: boolean; key_prefix: string | null; gemini_model: string }>('/assistant/status'),

  askPortfolioAssistant: (payload: {
    question: string;
    market_scope?: string;
    selected_sectors?: string[];
    selected_stocks?: string[];
    portfolio_summary?: string;
    conversation_history?: Array<{ role: 'user' | 'assistant'; content: string }>;
  }) =>
    fetchJson<DiverseRiskAdvisorResponse>('/portfolio/diverse-risk/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

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

  analyzeCrowdSentiment: (
    instrumentId: string,
    companyName?: string,
    horizon: '1W' | '1M' | '3M' = '1M',
    recentReturn20d?: number,
    annualizedVolatility?: number
  ) =>
    fetchJson<CrowdSentimentResponse>('/sentiment/crowd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instrument_id: instrumentId,
        company_name: companyName,
        horizon,
        recent_return_20d: recentReturn20d ?? null,
        annualized_volatility: annualizedVolatility ?? null,
      }),
    }),


  getRiskTracker: (riskId = 'rates_tightening', market = 'ALL') =>
    fetchJson<RiskTrackerResponse>(
      `/risk/tracker?risk_id=${encodeURIComponent(riskId)}&market=${encodeURIComponent(market)}`
    ),

  runBankruptcyPipeline: (instrumentId: string, equityVolatilityAnnual?: number) =>
    fetchJson<BankruptcyPipelineResponse>('/risk/bankruptcy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instrument_id: instrumentId,
        equity_volatility_annual: equityVolatilityAnnual ?? null,
      }),
    }),


  simulatePortfolio10Y: (payload: {
    instrument_ids: string[];
    capital: number;
    currency: string;
    allocation_method?: 'min_variance' | 'max_sharpe' | 'equal_weight';
    rebalance_frequency?: 'quarterly' | 'annually' | 'buy_and_hold';
    years?: number;
  }) =>
    fetchJson<PortfolioSimulationResponse>('/portfolio/simulate-10y-forecast', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  runPortfolioBacktest: (payload: {
    instrument_ids: string[];
    years?: number;
    allocation_method?: 'equal_weight' | 'min_variance' | 'max_sharpe';
    rebalance_frequency?: 'quarterly' | 'annually' | 'buy_and_hold';
    initial_capital?: number;
  }) =>
    fetchJson<PortfolioBacktestResponse>('/backtesting/portfolio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
};

export const api = quantApi;

