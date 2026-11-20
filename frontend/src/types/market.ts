export type DataStatus =
  | 'LIVE'
  | 'DELAYED'
  | 'HISTORICAL'
  | 'DAILY_REFERENCE'
  | 'DATA_UNAVAILABLE';

export type MarketSession =
  | 'PRE_MARKET'
  | 'REGULAR'
  | 'LUNCH_BREAK'
  | 'AFTER_HOURS'
  | 'CLOSED'
  | 'HOLIDAY'
  | 'MIGRATION_SUSPENDED';

export interface Instrument {
  instrument_id: string;
  ticker: string;
  exchange_mic: string;
  exchange_acronym: string;
  company_name: string;
  country: string;
  currency: string;
  sector: string;
  industry: string;
  asset_type: string;
  timezone: string;
  migration_note?: string | null;
}

export interface QuoteResponse {
  instrument_id: string;
  ticker: string;
  exchange_mic: string;
  currency: string;
  provider: string;
  data_status: DataStatus;
  delay_minutes?: number | null;
  market_session: MarketSession;
  market_timestamp?: string | null;
  retrieval_timestamp: string;
  price?: number | null;
  previous_close?: number | null;
  change?: number | null;
  change_percent?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
  warnings: string[];
  unavailable_reason?: string | null;
}

export interface OHLCVBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  adjusted_close?: number | null;
  volume: number;
}

export interface OHLCVResponse {
  instrument_id: string;
  ticker: string;
  exchange_mic: string;
  currency: string;
  interval: string;
  provider: string;
  data_status: DataStatus;
  market_timestamp?: string | null;
  retrieval_timestamp: string;
  bars: OHLCVBar[];
  warnings: string[];
  unavailable_reason?: string | null;
}

export interface FXRatesResponse {
  base: string;
  provider: string;
  data_status: DataStatus;
  reference_date?: string | null;
  retrieval_timestamp: string;
  rates: Record<string, number>;
  warnings: string[];
  unavailable_reason?: string | null;
}

export interface ExchangeCoverageEntry {
  exchange_mic: string;
  exchange_acronym: string;
  exchange_name: string;
  region: string;
  country: string;
  currency: string;
  timezone: string;
  phase: string;
  coverage_status: string;
  quote_data_status: DataStatus;
  historical_data_status: DataStatus;
  primary_provider: string;
  fallback_provider?: string | null;
  requires_credentials: boolean;
  requires_paid_plan_for_live: boolean;
  notes: string;
}
