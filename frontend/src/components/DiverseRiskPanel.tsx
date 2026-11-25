import React, { useEffect, useMemo, useState } from 'react';
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import {
  quantApi,
  type DiverseRiskAdvisorResponse,
  type DiverseRiskResponse,
  type PortfolioSimulationResponse,
} from '../services/api';
import type { Instrument } from '../types/market';
import { TickerSearchBox } from './TickerSearchBox';

interface Props {
  darkMode: boolean;
  availableInstruments: Instrument[];
  onAnalyze?: (res: DiverseRiskResponse) => void;
}

const ALL_MARKETS = [
  'United States',
  'Vietnam',
  'United Kingdom',
  'Germany',
  'Japan',
  'Hong Kong',
  'Singapore',
  'Australia',
] as const;

const ALL_GICS_SECTORS = [
  'Technology',
  'Financial Services',
  'Healthcare',
  'Consumer Defensive',
  'Consumer Cyclical',
  'Energy',
  'Industrials',
  'Basic Materials',
  'Utilities',
  'Real Estate',
  'Communication Services',
] as const;

const CURRENCIES = ['USD', 'VND', 'EUR', 'GBP', 'JPY', 'SGD', 'AUD', 'HKD'] as const;

const PIE_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899',
  '#06b6d4', '#f97316', '#84cc16', '#6366f1', '#14b8a6',
];

interface CorrelationPairing {
  id: string;
  name: string;
  thesis: string;
  sectors: string[];
  tag: string;
}

const INDUSTRY_PAIRINGS: CorrelationPairing[] = [
  {
    id: 'all_weather',
    name: 'All-Weather Defensive Core',
    tag: 'Low Beta · Drawdown Shield',
    thesis:
      'Pairs non-cyclical cash-flow anchors (Healthcare, Consumer Defensive, Utilities) with selective Technology growth to mute recession drawdowns.',
    sectors: ['Healthcare', 'Consumer Defensive', 'Utilities', 'Technology'],
  },
  {
    id: 'inflation_barbell',
    name: 'Inflation & Rate-Resilient Barbell',
    tag: 'Macro Hedge',
    thesis:
      'Combines rate-sensitive Financials and inflation-hedging Energy & Basic Materials against duration-sensitive Technology.',
    sectors: ['Energy', 'Financial Services', 'Basic Materials', 'Technology'],
  },
  {
    id: 'growth_stability',
    name: 'Global Growth & Real-Economy Blend',
    tag: 'Balanced Alpha',
    thesis:
      'Balances secular Technology & Communication Services compounding with Industrial infrastructure and Healthcare stability.',
    sectors: ['Technology', 'Communication Services', 'Industrials', 'Healthcare'],
  },
  {
    id: 'income_hard_assets',
    name: 'Real Assets, Income & Consumer Shield',
    tag: 'Yield & Tangible Value',
    thesis:
      'Diversifies across Real Estate, Utilities, Consumer Defensive, and Financial Services to dampen equity-index correlation.',
    sectors: ['Real Estate', 'Utilities', 'Consumer Defensive', 'Financial Services'],
  },
];

const cleanSym = (id: string) => (id.includes(':') ? id.split(':')[1] : id);

export const DiverseRiskPanel: React.FC<Props> = ({ darkMode, availableInstruments }) => {
  const [selectedMarkets, setSelectedMarkets] = useState<string[]>(['United States', 'Vietnam']);
  const [selectedSectors, setSelectedSectors] = useState<string[]>([
    'Healthcare',
    'Consumer Defensive',
    'Utilities',
    'Technology',
  ]);
  const [capital, setCapital] = useState<number>(100000);
  const [currency, setCurrency] = useState<string>('USD');
  const [allocationMethod, setAllocationMethod] = useState<'min_variance' | 'max_sharpe' | 'equal_weight'>('min_variance');
  const [rebalance, setRebalance] = useState<'quarterly' | 'annually' | 'buy_and_hold'>('quarterly');

  const [selectedStocks, setSelectedStocks] = useState<string[]>([
    'XNYS:JNJ',
    'XNYS:WMT',
    'XNYS:NEE',
    'XNAS:MSFT',
    'XSTC:FPT',
  ]);

  const [simResult, setSimResult] = useState<PortfolioSimulationResponse | null>(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  // Hedge Fund PM AI Desk state
  const [pmQuestion, setPmQuestion] = useState('');
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string; engine?: string }>>([]);
  const [pmLoading, setPmLoading] = useState(false);
  const [pmError, setPmError] = useState<string | null>(null);
  const [geminiOnline, setGeminiOnline] = useState<boolean | null>(null);

  const cardBg = darkMode
    ? 'bg-slate-900/75 border-slate-800'
    : 'bg-white border-slate-200 shadow-sm';
  const subBg = darkMode
    ? 'bg-slate-950/75 border-slate-800'
    : 'bg-slate-50 border-slate-200';

  const toggleMarket = (mkt: string) => {
    setSelectedMarkets((prev) =>
      prev.includes(mkt) ? (prev.length > 1 ? prev.filter((m) => m !== mkt) : prev) : [...prev, mkt]
    );
  };

  const toggleSector = (sec: string) => {
    setSelectedSectors((prev) =>
      prev.includes(sec) ? (prev.length > 1 ? prev.filter((s) => s !== sec) : prev) : [...prev, sec]
    );
  };

  // Candidate universe filtered by chosen markets & sectors
  const filteredPool = useMemo(() => {
    return availableInstruments.filter(
      (i) =>
        selectedMarkets.includes(i.country) &&
        i.sector &&
        selectedSectors.includes(i.sector)
    );
  }, [availableInstruments, selectedMarkets, selectedSectors]);

  // Auto-build diversified basket from chosen markets & sectors
  const autoBuildOptimalBasket = () => {
    const picked: string[] = [];
    // Pick up to 2 stocks per chosen sector, spread across chosen markets, max 8 stocks
    for (const sec of selectedSectors) {
      const matches = filteredPool.filter((i) => i.sector === sec);
      for (const m of matches.slice(0, 2)) {
        if (!picked.includes(m.instrument_id) && picked.length < 8) {
          picked.push(m.instrument_id);
        }
      }
    }
    if (picked.length >= 2) {
      setSelectedStocks(picked);
      runSimulation(picked);
    } else {
      setSimError('Select at least 2 matching stocks or add custom tickers to run the 10-year optimization.');
    }
  };

  const runSimulation = async (idsOverride?: string[]) => {
    const basket = idsOverride || selectedStocks;
    if (basket.length < 2) {
      setSimError('Select at least 2 stocks to optimize portfolio risk and run 10-year historical proof.');
      return;
    }
    const cappedCapital = Math.max(100, Math.min(1_000_000_000, Number(capital) || 100000));
    if (cappedCapital !== capital) setCapital(cappedCapital);

    setSimLoading(true);
    setSimError(null);
    try {
      const res = await quantApi.simulatePortfolio10Y({
        instrument_ids: basket,
        capital: cappedCapital,
        currency,
        allocation_method: allocationMethod,
        rebalance_frequency: rebalance,
        years: 10,
      });
      setSimResult(res);
    } catch (err: unknown) {
      setSimError(err instanceof Error && err.message ? err.message : 'Unable to run 10-year portfolio simulation. Check backend connection.');
    } finally {
      setSimLoading(false);
    }
  };

  // Run initial simulation on mount so the user sees an institutional dashboard immediately
  useEffect(() => {
    quantApi.getAssistantStatus().then((s) => setGeminiOnline(s.gemini_configured)).catch(() => setGeminiOnline(false));
    if (!simResult && selectedStocks.length >= 2) {
      runSimulation(selectedStocks);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const askHedgeFundPM = async (customQ?: string) => {
    const q = (customQ ?? pmQuestion).trim();
    if (!q || pmLoading) return;
    const historyPayload = chatMessages.map((m) => ({ role: m.role, content: m.content }));
    setChatMessages((prev) => [...prev, { role: 'user', content: q }]);
    setPmQuestion('');
    setPmLoading(true);
    setPmError(null);
    try {
      const res = await quantApi.askPortfolioAssistant({
        question: q,
        market_scope: selectedMarkets.join(' + '),
        selected_sectors: selectedSectors,
        selected_stocks: selectedStocks,
        portfolio_summary: simResult?.pm_verdict,
        conversation_history: historyPayload,
      });
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.answer, engine: res.engine_used },
      ]);
      if (res.used_llm) setGeminiOnline(true);
    } catch (err: unknown) {
      setPmError(err instanceof Error && err.message ? err.message : 'Unable to reach assistant. Verify backend is running on port 8000.');
    } finally {
      setPmLoading(false);
    }
  };

  const fmtAmt = (val: number) =>
    `${Math.round(val).toLocaleString()} ${currency}`;

  // SVG 10-year equity curve
  const render10YCurve = (res: PortfolioSimulationResponse) => {
    const w = 740;
    const h = 220;
    const pad = 28;
    const allV = [...res.equity_curve, ...res.benchmark_curve];
    const minV = Math.min(...allV);
    const maxV = Math.max(...allV);
    const span = Math.max(maxV - minV, 1);
    const pts = (arr: number[]) =>
      arr
        .map((v, i) => {
          const x = pad + (i / Math.max(1, arr.length - 1)) * (w - pad * 2);
          const y = h - pad - ((v - minV) / span) * (h - pad * 2);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(' ');
    return (
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-56">
        <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#334155" strokeWidth="1" />
        <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="#334155" strokeWidth="1" />
        <polyline fill="none" stroke="#94a3b8" strokeWidth="1.6" strokeDasharray="4 4" points={pts(res.benchmark_curve)} />
        <polyline fill="none" stroke="#10b981" strokeWidth="2.5" points={pts(res.equity_curve)} />
        <text x={pad + 4} y={pad + 10} fill="#94a3b8" fontSize="10">
          {Math.round(maxV).toLocaleString()} {res.currency}
        </text>
        <text x={pad + 4} y={h - pad - 4} fill="#94a3b8" fontSize="10">
          {Math.round(minV).toLocaleString()} {res.currency}
        </text>
        <text x={pad} y={h - 6} fill="#94a3b8" fontSize="10">{res.start_date}</text>
        <text x={w - pad - 62} y={h - 6} fill="#94a3b8" fontSize="10">{res.end_date}</text>
      </svg>
    );
  };

  return (
    <div className="space-y-6">
      {/* TARGET MARKET UNIVERSE & CAPITAL ALLOCATION BAR */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-base font-bold">Portfolio Mandate & Target Markets</h2>
            <p className="text-xs opacity-70 mt-0.5">
              Select one or multiple equity markets to combine and set your hypothetical test capital (up to 1,000,000,000 in any currency).
            </p>
          </div>
        </div>

        {/* Multi-Market Selection Bar */}
        <div className="flex flex-wrap gap-2 mb-4">
          {ALL_MARKETS.map((mkt) => {
            const active = selectedMarkets.includes(mkt);
            return (
              <button
                key={mkt}
                type="button"
                onClick={() => toggleMarket(mkt)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                  active
                    ? 'bg-blue-600/20 text-blue-300 border-blue-500/60'
                    : darkMode
                    ? 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-600'
                    : 'bg-slate-100 border-slate-300 text-slate-600'
                }`}
              >
                {active ? '✓ ' : '+ '}
                {mkt}
              </button>
            );
          })}
        </div>

        {/* Capital, Currency, Optimization Objective, Rebalance */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-slate-800/70">
          <div>
            <label className="text-[11px] opacity-65 block mb-1">Test Capital (Max 1,000,000,000)</label>
            <input
              type="number"
              min={100}
              max={1000000000}
              step={10000}
              value={capital}
              onChange={(e) => setCapital(Math.min(1_000_000_000, Math.max(0, Number(e.target.value))))}
              className={`w-full rounded-lg border px-2.5 py-1.5 text-xs font-mono ${subBg}`}
            />
          </div>
          <div>
            <label className="text-[11px] opacity-65 block mb-1">Currency</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className={`w-full rounded-lg border px-2.5 py-1.5 text-xs font-mono ${subBg}`}
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] opacity-65 block mb-1">Optimization Objective</label>
            <select
              value={allocationMethod}
              onChange={(e) => setAllocationMethod(e.target.value as typeof allocationMethod)}
              className={`w-full rounded-lg border px-2.5 py-1.5 text-xs ${subBg}`}
            >
              <option value="min_variance">Minimum Variance (Lowest Risk)</option>
              <option value="max_sharpe">Maximum Sharpe (Risk-Adjusted)</option>
              <option value="equal_weight">Equal Weight (1/N)</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] opacity-65 block mb-1">Rebalancing Schedule</label>
            <select
              value={rebalance}
              onChange={(e) => setRebalance(e.target.value as typeof rebalance)}
              className={`w-full rounded-lg border px-2.5 py-1.5 text-xs ${subBg}`}
            >
              <option value="quarterly">Quarterly Rebalance</option>
              <option value="annually">Annual Rebalance</option>
              <option value="buy_and_hold">Buy & Hold</option>
            </select>
          </div>
        </div>
      </div>

      {/* INDUSTRY CORRELATION PAIRINGS & FULL 11-SECTOR CUSTOM BUILDER */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="mb-3">
          <h2 className="text-base font-bold">Industry Correlation Blueprints & Custom Sector Mix</h2>
          <p className="text-xs opacity-70 mt-0.5">
            Apply a low-correlation institutional sector pairing below or customize across all 11 GICS industries.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          {INDUSTRY_PAIRINGS.map((p) => (
            <div key={p.id} className={`rounded-lg border p-3.5 flex flex-col justify-between ${subBg}`}>
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-blue-400">{p.name}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">{p.tag}</span>
                </div>
                <p className="text-[11px] opacity-75 mt-1.5 leading-relaxed">{p.thesis}</p>
              </div>
              <div className="mt-3 flex items-center justify-between gap-2">
                <div className="flex flex-wrap gap-1">
                  {p.sectors.map((s) => (
                    <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20">
                      {s}
                    </span>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedSectors(p.sectors)}
                  className="shrink-0 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-blue-600 hover:bg-blue-500 text-white"
                >
                  Apply
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* All 11 GICS Sectors Custom Toggle Pills */}
        <div className="pt-3 border-t border-slate-800/70">
          <div className="text-[11px] font-semibold opacity-70 mb-2">Custom Industry Selection (All 11 GICS Sectors)</div>
          <div className="flex flex-wrap gap-1.5">
            {ALL_GICS_SECTORS.map((sec) => {
              const active = selectedSectors.includes(sec);
              return (
                <button
                  key={sec}
                  type="button"
                  onClick={() => toggleSector(sec)}
                  className={`px-2.5 py-1 rounded-md text-[11px] border transition ${
                    active
                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/50 font-semibold'
                      : darkMode
                      ? 'bg-slate-950/50 border-slate-800 text-slate-400 hover:border-slate-600'
                      : 'bg-slate-100 border-slate-300 text-slate-600'
                  }`}
                >
                  {sec}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* PORTFOLIO BASKET & CUSTOM STOCK BUILDER */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-base font-bold">Portfolio Constituents ({selectedStocks.length} / 10 Stocks)</h2>
            <p className="text-xs opacity-70 mt-0.5">
              Auto-generate from your chosen markets & industries, or add/remove any global stock to test your own custom portfolio.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={autoBuildOptimalBasket}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white"
            >
              Auto-Select from Sectors
            </button>
            <button
              type="button"
              onClick={() => runSimulation()}
              disabled={simLoading}
              className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
            >
              {simLoading ? 'Optimizing & Running 10Y Proof...' : 'Optimize Weights & Run 10Y Proof'}
            </button>
          </div>
        </div>

        {/* Active basket chips + Live Autocomplete Add Stock */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {selectedStocks.map((id) => (
            <span
              key={id}
              title={id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono font-semibold bg-blue-600/20 text-blue-300 border border-blue-500/40"
            >
              {cleanSym(id)}
              <button
                type="button"
                onClick={() => setSelectedStocks((prev) => prev.filter((x) => x !== id))}
                className="opacity-70 hover:opacity-100"
              >
                ×
              </button>
            </span>
          ))}
          <TickerSearchBox
            darkMode={darkMode}
            className="w-64"
            placeholder="+ Search & add any stock..."
            onSelect={(inst) => {
              if (selectedStocks.length < 10 && !selectedStocks.includes(inst.instrument_id)) {
                setSelectedStocks((prev) => [...prev, inst.instrument_id]);
              }
            }}
          />
        </div>

        {/* Quick add from matching sectors */}
        {filteredPool.length > 0 && (
          <div className="pt-2.5 border-t border-slate-800/60">
            <div className="text-[11px] opacity-60 mb-1.5">Quick-Add Candidates in Selected Markets & Sectors:</div>
            <div className="flex flex-wrap gap-1.5">
              {filteredPool.slice(0, 14).map((inst) => {
                const picked = selectedStocks.includes(inst.instrument_id);
                return (
                  <button
                    key={inst.instrument_id}
                    type="button"
                    disabled={picked || selectedStocks.length >= 10}
                    onClick={() => setSelectedStocks((prev) => [...prev, inst.instrument_id])}
                    className={`px-2 py-0.5 rounded text-[11px] font-mono border transition ${
                      picked
                        ? 'opacity-40 border-slate-800 cursor-not-allowed'
                        : 'border-slate-700 hover:border-blue-500 text-slate-300'
                    }`}
                    title={`${inst.company_name} (${inst.sector})`}
                  >
                    + {inst.ticker}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {simError && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-300">
          {simError}
        </div>
      )}

      {/* OPTIMAL ALLOCATION PIE CHART + 10Y HISTORICAL PROOF + FORWARD SCENARIO FORECAST */}
      {simResult && (
        <>
          {/* Portfolio Desk Verdict & Core KPIs */}
          <div className={`rounded-xl border p-5 ${cardBg}`}>
            <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
              Hedge Fund Portfolio Risk Assessment
            </div>
            <p className="text-sm mt-1.5 leading-relaxed opacity-90">{simResult.pm_verdict}</p>
            {simResult.excluded_tickers && simResult.excluded_tickers.length > 0 && (
              <div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                Excluded due to missing historical data:{' '}
                {simResult.excluded_tickers.map((e) => `${e.ticker} (${e.reason})`).join(', ')}
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
              <div className={`rounded-lg border p-3.5 ${subBg}`}>
                <div className="text-[11px] opacity-65">10Y Ending Wealth</div>
                <div className="text-base font-bold font-mono text-emerald-400 mt-1">
                  {fmtAmt(simResult.final_portfolio_value)}
                </div>
                <div className="text-[10px] opacity-65">
                  Start: {fmtAmt(simResult.initial_capital)}
                </div>
              </div>
              <div className={`rounded-lg border p-3.5 ${subBg}`}>
                <div className="text-[11px] opacity-65">Annualized CAGR</div>
                <div className="text-base font-bold font-mono text-blue-400 mt-1">
                  {(simResult.cagr * 100).toFixed(2)}%
                </div>
                <div className="text-[10px] opacity-65">
                  Equal-Wt: {(simResult.benchmark_cagr * 100).toFixed(2)}%
                </div>
              </div>
              <div className={`rounded-lg border p-3.5 ${subBg}`}>
                <div className="text-[11px] opacity-65">Volatility Reduction</div>
                <div className="text-base font-bold font-mono text-emerald-300 mt-1">
                  -{(simResult.risk_reduction_pct * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] opacity-65">
                  Div. Ratio: {simResult.diversification_ratio.toFixed(2)}x
                </div>
              </div>
              <div className={`rounded-lg border p-3.5 ${subBg}`}>
                <div className="text-[11px] opacity-65">Portfolio Vol / Sharpe</div>
                <div className="text-base font-bold font-mono mt-1">
                  {(simResult.portfolio_volatility * 100).toFixed(1)}% / {simResult.sharpe_ratio?.toFixed(2) ?? 'N/A'}
                </div>
                <div className="text-[10px] opacity-65">
                  Avg Stock Vol: {(simResult.weighted_avg_stock_volatility * 100).toFixed(1)}%
                </div>
              </div>
              <div className={`rounded-lg border p-3.5 ${subBg}`}>
                <div className="text-[11px] opacity-65">10Y Max Drawdown</div>
                <div className="text-base font-bold font-mono text-rose-400 mt-1">
                  {(simResult.max_drawdown * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] opacity-65">
                  Span: {simResult.years_covered}Y
                </div>
              </div>
            </div>
          </div>

          {/* PIE CHART + EXACT WEIGHT & CAPITAL ALLOCATION TABLE */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className={`rounded-xl border p-5 ${cardBg}`}>
              <h3 className="text-sm font-bold mb-1">Recommended Portfolio Allocation</h3>
              <p className="text-xs opacity-65 mb-3">
                Optimal risk-budget weights calibrated for {fmtAmt(simResult.initial_capital)}.
              </p>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={simResult.allocations.map((a) => ({
                        name: a.ticker,
                        value: Number((a.weight * 100).toFixed(1)),
                      }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={58}
                      outerRadius={95}
                      paddingAngle={2}
                    >
                      {simResult.allocations.map((_, idx) => (
                        <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number | string) => `${v}%`} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className={`rounded-xl border p-5 ${cardBg}`}>
              <h3 className="text-sm font-bold mb-1">Exact Stock Weights & Capital Deployment</h3>
              <p className="text-xs opacity-65 mb-3">
                Position sizing across each constituent based on covariance & volatility contribution.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="opacity-60 border-b border-slate-800">
                    <tr>
                      <th className="py-2 pr-2">Ticker</th>
                      <th className="py-2 px-2">Sector</th>
                      <th className="py-2 px-2">Weight</th>
                      <th className="py-2 px-2">Allocation</th>
                      <th className="py-2 pl-2">Stock Vol</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {simResult.allocations.map((a, idx) => (
                      <tr key={a.instrument_id}>
                        <td className="py-2 pr-2 font-mono font-bold flex items-center gap-2">
                          <span
                            className="inline-block w-2.5 h-2.5 rounded-full"
                            style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }}
                          />
                          {a.ticker}
                        </td>
                        <td className="py-2 px-2 opacity-80">{a.sector}</td>
                        <td className="py-2 px-2 font-mono text-blue-400 font-semibold">
                          {(a.weight * 100).toFixed(1)}%
                        </td>
                        <td className="py-2 px-2 font-mono">{fmtAmt(a.allocated_capital)}</td>
                        <td className="py-2 pl-2 font-mono opacity-75">
                          {(a.annualized_volatility * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* 10-YEAR HISTORICAL EVIDENCE CURVE */}
          <div className={`rounded-xl border p-5 ${cardBg}`}>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div>
                <h3 className="text-sm font-bold">
                  10-Year Historical Performance Evidence ({simResult.start_date} → {simResult.end_date})
                </h3>
                <p className="text-xs opacity-65">
                  How {fmtAmt(simResult.initial_capital)} invested in this exact portfolio would have behaved over the past decade.
                </p>
              </div>
              <div className="flex items-center gap-4 text-[11px]">
                <span className="text-emerald-400">━━ Optimized Portfolio</span>
                <span className="text-slate-400">┄┄ Equal-Weight Buy & Hold</span>
              </div>
            </div>
            {render10YCurve(simResult)}

            {simResult.calendar_year_returns.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mt-4 pt-3 border-t border-slate-800/70">
                {simResult.calendar_year_returns.map((yr) => (
                  <div key={yr.year} className={`rounded-lg border p-2 text-xs ${subBg}`}>
                    <div className="opacity-65 font-semibold">{yr.year}</div>
                    <div
                      className={`font-mono font-bold mt-0.5 ${
                        yr.portfolio_return >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {yr.portfolio_return >= 0 ? '+' : ''}
                      {(yr.portfolio_return * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* FORWARD SCENARIO FORECAST (1Y / 3Y / 5Y BEAR / BASE / BULL) */}
          <div className={`rounded-xl border p-5 ${cardBg}`}>
            <h3 className="text-sm font-bold">Forward Scenario Forecast (Monte Carlo — 5,000 Paths)</h3>
            <p className="text-xs opacity-65 mt-0.5 mb-4">
              Projected value of {fmtAmt(simResult.initial_capital)} under Stress/Bear (10th pct), Median/Base (50th pct), and Bull (90th pct) regimes.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {simResult.forward_scenarios.map((sc) => (
                <div key={sc.horizon_years} className={`rounded-xl border p-4 ${subBg}`}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold text-blue-400">{sc.horizon_years}-Year Horizon</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300">
                      P(Profit): {(sc.prob_positive * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-emerald-400 font-medium">Bull Case (90th pct)</span>
                      <span className="font-mono font-bold text-emerald-400">
                        {fmtAmt(sc.bull_value)} ({sc.bull_cagr >= 0 ? '+' : ''}{(sc.bull_cagr * 100).toFixed(1)}%/yr)
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-blue-300 font-medium">Base Case (Median)</span>
                      <span className="font-mono font-bold text-blue-300">
                        {fmtAmt(sc.base_value)} ({sc.base_cagr >= 0 ? '+' : ''}{(sc.base_cagr * 100).toFixed(1)}%/yr)
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-rose-400 font-medium">Bear Case (10th pct)</span>
                      <span className="font-mono font-bold text-rose-400">
                        {fmtAmt(sc.bear_value)} ({sc.bear_cagr >= 0 ? '+' : ''}{(sc.bear_cagr * 100).toFixed(1)}%/yr)
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* MULTI-TURN CONVERSATIONAL ASSISTANT */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div>
            <h3 className="text-sm font-bold">I&apos;m your assistant, ask me something</h3>

          </div>
          <div className="flex items-center gap-2">
            {geminiOnline !== null && (
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full border font-mono ${
                  geminiOnline
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40'
                    : 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                }`}
              >
                {geminiOnline ? '● Gemini Live' : '● Local Fallback'}
              </span>
            )}
            {chatMessages.length > 0 && (
              <button
                type="button"
                onClick={() => setChatMessages([])}
                className="text-[11px] px-2 py-0.5 rounded border border-slate-700 opacity-70 hover:opacity-100"
              >
                Clear Chat
              </button>
            )}
          </div>
        </div>

        {chatMessages.length === 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {[
              'Which stock should I trim or replace in my current portfolio?',
              'How can I cut crash drawdown across these markets?',
              'Which defensive sector am I missing right now?',
            ].map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => askHedgeFundPM(preset)}
                className={`text-[11px] px-2.5 py-1 rounded-full border transition ${
                  darkMode
                    ? 'border-slate-700 hover:border-blue-500 text-slate-300'
                    : 'border-slate-300 hover:border-blue-500 text-slate-700'
                }`}
              >
                {preset}
              </button>
            ))}
          </div>
        )}

        {chatMessages.length > 0 && (
          <div className={`mb-4 rounded-xl border p-4 max-h-96 overflow-y-auto space-y-3 ${subBg}`}>
            {chatMessages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
              >
                <div
                  className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-line ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-br-sm'
                      : darkMode
                      ? 'bg-slate-800/90 text-slate-100 border border-slate-700/70 rounded-bl-sm'
                      : 'bg-white text-slate-900 border border-slate-200 rounded-bl-sm'
                  }`}
                >
                  {msg.content}
                </div>
                {msg.role === 'assistant' && msg.engine && (
                  <span className="text-[10px] opacity-45 mt-1 px-1 font-mono">{msg.engine}</span>
                )}
              </div>
            ))}
            {pmLoading && (
              <div className="flex items-start">
                <div className="rounded-2xl rounded-bl-sm px-3.5 py-2 text-xs bg-slate-800/70 text-slate-400 animate-pulse">
                  Typing...
                </div>
              </div>
            )}
          </div>
        )}

        {pmError && (
          <div className="mb-3 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-300">
            {pmError}
          </div>
        )}

        <div className="flex gap-2">
          <input
            value={pmQuestion}
            onChange={(e) => setPmQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && askHedgeFundPM()}
            placeholder="Message your assistant..."
            className={`flex-1 rounded-xl border px-3.5 py-2.5 text-xs ${subBg}`}
          />
          <button
            type="button"
            onClick={() => askHedgeFundPM()}
            disabled={pmLoading || !pmQuestion.trim()}
            className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
          >
            {pmLoading ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
};
