import React, { useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CandlestickChart } from './components/CandlestickChart';
import { StatusBadge } from './components/StatusBadge';
import { en } from './i18n/en';
import { quantApi, type SingleAssetAnalyticsResponse } from './services/api';
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
  | 'fx'
  | 'coverage'
  | 'methodology'
  | 'portfolio'
  | 'risk'
  | 'ml'
  | 'signals'
  | 'backtesting';

const NAV_ITEMS: Array<{ key: TabKey; label: string; active: boolean; targetPhase?: string }> = [
  { key: 'overview', label: en.nav.overview, active: true },
  { key: 'marketData', label: en.nav.marketData, active: true },
  { key: 'quantAnalysis', label: en.nav.quantAnalysis, active: true },
  { key: 'fx', label: en.nav.fx, active: true },
  { key: 'coverage', label: en.nav.coverage, active: true },
  { key: 'methodology', label: en.nav.methodology, active: true },
  { key: 'portfolio', label: en.nav.portfolio, active: false, targetPhase: 'Phase 3' },
  { key: 'risk', label: en.nav.risk, active: false, targetPhase: 'Phase 4' },
  { key: 'ml', label: en.nav.ml, active: false, targetPhase: 'Phase 5' },
  { key: 'signals', label: en.nav.signals, active: false, targetPhase: 'Phase 6' },
  { key: 'backtesting', label: en.nav.backtesting, active: false, targetPhase: 'Phase 6' },
];

const fmtPct = (v: number | null | undefined) =>
  v == null ? 'N/A' : `${(v * 100).toFixed(2)}%`;

const fmtNum = (v: number | null | undefined, digits = 2) =>
  v == null ? 'N/A' : v.toFixed(digits);

export const App: React.FC = () => {
  const [darkMode, setDarkMode] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [searchQuery, setSearchQuery] = useState('');
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [selectedId, setSelectedId] = useState<string>('XNAS:AAPL');
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [ohlcv, setOhlcv] = useState<OHLCVResponse | null>(null);
  const [analytics, setAnalytics] = useState<SingleAssetAnalyticsResponse | null>(null);
  const [coverage, setCoverage] = useState<ExchangeCoverageEntry[]>([]);
  const [fxBase, setFxBase] = useState<string>('USD');
  const [fxRates, setFxRates] = useState<FXRatesResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    quantApi.searchInstruments({ q: searchQuery }).then(setInstruments).catch(() => setInstruments([]));
  }, [searchQuery]);

  useEffect(() => {
    setErrorMsg(null);
    setAnalytics(null);
    Promise.all([
      quantApi.getQuote(selectedId, false, false),
      quantApi.getOhlcv(selectedId, '1d', true),
    ])
      .then(([q, barsResp]) => {
        setQuote(q);
        setOhlcv(barsResp);
        if (barsResp.bars.length >= 2) {
          quantApi
            .analyzeSingleAsset(selectedId, barsResp.bars, 0.04)
            .then(setAnalytics)
            .catch(() => setAnalytics(null));
        }
      })
      .catch((err) => setErrorMsg(String(err)));
  }, [selectedId]);

  useEffect(() => {
    quantApi.getExchangeCoverage().then(setCoverage).catch(() => setCoverage([]));
  }, []);

  useEffect(() => {
    quantApi.getFxRates(fxBase).then(setFxRates).catch(() => setFxRates(null));
  }, [fxBase]);

  const chartSeries = useMemo(() => {
    if (!analytics) return [];
    return analytics.timestamps.map((ts, idx) => ({
      date: ts.slice(0, 10),
      cumRetPct: analytics.cumulative_returns[idx] != null ? Number((analytics.cumulative_returns[idx]! * 100).toFixed(2)) : null,
      drawdownPct: Number((analytics.drawdown_series[idx] * 100).toFixed(2)),
    }));
  }, [analytics]);

  const currentNav = NAV_ITEMS.find((n) => n.key === activeTab);
  const shellBg = darkMode ? 'bg-terminal-bg text-slate-100' : 'bg-slate-50 text-slate-900';
  const panelBg = darkMode
    ? 'bg-terminal-surface border-terminal-border'
    : 'bg-white border-slate-200';

  return (
    <div className={`min-h-screen flex ${shellBg}`}>
      <aside className={`w-64 shrink-0 border-r p-4 flex flex-col ${panelBg}`}>
        <div className="mb-6 border-b border-terminal-border pb-4 flex items-center justify-between">
          <div>
            <div className="text-lg font-bold tracking-tight">{en.brand.name}</div>
            <div className="mt-1 font-mono text-[11px] text-blue-400">v0.2 · Phase 2 Active</div>
          </div>
          <button
            onClick={() => setDarkMode((d) => !d)}
            className="rounded border border-slate-600/40 px-2 py-1 font-mono text-[10px]"
            title="Toggle Dark / Light Theme"
          >
            {darkMode ? 'Light' : 'Dark'}
          </button>
        </div>

        <nav className="space-y-1 flex-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              onClick={() => setActiveTab(item.key)}
              className={`w-full flex items-center justify-between rounded-md px-3 py-2 text-left text-xs font-medium transition ${
                activeTab === item.key
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-500/40'
                  : 'opacity-80 hover:opacity-100'
              }`}
            >
              <span>{item.label}</span>
              {!item.active && (
                <span className="font-mono text-[10px] opacity-60">{item.targetPhase}</span>
              )}
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
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={en.labels.searchPlaceholder}
            className={`w-80 rounded-md border px-3 py-1.5 text-xs focus:border-blue-500 focus:outline-none ${panelBg}`}
          />
        </header>

        {errorMsg && (
          <div className="mb-4 rounded-md border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-400">
            Backend error: {errorMsg}
          </div>
        )}

        {(activeTab === 'overview' || activeTab === 'marketData') && (
          <div className="space-y-6">
            <div className="flex flex-wrap gap-2">
              {instruments.slice(0, 12).map((inst) => (
                <button
                  key={inst.instrument_id}
                  onClick={() => setSelectedId(inst.instrument_id)}
                  className={`rounded border px-2.5 py-1 font-mono text-xs ${
                    selectedId === inst.instrument_id
                      ? 'border-blue-500 bg-blue-600/20 text-blue-300'
                      : panelBg
                  }`}
                >
                  {inst.instrument_id} · {inst.currency}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-xs opacity-70">Selected Instrument</div>
                <div className="mt-1 font-mono text-lg font-bold">{selectedId}</div>
                <div className="mt-2">
                  {quote && <StatusBadge status={quote.data_status} delayMinutes={quote.delay_minutes} />}
                </div>
              </div>
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-xs opacity-70">Latest Verified Price</div>
                <div className="mt-1 font-mono text-lg font-bold">
                  {quote?.price != null ? `${quote.price.toLocaleString()} ${quote.currency}` : 'DATA UNAVAILABLE'}
                </div>
                <div className="mt-1 text-xs opacity-70">Session: {quote?.market_session ?? 'N/A'}</div>
              </div>
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-xs opacity-70">Annualized Vol / Sharpe</div>
                <div className="mt-1 font-mono text-lg font-bold">
                  {fmtPct(analytics?.summary.annualized_volatility)} / {fmtNum(analytics?.summary.sharpe_ratio)}
                </div>
                <div className="mt-1 text-xs opacity-70">Max Drawdown: {fmtPct(analytics?.summary.max_drawdown)}</div>
              </div>
              <div className={`rounded-lg border p-4 ${panelBg}`}>
                <div className="text-xs opacity-70">{en.labels.retrievalTimestamp}</div>
                <div className="mt-1 font-mono text-xs">{quote?.retrieval_timestamp ?? 'N/A'}</div>
                <div className="mt-2 text-xs opacity-70">RSI (14): {fmtNum(analytics?.summary.latest_rsi_14)}</div>
              </div>
            </div>

            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Historical OHLCV Price Series</h2>
                {ohlcv && <StatusBadge status={ohlcv.data_status} />}
              </div>
              <CandlestickChart bars={ohlcv?.bars ?? []} />
            </div>
          </div>
        )}

        {activeTab === 'quantAnalysis' && (
          <div className="space-y-6">
            {!analytics ? (
              <div className={`rounded-lg border p-8 text-center text-sm opacity-80 ${panelBg}`}>
                No verified historical OHLCV bars loaded for <strong>{selectedId}</strong> yet. Run the backend with
                live or historical providers configured to compute quantitative analytics.
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

                <div className={`rounded-lg border p-4 text-xs space-y-1 ${panelBg}`}>
                  <h3 className="font-semibold text-sm mb-2">Model Assumptions &amp; Methodology</h3>
                  {analytics.assumptions.map((a, i) => (
                    <p key={i} className="opacity-80">• {a}</p>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'fx' && (
          <div className="space-y-4">
            <div className={`flex items-center justify-between rounded-lg border p-4 ${panelBg}`}>
              <div>
                <h2 className="text-sm font-semibold">Global FX Reference Rates (15 Target Currencies)</h2>
                <p className="text-xs opacity-70">Frankfurter v2 official central-bank DAILY_REFERENCE midpoints.</p>
              </div>
              <div className="flex items-center gap-3">
                <select
                  value={fxBase}
                  onChange={(e) => setFxBase(e.target.value)}
                  className={`rounded border px-2.5 py-1 font-mono text-xs ${panelBg}`}
                >
                  {['USD', 'EUR', 'GBP', 'JPY', 'VND', 'SGD', 'AUD', 'CHF'].map((c) => (
                    <option key={c} value={c}>Base: {c}</option>
                  ))}
                </select>
                {fxRates && <StatusBadge status={fxRates.data_status} />}
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
              All Phase 2 analytics run server-side in Python using NumPy, Pandas, and SciPy. Full formulas and
              assumptions (252-day annualization, ddof=1 sample volatility, Wilder RSI/ATR smoothing, and inner-joined
              multi-asset covariance) are documented in <code>docs/financial_formulas.md</code>.
            </p>
          </div>
        )}

        {!currentNav?.active && (
          <div className={`rounded-lg border p-8 text-center ${panelBg}`}>
            <h2 className="text-base font-semibold">
              {currentNav?.label} — Scheduled for {currentNav?.targetPhase}
            </h2>
            <p className="mt-2 text-xs opacity-70">{en.labels.plannedNotice}</p>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
