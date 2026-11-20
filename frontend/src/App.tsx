import React, { useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CandlestickChart } from './components/CandlestickChart';
import { DiverseRiskPanel } from './components/DiverseRiskPanel';
import { StatusBadge } from './components/StatusBadge';
import { en } from './i18n/en';
import {
  quantApi,
  type BacktestResponse,
  type ForecastResponse,
  type PortfolioOptimizeResponse,
  type RiskAnalysisResponse,
  type SignalsResponse,
  type SingleAssetAnalyticsResponse,
} from './services/api';
import type {
  ExchangeCoverageEntry,
  FXRatesResponse,
  Instrument,
  OHLCVResponse,
  QuoteResponse,
} from './types/market';

type TabKey =
  | 'overview'
  | 'marketData'
  | 'quantAnalysis'
  | 'portfolio'
  | 'risk'
  | 'fx'
  | 'ml'
  | 'signals'
  | 'backtesting'
  | 'coverage'
  | 'methodology';

const NAV_ITEMS: Array<{ key: TabKey; label: string }> = [
  { key: 'overview', label: en.nav.overview },
  { key: 'marketData', label: en.nav.marketData },
  { key: 'quantAnalysis', label: en.nav.quantAnalysis },
  { key: 'portfolio', label: en.nav.portfolio },
  { key: 'risk', label: en.nav.risk },
  { key: 'fx', label: en.nav.fx },
  { key: 'ml', label: en.nav.ml },
  { key: 'signals', label: en.nav.signals },
  { key: 'backtesting', label: en.nav.backtesting },
  { key: 'coverage', label: en.nav.coverage },
  { key: 'methodology', label: en.nav.methodology },
];

const INTERVALS = ['1m', '5m', '15m', '1h', '1d', '1wk', '1mo'] as const;
const PERIODS: Array<{ label: string; value: string }> = [
  { label: '1M', value: '1mo' },
  { label: '6M', value: '6mo' },
  { label: '1Y', value: '1y' },
  { label: '5Y', value: '5y' },
  { label: 'ALL (IPO)', value: 'max' },
];

const fmtPct = (v: number | null | undefined) => (v == null ? 'N/A' : `${(v * 100).toFixed(2)}%`);
const fmtNum = (v: number | null | undefined, digits = 2) => (v == null ? 'N/A' : v.toFixed(digits));

export const App: React.FC = () => {
  const [darkMode, setDarkMode] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [searchQuery, setSearchQuery] = useState('');
  const [countryFilter, setCountryFilter] = useState<string>('');
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [selectedId, setSelectedId] = useState<string>('XNAS:AAPL');

  // Market Data Explorer controls (defaults to FULL IPO-to-present daily history!)
  const [interval, setInterval] = useState<string>('1d');
  const [period, setPeriod] = useState<string>('max');

  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [ohlcv, setOhlcv] = useState<OHLCVResponse | null>(null);
  const [dailyOhlcv, setDailyOhlcv] = useState<OHLCVResponse | null>(null);
  const [analytics, setAnalytics] = useState<SingleAssetAnalyticsResponse | null>(null);
  const [riskData, setRiskData] = useState<RiskAnalysisResponse | null>(null);
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [signalsData, setSignalsData] = useState<SignalsResponse | null>(null);
  const [backtestStrategy, setBacktestStrategy] = useState<'sma_crossover' | 'rsi_mean_reversion' | 'buy_and_hold'>('sma_crossover');
  const [backtestData, setBacktestData] = useState<BacktestResponse | null>(null);
  const [portfolioAssets, setPortfolioAssets] = useState<string>('XNAS:AAPL, XNAS:MSFT, XSTC:FPT, XSTC:TCB');
  const [portfolioData, setPortfolioData] = useState<PortfolioOptimizeResponse | null>(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [portfolioSubTab, setPortfolioSubTab] = useState<'mpt' | 'diverse'>('diverse');

  const [coverage, setCoverage] = useState<ExchangeCoverageEntry[]>([]);
  const [fxBase, setFxBase] = useState<string>('USD');
  const [fxQuote, setFxQuote] = useState<string>('VND');
  const [fxAmount, setFxAmount] = useState<string>('1000');
  const [fxConverted, setFxConverted] = useState<{ converted_amount: number | null; rate: number | null; reference_date: string | null } | null>(null);
  const [fxRates, setFxRates] = useState<FXRatesResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    quantApi
      .searchInstruments({ q: searchQuery, country: countryFilter || undefined })
      .then(setInstruments)
      .catch(() => setInstruments([]));
  }, [searchQuery, countryFilter]);

  // Fetch quote + full daily history for quantitative models whenever instrument changes
  useEffect(() => {
    setErrorMsg(null);
    setAnalytics(null);
    setRiskData(null);
    setForecastData(null);
    setSignalsData(null);
    setBacktestData(null);

    Promise.all([
      quantApi.getQuote(selectedId, false, true),
      quantApi.getOhlcv(selectedId, { period: 'max', interval: '1d', allowEducationalFallback: true }),
    ])
      .then(([q, dailyResp]) => {
        setQuote(q);
        setDailyOhlcv(dailyResp);
        const recentForQuant = dailyResp.bars.slice(-504); // Last 2 trading years for Sharpe/VaR/ML stability
        if (recentForQuant.length >= 2) {
          quantApi.analyzeSingleAsset(selectedId, recentForQuant, 0.04).then((res) => {
            setAnalytics(res);
            const validRets = res.simple_returns.filter((r): r is number => r !== null);
            if (validRets.length >= 10) {
              quantApi.analyzeRisk(validRets, 100000).then(setRiskData).catch(() => {});
            }
          }).catch(() => {});
        }
        if (recentForQuant.length >= 15) {
          quantApi.evaluateSignals(selectedId, recentForQuant).then(setSignalsData).catch(() => {});
        }
        if (recentForQuant.length >= 40) {
          quantApi.runForecast(selectedId, recentForQuant).then(setForecastData).catch(() => {});
        }
        if (recentForQuant.length >= 25) {
          quantApi.runBacktest(selectedId, recentForQuant, backtestStrategy).then(setBacktestData).catch(() => {});
        }
      })
      .catch((err) => setErrorMsg(String(err)));
  }, [selectedId]);

  // Fetch interactive candlestick chart bars whenever instrument, interval, or period changes
  useEffect(() => {
    quantApi
      .getOhlcv(selectedId, { period, interval, allowEducationalFallback: true })
      .then(setOhlcv)
      .catch((err) => setErrorMsg(String(err)));
  }, [selectedId, interval, period]);

  useEffect(() => {
    if (dailyOhlcv && dailyOhlcv.bars.length >= 25) {
      quantApi
        .runBacktest(selectedId, dailyOhlcv.bars.slice(-504), backtestStrategy)
        .then(setBacktestData)
        .catch(() => {});
    }
  }, [backtestStrategy]);

  useEffect(() => {
    quantApi.getExchangeCoverage().then(setCoverage).catch(() => setCoverage([]));
  }, []);

  useEffect(() => {
    quantApi.getFxRates(fxBase).then(setFxRates).catch(() => setFxRates(null));
  }, [fxBase]);

  useEffect(() => {
    const amt = parseFloat(fxAmount);
    if (!Number.isFinite(amt) || amt <= 0) return;
    quantApi.convertFx(fxBase, fxQuote, amt).then(setFxConverted).catch(() => setFxConverted(null));
  }, [fxBase, fxQuote, fxAmount]);

  const runPortfolioOptimization = async () => {
    setPortfolioLoading(true);
    setErrorMsg(null);
    try {
      const ids = portfolioAssets.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);
      const priceMaps: Record<string, Record<string, number>> = {};
      await Promise.all(
        ids.map(async (id) => {
          const resp = await quantApi.getOhlcv(id, { period: '1y', interval: '1d', allowEducationalFallback: true });
          if (resp.bars.length >= 10) {
            const map: Record<string, number> = {};
            resp.bars.forEach((b) => {
              map[b.timestamp.slice(0, 10)] = b.adjusted_close ?? b.close;
            });
            priceMaps[id] = map;
          }
        })
      );
      if (Object.keys(priceMaps).length < 2) {
        setErrorMsg('Need at least 2 valid instruments with overlapping historical prices to optimize.');
      } else {
        const res = await quantApi.optimizePortfolio(priceMaps, 0.04);
        setPortfolioData(res);
      }
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setPortfolioLoading(false);
    }
  };

  const downloadOhlcvCsv = () => {
    if (!ohlcv || ohlcv.bars.length === 0) return;
    const header = 'timestamp,open,high,low,close,volume\n';
    const rows = ohlcv.bars.map((b) => `${b.timestamp},${b.open},${b.high},${b.low},${b.close},${b.volume}`).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedId.replace(':', '_')}_${interval}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const chartSeries = useMemo(() => {
    if (!analytics) return [];
    return analytics.timestamps.map((ts, idx) => ({
      date: ts.slice(0, 10),
      cumRetPct: analytics.cumulative_returns[idx] != null ? Number((analytics.cumulative_returns[idx]! * 100).toFixed(2)) : null,
      drawdownPct: Number((analytics.drawdown_series[idx] * 100).toFixed(2)),
    }));
  }, [analytics]);

  const backtestSeries = useMemo(() => {
    if (!backtestData) return [];
    return backtestData.timestamps.map((ts, idx) => ({
      date: ts.slice(0, 10),
      strategy: backtestData.equity_curve[idx],
      benchmark: backtestData.benchmark_curve[idx],
    }));
  }, [backtestData]);

  const histVar95 = riskData?.var_results.find((v) => v.method === 'historical' && Math.abs(v.confidence_level - 0.95) < 0.01);
  const currentNav = NAV_ITEMS.find((n) => n.key === activeTab);
  const shellBg = darkMode ? 'bg-terminal-bg text-slate-100' : 'bg-slate-50 text-slate-900';
  const panelBg = darkMode ? 'bg-terminal-surface border-terminal-border' : 'bg-white border-slate-200';

  return (
    <div className={`min-h-screen flex ${shellBg}`}>
      <aside className={`w-64 shrink-0 border-r p-4 flex flex-col ${panelBg}`}>
        <div className="mb-6 border-b border-terminal-border pb-4 flex items-center justify-between">
          <div>
            <div className="text-lg font-bold tracking-tight">{en.brand.name}</div>
            <div className="mt-1 font-mono text-[11px] text-emerald-400">v1.6.1 · Full Suite</div>
          </div>
          <button onClick={() => setDarkMode((d) => !d)} className="rounded border border-slate-600/40 px-2 py-1 font-mono text-[10px]">
            {darkMode ? 'Light' : 'Dark'}
          </button>
        </div>

        <nav className="space-y-1 flex-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              onClick={() => setActiveTab(item.key)}
              className={`w-full flex items-center justify-between rounded-md px-3 py-2 text-left text-xs font-medium transition ${
                activeTab === item.key ? 'bg-blue-600/20 text-blue-400 border border-blue-500/40' : 'opacity-80 hover:opacity-100'
              }`}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <main className="flex-1 p-6 overflow-y-auto">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-terminal-border pb-4">
          <div>
            <h1 className="text-xl font-bold">{currentNav?.label}</h1>
            <p className="text-xs opacity-70">{en.brand.subtitle}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select value={countryFilter} onChange={(e) => setCountryFilter(e.target.value)} className={`rounded-md border px-2.5 py-1.5 text-xs ${panelBg}`}>
              <option value="">All Markets</option>
              <option value="Vietnam">Vietnam (HOSE/HNX)</option>
              <option value="United States">United States</option>
              <option value="United Kingdom">United Kingdom</option>
              <option value="Germany">Germany</option>
              <option value="Japan">Japan</option>
              <option value="Hong Kong">Hong Kong</option>
              <option value="Singapore">Singapore</option>
              <option value="Australia">Australia</option>
            </select>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && searchQuery.includes(':')) {
                  setSelectedId(searchQuery.trim().toUpperCase());
                }
              }}
              placeholder="Search or type MIC:TICKER + Enter (e.g. XSTC:TCB)..."
              className={`w-80 rounded-md border px-3 py-1.5 text-xs focus:border-blue-500 focus:outline-none ${panelBg}`}
            />
          </div>
        </header>

        {errorMsg && (
          <div className="mb-4 rounded-md border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-400">
            {errorMsg}
          </div>
        )}

        {/* Quick Instrument Strip */}
        {(activeTab === 'overview' || activeTab === 'marketData') && (
          <div className="mb-5 flex flex-wrap gap-2">
            {instruments.slice(0, 18).map((inst) => (
              <button
                key={inst.instrument_id}
                onClick={() => setSelectedId(inst.instrument_id)}
                className={`rounded border px-2.5 py-1 font-mono text-xs ${
                  selectedId === inst.instrument_id ? 'border-blue-500 bg-blue-600/20 text-blue-300' : panelBg
                }`}
              >
                {inst.instrument_id} · {inst.currency}
              </button>
            ))}
          </div>
        )}

        {/* TAB 1: EXECUTIVE OVERVIEW DASHBOARD (Distinct from Global Market Data) */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-6">
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-[11px] opacity-70">Instrument</div>
                <div className="mt-1 font-mono text-base font-bold">{selectedId}</div>
                <div className="mt-2">{quote && <StatusBadge status={quote.data_status} delayMinutes={quote.delay_minutes} />}</div>
              </div>
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-[11px] opacity-70">Verified Price</div>
                <div className="mt-1 font-mono text-base font-bold">
                  {quote?.price != null ? `${quote.price.toLocaleString()} ${quote.currency}` : 'DATA UNAVAILABLE'}
                </div>
                <div className="mt-1 text-[11px] opacity-70">Session: {quote?.market_session ?? 'N/A'}</div>
              </div>
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-[11px] opacity-70">2Y Return / Vol</div>
                <div className="mt-1 font-mono text-base font-bold">
                  {fmtPct(analytics?.summary.annualized_return)} / {fmtPct(analytics?.summary.annualized_volatility)}
                </div>
                <div className="mt-1 text-[11px] opacity-70">Annualized (252d)</div>
              </div>
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-[11px] opacity-70">Sharpe / Max DD</div>
                <div className="mt-1 font-mono text-base font-bold">
                  {fmtNum(analytics?.summary.sharpe_ratio)} / {fmtPct(analytics?.summary.max_drawdown)}
                </div>
                <div className="mt-1 text-[11px] opacity-70">RSI(14): {fmtNum(analytics?.summary.latest_rsi_14)}</div>
              </div>
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-[11px] opacity-70">Composite Signal</div>
                <div className="mt-1 font-mono text-base font-bold text-blue-400">
                  {signalsData?.composite_signal ?? 'N/A'}
                </div>
                <div className="mt-1 text-[11px] opacity-70">
                  {signalsData ? `${signalsData.bullish_count}B / ${signalsData.bearish_count}S` : 'Rules-based'}
                </div>
              </div>
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-[11px] opacity-70">1-Day VaR (95%)</div>
                <div className="mt-1 font-mono text-base font-bold text-amber-400">
                  {fmtPct(histVar95?.var_pct)}
                </div>
                <div className="mt-1 text-[11px] opacity-70">CVaR: {fmtPct(histVar95?.cvar_pct)}</div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div className={`lg:col-span-2 rounded-lg border p-4 ${panelBg}`}>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold">2-Year Cumulative Return &amp; Drawdown Profile</h2>
                  <button onClick={() => setActiveTab('marketData')} className="text-xs text-blue-400 hover:underline">
                    Candle Chart →
                  </button>
                </div>
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartSeries}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Area type="monotone" dataKey="cumRetPct" stroke="#2563EB" fill="#2563EB" fillOpacity={0.18} name="Cumulative Return %" />
                      <Area type="monotone" dataKey="drawdownPct" stroke="#EF4444" fill="#EF4444" fillOpacity={0.18} name="Drawdown %" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className={`rounded-lg border p-4 space-y-3 ${panelBg}`}>
                <h2 className="text-sm font-semibold">Executive Signal &amp; Provenance Snapshot</h2>
                <div className="text-xs space-y-1.5 font-mono opacity-85">
                  <div>Provider: {quote?.provider ?? 'N/A'}</div>
                  <div>Market TS: {quote?.market_timestamp?.slice(0, 19) ?? 'N/A'}</div>
                  <div>History Span: {dailyOhlcv?.bars.length ? `${dailyOhlcv.bars[0].timestamp.slice(0, 10)} → ${dailyOhlcv.bars[dailyOhlcv.bars.length - 1].timestamp.slice(0, 10)}` : 'N/A'}</div>
                  <div>Total Daily Bars: {dailyOhlcv?.bars.length.toLocaleString() ?? 0}</div>
                </div>
                <div className="border-t border-terminal-border pt-3 space-y-2">
                  {signalsData?.rules.slice(0, 4).map((r) => (
                    <div key={r.rule_name} className="flex items-center justify-between text-xs">
                      <span className="opacity-80">{r.rule_name}</span>
                      <span className="font-mono font-semibold">{r.direction}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: GLOBAL MARKET DATA EXPLORER (Full IPO History + Minute/Hour/Day Candles + Volume + Table) */}
        {activeTab === 'marketData' && (
          <div className="space-y-6">
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <div>
                    <span className="text-xs opacity-70 mr-2">Candle Interval:</span>
                    {INTERVALS.map((iv) => (
                      <button
                        key={iv}
                        onClick={() => setInterval(iv)}
                        className={`mr-1 rounded px-2 py-0.5 font-mono text-[11px] border ${
                          interval === iv ? 'border-emerald-500 bg-emerald-600/20 text-emerald-300' : 'border-slate-600/40 opacity-75'
                        }`}
                      >
                        {iv}
                      </button>
                    ))}
                  </div>
                  <div>
                    <span className="text-xs opacity-70 mr-2">Range:</span>
                    {PERIODS.map((p) => (
                      <button
                        key={p.value}
                        onClick={() => setPeriod(p.value)}
                        className={`mr-1 rounded px-2 py-0.5 font-mono text-[11px] border ${
                          period === p.value ? 'border-blue-500 bg-blue-600/20 text-blue-300' : 'border-slate-600/40 opacity-75'
                        }`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {ohlcv && <StatusBadge status={ohlcv.data_status} />}
                  <button onClick={downloadOhlcvCsv} className="rounded border border-slate-600/50 px-2.5 py-1 font-mono text-[11px] hover:border-blue-400">
                    Export CSV
                  </button>
                </div>
              </div>

              <div className="mb-2 text-xs opacity-70 font-mono">
                {ohlcv?.bars.length
                  ? `${selectedId} · Interval: ${interval} · Bars: ${ohlcv.bars.length.toLocaleString()} (${ohlcv.bars[0].timestamp.slice(0, 10)} → ${ohlcv.bars[ohlcv.bars.length - 1].timestamp.slice(0, 10)})`
                  : 'Loading OHLCV bars...'}
              </div>
              <CandlestickChart bars={ohlcv?.bars ?? []} interval={interval} />
              <p className="mt-2 text-[11px] opacity-65">
                Note: Intraday intervals on Yahoo Finance are capped at 7 days (1m), 60 days (5m/15m), and 730 days (1h). Daily/weekly/monthly intervals with ALL (IPO) load full history from listing date to present.
              </p>
            </div>

            <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
              <div className="p-3 border-b border-terminal-border text-xs font-semibold">
                Latest 25 OHLCV Observations ({selectedId} · {interval})
              </div>
              <table className="w-full text-left text-xs">
                <thead className="border-b border-terminal-border font-mono opacity-70">
                  <tr>
                    <th className="p-2.5">Timestamp (UTC)</th>
                    <th className="p-2.5">Open</th>
                    <th className="p-2.5">High</th>
                    <th className="p-2.5">Low</th>
                    <th className="p-2.5">Close</th>
                    <th className="p-2.5">Volume</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-terminal-border font-mono">
                  {(ohlcv?.bars ?? []).slice(-25).reverse().map((b) => (
                    <tr key={b.timestamp}>
                      <td className="p-2.5">{b.timestamp.replace('T', ' ').slice(0, 19)}</td>
                      <td className="p-2.5">{b.open.toLocaleString()}</td>
                      <td className="p-2.5 text-emerald-400">{b.high.toLocaleString()}</td>
                      <td className="p-2.5 text-rose-400">{b.low.toLocaleString()}</td>
                      <td className="p-2.5 font-semibold">{b.close.toLocaleString()}</td>
                      <td className="p-2.5 opacity-80">{b.volume.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'quantAnalysis' && (
          <div className="space-y-6">
            {!analytics ? (
              <div className={`rounded-lg border p-8 text-center text-sm opacity-80 ${panelBg}`}>
                Load historical OHLCV bars for <strong>{selectedId}</strong> to view Quantitative Analysis.
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <div className={`rounded-lg border p-4 ${panelBg}`}>
                    <div className="text-xs opacity-70">Total / Annualized Return</div>
                    <div className="mt-1 font-mono text-base font-bold">
                      {fmtPct(analytics.summary.total_return)} / {fmtPct(analytics.summary.annualized_return)}
                    </div>
                  </div>
                  <div className={`rounded-lg border p-4 ${panelBg}`}>
                    <div className="text-xs opacity-70">Sharpe / Sortino (Rf=4%)</div>
                    <div className="mt-1 font-mono text-base font-bold">
                      {fmtNum(analytics.summary.sharpe_ratio)} / {fmtNum(analytics.summary.sortino_ratio)}
                    </div>
                  </div>
                  <div className={`rounded-lg border p-4 ${panelBg}`}>
                    <div className="text-xs opacity-70">Max Drawdown / Recovery</div>
                    <div className="mt-1 font-mono text-base font-bold text-rose-400">
                      {fmtPct(analytics.summary.max_drawdown)} ({analytics.summary.max_drawdown_recovery_bars ?? 'Unrecovered'} bars)
                    </div>
                  </div>
                  <div className={`rounded-lg border p-4 ${panelBg}`}>
                    <div className="text-xs opacity-70">RSI (14) / Skew / Kurtosis</div>
                    <div className="mt-1 font-mono text-base font-bold">
                      {fmtNum(analytics.summary.latest_rsi_14)} / {fmtNum(analytics.summary.skewness)} / {fmtNum(analytics.summary.excess_kurtosis)}
                    </div>
                  </div>
                </div>
                <div className={`rounded-lg border p-4 ${panelBg}`}>
                  <h2 className="mb-3 text-sm font-semibold">Cumulative Return (%) &amp; Drawdown (%)</h2>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartSeries}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Area type="monotone" dataKey="cumRetPct" stroke="#2563EB" fill="#2563EB" fillOpacity={0.18} name="Cumulative Return %" />
                        <Area type="monotone" dataKey="drawdownPct" stroke="#EF4444" fill="#EF4444" fillOpacity={0.18} name="Drawdown %" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'portfolio' && (
          <div className="space-y-6">
            <div className="flex gap-2 border-b border-terminal-border pb-3">
              <button
                onClick={() => setPortfolioSubTab('mpt')}
                className={`rounded-md px-3.5 py-1.5 text-xs font-semibold border transition ${
                  portfolioSubTab === 'mpt'
                    ? 'border-blue-500 bg-blue-600/20 text-blue-300'
                    : 'border-slate-600/40 opacity-75 hover:opacity-100'
                }`}
              >
                MPT Efficient Frontier
              </button>
              <button
                onClick={() => setPortfolioSubTab('diverse')}
                className={`rounded-md px-3.5 py-1.5 text-xs font-semibold border transition ${
                  portfolioSubTab === 'diverse'
                    ? 'border-emerald-500 bg-emerald-600/20 text-emerald-300'
                    : 'border-slate-600/40 opacity-75 hover:opacity-100'
                }`}
              >
                Diverse-Risk (Up to 10 Stocks)
              </button>
            </div>

            {portfolioSubTab === 'diverse' && <DiverseRiskPanel panelBg={panelBg} />}

            {portfolioSubTab === 'mpt' && (
              <>
            <div className={`rounded-lg border p-4 flex flex-wrap items-center gap-3 ${panelBg}`}>
              <input
                type="text"
                value={portfolioAssets}
                onChange={(e) => setPortfolioAssets(e.target.value)}
                className={`flex-1 min-w-[260px] rounded border px-3 py-1.5 font-mono text-xs ${panelBg}`}
              />
              <button
                onClick={runPortfolioOptimization}
                disabled={portfolioLoading}
                className="rounded bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {portfolioLoading ? 'Optimizing...' : 'Run MPT Efficient Frontier'}
              </button>
            </div>
            {portfolioData && (
              <>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  {[
                    { title: 'Global Minimum Variance', pt: portfolioData.min_variance_portfolio },
                    { title: 'Maximum Sharpe Portfolio', pt: portfolioData.max_sharpe_portfolio },
                    { title: 'Equal Weight Benchmark', pt: portfolioData.equal_weight_portfolio },
                  ].map((item) => (
                    <div key={item.title} className={`rounded-lg border p-4 ${panelBg}`}>
                      <h3 className="text-sm font-semibold">{item.title}</h3>
                      <div className="mt-2 font-mono text-xs space-y-1">
                        <div>Expected Return: <span className="text-emerald-400">{fmtPct(item.pt.expected_return)}</span></div>
                        <div>Annual Volatility: <span>{fmtPct(item.pt.volatility)}</span></div>
                        <div>Sharpe Ratio: <span className="text-blue-400">{fmtNum(item.pt.sharpe_ratio)}</span></div>
                      </div>
                      <div className="mt-3 border-t border-terminal-border pt-2 font-mono text-[11px] space-y-0.5">
                        {Object.entries(item.pt.weights).map(([sym, w]) => (
                          <div key={sym} className="flex justify-between">
                            <span>{sym}</span>
                            <span>{(w * 100).toFixed(1)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                <div className={`rounded-lg border p-4 ${panelBg}`}>
                  <h2 className="mb-3 text-sm font-semibold">Efficient Frontier (Volatility % vs Expected Return %)</h2>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis type="number" dataKey="vol" name="Volatility %" unit="%" tick={{ fontSize: 11 }} />
                        <YAxis type="number" dataKey="ret" name="Return %" unit="%" tick={{ fontSize: 11 }} />
                        <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                        <Scatter
                          name="Efficient Frontier"
                          data={portfolioData.efficient_frontier.map((p) => ({
                            vol: Number((p.volatility * 100).toFixed(2)),
                            ret: Number((p.expected_return * 100).toFixed(2)),
                          }))}
                          fill="#2563EB"
                        />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </>
            )}
              </>
            )}
          </div>
        )}

        {activeTab === 'risk' && (
          <div className="space-y-6">
            {!riskData ? (
              <div className={`rounded-lg border p-8 text-center text-sm opacity-80 ${panelBg}`}>
                Load historical bars for <strong>{selectedId}</strong> to compute VaR, CVaR &amp; Stress Tests.
              </div>
            ) : (
              <>
                <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-terminal-border font-mono opacity-70">
                      <tr>
                        <th className="p-3">VaR Methodology</th>
                        <th className="p-3">Confidence</th>
                        <th className="p-3">1-Day VaR (%)</th>
                        <th className="p-3">1-Day CVaR / ES (%)</th>
                        <th className="p-3">VaR ($100k)</th>
                        <th className="p-3">CVaR ($100k)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-terminal-border font-mono">
                      {riskData.var_results.map((r, i) => (
                        <tr key={i}>
                          <td className="p-3">{r.method}</td>
                          <td className="p-3">{(r.confidence_level * 100).toFixed(0)}%</td>
                          <td className="p-3 text-amber-400">{fmtPct(r.var_pct)}</td>
                          <td className="p-3 text-rose-400">{fmtPct(r.cvar_pct)}</td>
                          <td className="p-3">${r.var_amount.toLocaleString()}</td>
                          <td className="p-3">${r.cvar_amount.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-terminal-border font-mono opacity-70">
                      <tr>
                        <th className="p-3">Stress Test Scenario</th>
                        <th className="p-3">Shock</th>
                        <th className="p-3">Estimated P&amp;L</th>
                        <th className="p-3">Post-Shock Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-terminal-border font-mono">
                      {riskData.stress_scenarios.map((s) => (
                        <tr key={s.scenario_name}>
                          <td className="p-3 font-sans">{s.scenario_name}</td>
                          <td className="p-3 text-rose-400">{fmtPct(s.shock_pct)}</td>
                          <td className="p-3 text-rose-400">${s.estimated_pnl.toLocaleString()}</td>
                          <td className="p-3">${s.post_shock_value.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'ml' && (
          <div className="space-y-6">
            {!forecastData ? (
              <div className={`rounded-lg border p-8 text-center text-sm opacity-80 ${panelBg}`}>
                At least 40 historical bars for <strong>{selectedId}</strong> are required to run chronological ML evaluation.
              </div>
            ) : (
              <>
                <div className={`rounded-lg border p-4 text-xs font-mono flex flex-wrap gap-6 ${panelBg}`}>
                  <div>Train: {forecastData.train_start.slice(0, 10)} → {forecastData.train_end.slice(0, 10)} ({forecastData.train_samples} obs)</div>
                  <div>Test: {forecastData.test_start.slice(0, 10)} → {forecastData.test_end.slice(0, 10)} ({forecastData.test_samples} obs)</div>
                </div>
                <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-terminal-border font-mono opacity-70">
                      <tr>
                        <th className="p-3">Model</th>
                        <th className="p-3">Family</th>
                        <th className="p-3">Test MAE</th>
                        <th className="p-3">Test RMSE</th>
                        <th className="p-3">Walk-Forward RMSE</th>
                        <th className="p-3">R²</th>
                        <th className="p-3">Next-Bar Estimate</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-terminal-border font-mono">
                      {forecastData.models.map((m) => (
                        <tr key={m.model_name}>
                          <td className="p-3 font-semibold">{m.model_name}</td>
                          <td className="p-3 font-sans">{m.model_family}</td>
                          <td className="p-3">{fmtNum(m.mae, 3)}</td>
                          <td className="p-3">{fmtNum(m.rmse, 3)}</td>
                          <td className="p-3">{fmtNum(m.walk_forward_rmse, 3)}</td>
                          <td className="p-3">{fmtNum(m.r_squared, 3)}</td>
                          <td className="p-3 text-blue-400">{m.next_step_predicted_price.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs opacity-70">{forecastData.disclaimer}</p>
              </>
            )}
          </div>
        )}

        {activeTab === 'signals' && (
          <div className="space-y-4">
            {!signalsData ? (
              <div className={`rounded-lg border p-8 text-center text-sm opacity-80 ${panelBg}`}>
                Load at least 15 historical bars for <strong>{selectedId}</strong> to evaluate rules-based signals.
              </div>
            ) : (
              <>
                <div className={`rounded-lg border p-4 flex items-center justify-between ${panelBg}`}>
                  <div>
                    <div className="text-xs opacity-70">Composite Rules-Based Signal ({selectedId})</div>
                    <div className="text-lg font-bold font-mono">{signalsData.composite_signal}</div>
                  </div>
                  <div className="font-mono text-xs">
                    Bullish: {signalsData.bullish_count} · Bearish: {signalsData.bearish_count} · Neutral: {signalsData.neutral_count}
                  </div>
                </div>
                <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-terminal-border font-mono opacity-70">
                      <tr>
                        <th className="p-3">Indicator Rule</th>
                        <th className="p-3">Direction</th>
                        <th className="p-3">Observed</th>
                        <th className="p-3">Condition</th>
                        <th className="p-3">Rationale</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-terminal-border">
                      {signalsData.rules.map((r) => (
                        <tr key={r.rule_name}>
                          <td className="p-3 font-semibold">{r.rule_name}</td>
                          <td className="p-3 font-mono">{r.direction}</td>
                          <td className="p-3 font-mono">{r.observed_value ?? 'N/A'}</td>
                          <td className="p-3 font-mono opacity-80">{r.condition}</td>
                          <td className="p-3 opacity-80">{r.rationale}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'backtesting' && (
          <div className="space-y-6">
            <div className={`rounded-lg border p-4 flex flex-wrap items-center justify-between gap-3 ${panelBg}`}>
              <div className="text-xs">
                Strategy Backtest for <strong className="font-mono">{selectedId}</strong> (T+1 execution, 10 bps commission, 5 bps slippage)
              </div>
              <select
                value={backtestStrategy}
                onChange={(e) => setBacktestStrategy(e.target.value as 'sma_crossover' | 'rsi_mean_reversion' | 'buy_and_hold')}
                className={`rounded border px-3 py-1 font-mono text-xs ${panelBg}`}
              >
                <option value="sma_crossover">SMA 10/20 Crossover</option>
                <option value="rsi_mean_reversion">RSI (14) Mean Reversion</option>
                <option value="buy_and_hold">Buy &amp; Hold Benchmark</option>
              </select>
            </div>
            {backtestData && (
              <>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <div className={`rounded-lg border p-4 ${panelBg}`}>
                    <div className="text-xs opacity-70">Final Value / Total Return</div>
                    <div className="mt-1 font-mono text-base font-bold">
                      ${backtestData.final_portfolio_value.toLocaleString()} ({fmtPct(backtestData.total_return)})
                    </div>
                  </div>
                  <div className={`rounded-lg border p-4 ${panelBg}`}>
                    <div className="text-xs opacity-70">Benchmark (Buy &amp; Hold)</div>
                    <div className="mt-1 font-mono text-base font-bold">
                      ${backtestData.benchmark_final_value.toLocaleString()} ({fmtPct(backtestData.benchmark_total_return)})
                    </div>
                  </div>
                  <div className={`rounded-lg border p-4 ${panelBg}`}>
                    <div className="text-xs opacity-70">Sharpe / Max Drawdown</div>
                    <div className="mt-1 font-mono text-base font-bold">
                      {fmtNum(backtestData.sharpe_ratio)} / {fmtPct(backtestData.max_drawdown)}
                    </div>
                  </div>
                  <div className={`rounded-lg border p-4 ${panelBg}`}>
                    <div className="text-xs opacity-70">Trades / Win Rate / Costs</div>
                    <div className="mt-1 font-mono text-base font-bold">
                      {backtestData.number_of_trades} / {fmtPct(backtestData.win_rate)} / ${backtestData.total_transaction_costs}
                    </div>
                  </div>
                </div>
                <div className={`rounded-lg border p-4 ${panelBg}`}>
                  <h2 className="mb-3 text-sm font-semibold">Strategy Equity Curve vs Buy &amp; Hold Benchmark ($)</h2>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={backtestSeries}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="strategy" stroke="#10B981" dot={false} strokeWidth={2} name="Strategy ($)" />
                        <Line type="monotone" dataKey="benchmark" stroke="#64748B" dot={false} strokeDasharray="4 4" name="Buy & Hold ($)" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'fx' && (
          <div className="space-y-6">
            <div className={`rounded-lg border p-5 space-y-4 ${panelBg}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold">FX Currency Converter</h2>
                  <p className="text-xs opacity-70">Official central-bank daily reference rates across 15 global currencies (Frankfurter v2).</p>
                </div>
                {fxRates && <StatusBadge status={fxRates.data_status} />}
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-4 items-end">
                <div>
                  <label className="block text-[11px] opacity-70 mb-1">Amount</label>
                  <input
                    type="number"
                    min="0"
                    value={fxAmount}
                    onChange={(e) => setFxAmount(e.target.value)}
                    className={`w-full rounded border px-3 py-2 font-mono text-sm ${panelBg}`}
                  />
                </div>
                <div>
                  <label className="block text-[11px] opacity-70 mb-1">From Currency</label>
                  <select value={fxBase} onChange={(e) => setFxBase(e.target.value)} className={`w-full rounded border px-3 py-2 font-mono text-sm ${panelBg}`}>
                    {['USD', 'EUR', 'GBP', 'CHF', 'JPY', 'HKD', 'CNY', 'KRW', 'SGD', 'AUD', 'CAD', 'VND', 'MYR', 'IDR', 'THB'].map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] opacity-70 mb-1">To Currency</label>
                  <select value={fxQuote} onChange={(e) => setFxQuote(e.target.value)} className={`w-full rounded border px-3 py-2 font-mono text-sm ${panelBg}`}>
                    {['VND', 'USD', 'EUR', 'GBP', 'CHF', 'JPY', 'HKD', 'CNY', 'KRW', 'SGD', 'AUD', 'CAD', 'MYR', 'IDR', 'THB'].map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-2">
                  <div className="text-[10px] opacity-75">Converted Value ({fxConverted?.reference_date ?? 'Latest'})</div>
                  <div className="font-mono text-base font-bold text-emerald-300">
                    {fxConverted?.converted_amount != null ? `${fxConverted.converted_amount.toLocaleString()} ${fxQuote}` : 'N/A'}
                  </div>
                </div>
              </div>
            </div>
            <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
              <table className="w-full text-left text-xs">
                <thead className="border-b border-terminal-border font-mono opacity-70">
                  <tr>
                    <th className="p-3">Pair</th>
                    <th className="p-3">Rate</th>
                    <th className="p-3">Reference Date</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-terminal-border font-mono">
                  {fxRates &&
                    Object.entries(fxRates.rates).map(([ccy, rate]) => (
                      <tr key={ccy}>
                        <td className="p-3">{fxRates.base}/{ccy}</td>
                        <td className="p-3 text-emerald-400">{rate.toFixed(4)}</td>
                        <td className="p-3">{fxRates.reference_date ?? 'N/A'}</td>
                        <td className="p-3"><StatusBadge status={fxRates.data_status} /></td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'coverage' && (
          <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
            <table className="w-full text-left text-xs">
              <thead className="border-b border-terminal-border font-mono opacity-70">
                <tr>
                  <th className="p-3">MIC / Exchange</th>
                  <th className="p-3">Country / CCY</th>
                  <th className="p-3">Phase</th>
                  <th className="p-3">Quote Status</th>
                  <th className="p-3">Primary Provider</th>
                  <th className="p-3">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-terminal-border">
                {coverage.map((row) => (
                  <tr key={row.exchange_mic}>
                    <td className="p-3 font-mono font-semibold">{row.exchange_mic} ({row.exchange_acronym})</td>
                    <td className="p-3">{row.country} · {row.currency}</td>
                    <td className="p-3 font-mono">{row.phase}</td>
                    <td className="p-3"><StatusBadge status={row.quote_data_status} /></td>
                    <td className="p-3">{row.primary_provider}</td>
                    <td className="p-3 opacity-80">{row.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'methodology' && (
          <div className={`max-w-3xl space-y-3 rounded-lg border p-6 text-sm ${panelBg}`}>
            <h2 className="text-base font-bold">Quantitative Methodology &amp; Data Provenance</h2>
            <p className="opacity-80">
              All QuantAI analytics, MPT portfolio optimizations, VaR/CVaR risk models, leakage-free ML forecasts, and
              T+1 backtests run server-side in Python (NumPy, Pandas, SciPy). Full formulas and assumptions are documented
              in <code>docs/financial_formulas.md</code> and <code>docs/data_sources.md</code>.
            </p>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
