import React, { useState } from 'react';
import { api, type PortfolioBacktestResponse } from '../services/api';

interface Props {
  selectedPortfolioIds: string[];
  onUpdatePortfolioIds?: (ids: string[]) => void;
  availableInstruments: { instrument_id: string; ticker: string; company_name: string }[];
  darkMode: boolean;
}

const cleanSym = (id: string) => (id.includes(':') ? id.split(':')[1] : id);

export const PortfolioBacktestPanel: React.FC<Props> = ({
  selectedPortfolioIds,
  availableInstruments,
  darkMode,
}) => {
  const [tickers, setTickers] = useState<string[]>(
    selectedPortfolioIds.length >= 2
      ? selectedPortfolioIds
      : ['XNAS:AAPL', 'XNAS:MSFT', 'XNYS:JPM', 'XSTC:FPT']
  );
  const [addInput, setAddInput] = useState('');
  const [years, setYears] = useState<number>(10);
  const [allocation, setAllocation] = useState<'equal_weight' | 'min_variance' | 'max_sharpe'>('equal_weight');
  const [rebalance, setRebalance] = useState<'quarterly' | 'annually' | 'buy_and_hold'>('quarterly');
  const [initialCapital, setInitialCapital] = useState<number>(100000);
  const [result, setResult] = useState<PortfolioBacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cardBg = darkMode
    ? 'bg-slate-900/75 border-slate-800'
    : 'bg-white border-slate-200 shadow-sm';

  const handleAddTicker = () => {
    const raw = addInput.trim().toUpperCase();
    if (!raw || tickers.length >= 10) return;
    let resolved = raw;
    if (!raw.includes(':')) {
      const match = availableInstruments.find((i) => i.ticker.toUpperCase() === raw);
      resolved = match ? match.instrument_id : `XNAS:${raw}`;
    }
    if (!tickers.includes(resolved)) {
      setTickers([...tickers, resolved]);
    }
    setAddInput('');
  };

  const handleRun = async () => {
    if (tickers.length < 2) {
      setError('Select at least 2 portfolio stocks to run a 10-year portfolio backtest.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.runPortfolioBacktest({
        instrument_ids: tickers,
        years,
        allocation_method: allocation,
        rebalance_frequency: rebalance,
        initial_capital: initialCapital,
      });
      setResult(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to run 10-year portfolio backtest.');
    } finally {
      setLoading(false);
    }
  };

  // Sync button to pull latest stocks from Portfolio Manager
  const syncFromPortfolio = () => {
    if (selectedPortfolioIds.length >= 2) {
      setTickers([...selectedPortfolioIds]);
    }
  };

  // Build SVG polyline points for equity curve vs benchmark
  const renderEquitySvg = (res: PortfolioBacktestResponse) => {
    const w = 720;
    const h = 230;
    const pad = 24;
    const allVals = [...res.equity_curve, ...res.benchmark_curve];
    const minV = Math.min(...allVals);
    const maxV = Math.max(...allVals);
    const span = Math.max(maxV - minV, 1);
    const toPts = (arr: number[]) =>
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
        <polyline fill="none" stroke="#94a3b8" strokeWidth="1.75" strokeDasharray="4 4" points={toPts(res.benchmark_curve)} />
        <polyline fill="none" stroke="#3b82f6" strokeWidth="2.5" points={toPts(res.equity_curve)} />
        <text x={pad + 4} y={pad + 10} fill="#94a3b8" fontSize="10">
          ${Math.round(maxV).toLocaleString()}
        </text>
        <text x={pad + 4} y={h - pad - 4} fill="#94a3b8" fontSize="10">
          ${Math.round(minV).toLocaleString()}
        </text>
        <text x={pad} y={h - 6} fill="#94a3b8" fontSize="10">
          {res.start_date}
        </text>
        <text x={w - pad - 60} y={h - 6} fill="#94a3b8" fontSize="10">
          {res.end_date}
        </text>
      </svg>
    );
  };

  return (
    <div className="space-y-5">
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-base font-semibold">10-Year Multi-Stock Portfolio Backtesting</h2>
            <p className="text-xs opacity-70 mt-0.5">
              Simulate historical portfolio growth over up to 10 years using your selected stocks, rebalancing rules, and realistic transaction costs.
            </p>
          </div>
          {selectedPortfolioIds.length >= 2 && (
            <button
              type="button"
              onClick={syncFromPortfolio}
              className="px-3 py-1.5 rounded-lg text-xs border border-blue-500/40 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20"
            >
              Load Current Portfolio ({selectedPortfolioIds.length} stocks)
            </button>
          )}
        </div>

        {/* Selected stocks chips (clean tickers only) */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {tickers.map((id) => (
            <span
              key={id}
              title={id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono font-semibold bg-blue-600/20 text-blue-300 border border-blue-500/40"
            >
              {cleanSym(id)}
              <button
                type="button"
                onClick={() => setTickers(tickers.filter((t) => t !== id))}
                className="opacity-70 hover:opacity-100"
              >
                ×
              </button>
            </span>
          ))}
          <div className="flex items-center gap-1.5">
            <input
              value={addInput}
              onChange={(e) => setAddInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddTicker()}
              placeholder="Add ticker (e.g. NVDA, FPT)..."
              className={`rounded-lg border px-2.5 py-1 text-xs w-44 ${
                darkMode ? 'bg-slate-950 border-slate-700' : 'bg-slate-50 border-slate-300'
              }`}
            />
            <button
              type="button"
              onClick={handleAddTicker}
              className="px-2.5 py-1 rounded-lg text-xs border border-slate-700 hover:border-blue-500"
            >
              + Add
            </button>
          </div>
        </div>

        {/* Parameters */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
          <div>
            <label className="text-[11px] opacity-65 block mb-1">Backtest Horizon</label>
            <select
              value={years}
              onChange={(e) => setYears(Number(e.target.value))}
              className={`w-full rounded-lg border px-2.5 py-1.5 text-xs ${
                darkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-slate-300'
              }`}
            >
              <option value={10}>10 Years (Default)</option>
              <option value={5}>5 Years</option>
              <option value={3}>3 Years</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] opacity-65 block mb-1">Weighting Strategy</label>
            <select
              value={allocation}
              onChange={(e) => setAllocation(e.target.value as any)}
              className={`w-full rounded-lg border px-2.5 py-1.5 text-xs ${
                darkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-slate-300'
              }`}
            >
              <option value="equal_weight">Equal Weight (1/N)</option>
              <option value="min_variance">Min Variance (GMV)</option>
              <option value="max_sharpe">Max Sharpe Ratio</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] opacity-65 block mb-1">Rebalancing</label>
            <select
              value={rebalance}
              onChange={(e) => setRebalance(e.target.value as any)}
              className={`w-full rounded-lg border px-2.5 py-1.5 text-xs ${
                darkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-slate-300'
              }`}
            >
              <option value="quarterly">Quarterly</option>
              <option value="annually">Annually</option>
              <option value="buy_and_hold">Buy & Hold (No Rebal)</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] opacity-65 block mb-1">Initial Capital ($)</label>
            <input
              type="number"
              min={1000}
              step={10000}
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value) || 100000)}
              className={`w-full rounded-lg border px-2.5 py-1.5 text-xs font-mono ${
                darkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-slate-300'
              }`}
            />
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleRun}
              disabled={loading}
              className="w-full py-1.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition disabled:opacity-50"
            >
              {loading ? 'Running 10Y Test...' : 'Run Portfolio Backtest'}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-300">
          {error}
        </div>
      )}

      {result && (
        <>
          {/* KPI Summary */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className={`rounded-xl border p-4 ${cardBg}`}>
              <div className="text-[11px] opacity-65">Final Value ({result.years_covered}Y)</div>
              <div className="text-lg font-bold font-mono text-emerald-400 mt-1">
                ${result.final_portfolio_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div className="text-[10px] opacity-65">
                Total: {(result.total_return * 100).toFixed(1)}%
              </div>
            </div>
            <div className={`rounded-xl border p-4 ${cardBg}`}>
              <div className="text-[11px] opacity-65">CAGR (Annualized)</div>
              <div className="text-lg font-bold font-mono text-blue-400 mt-1">
                {(result.cagr * 100).toFixed(2)}%
              </div>
              <div className="text-[10px] opacity-65">
                Bench: {(result.benchmark_cagr * 100).toFixed(2)}%
              </div>
            </div>
            <div className={`rounded-xl border p-4 ${cardBg}`}>
              <div className="text-[11px] opacity-65">Sharpe / Volatility</div>
              <div className="text-lg font-bold font-mono mt-1">
                {result.sharpe_ratio?.toFixed(2) ?? 'N/A'}
              </div>
              <div className="text-[10px] opacity-65">
                Vol: {(result.annualized_volatility * 100).toFixed(1)}%
              </div>
            </div>
            <div className={`rounded-xl border p-4 ${cardBg}`}>
              <div className="text-[11px] opacity-65">Max Drawdown</div>
              <div className="text-lg font-bold font-mono text-rose-400 mt-1">
                {(result.max_drawdown * 100).toFixed(1)}%
              </div>
              <div className="text-[10px] opacity-65">Peak-to-trough</div>
            </div>
            <div className={`rounded-xl border p-4 ${cardBg}`}>
              <div className="text-[11px] opacity-65">Rebalances & Costs</div>
              <div className="text-lg font-bold font-mono mt-1">{result.rebalance_count}</div>
              <div className="text-[10px] opacity-65">
                Costs: ${result.total_transaction_costs.toLocaleString()}
              </div>
            </div>
          </div>

          {/* Equity Curve Chart */}
          <div className={`rounded-xl border p-5 ${cardBg}`}>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div className="text-sm font-semibold">
                Portfolio Growth Curve ({result.start_date} → {result.end_date})
              </div>
              <div className="flex items-center gap-4 text-[11px]">
                <span className="text-blue-400">━━ Selected Portfolio ({result.allocation_method})</span>
                <span className="text-slate-400">┄┄ Equal-Weight Buy & Hold</span>
              </div>
            </div>
            {renderEquitySvg(result)}

            {/* Target Weights */}
            <div className="mt-4 pt-3 border-t border-slate-800/70 flex flex-wrap gap-2">
              {Object.entries(result.target_weights).map(([id, w]) => (
                <span
                  key={id}
                  className="px-2.5 py-1 rounded-lg text-xs font-mono bg-slate-800/70 border border-slate-700/70"
                >
                  {cleanSym(id)}: <strong>{(w * 100).toFixed(1)}%</strong>
                </span>
              ))}
            </div>
          </div>

          {/* Calendar-Year Returns */}
          {result.calendar_year_returns.length > 0 && (
            <div className={`rounded-xl border p-5 ${cardBg}`}>
              <div className="text-sm font-semibold mb-3">Calendar-Year Performance Breakdown</div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
                {result.calendar_year_returns.map((yr) => (
                  <div
                    key={yr.year}
                    className={`rounded-lg border p-2.5 text-xs ${
                      darkMode ? 'bg-slate-950/70 border-slate-800' : 'bg-slate-50 border-slate-200'
                    }`}
                  >
                    <div className="font-semibold opacity-70">{yr.year}</div>
                    <div
                      className={`text-sm font-bold font-mono mt-0.5 ${
                        yr.portfolio_return >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {yr.portfolio_return >= 0 ? '+' : ''}
                      {(yr.portfolio_return * 100).toFixed(1)}%
                    </div>
                    <div className="text-[10px] opacity-60">
                      B&H: {yr.benchmark_return >= 0 ? '+' : ''}
                      {(yr.benchmark_return * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
