import React, { useState } from 'react';
import { quantApi, type DiverseRiskResponse } from '../services/api';

interface Props {
  panelBg: string;
}

const QUICK_PRESETS = [
  'XNAS:AAPL',
  'XNAS:MSFT',
  'XNAS:NVDA',
  'XNYS:JPM',
  'XSTC:FPT',
  'XSTC:TCB',
  'XSTC:VNM',
  'XSTC:HPG',
  'XSWX:NESN',
  'XTKS:7203',
  'XLON:HSBA',
  'XASX:BHP',
];

const CROSS_MARKET_CANDIDATES = [
  'XSWX:NESN',
  'XSTC:VNM',
  'XSTC:GAS',
  'XNYS:JPM',
  'XLON:HSBA',
  'XTKS:7203',
  'XASX:BHP',
  'XSES:D05',
];

const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;

export const DiverseRiskPanel: React.FC<Props> = ({ panelBg }) => {
  const [selected, setSelected] = useState<string[]>([
    'XNAS:AAPL',
    'XNAS:MSFT',
    'XSTC:FPT',
    'XSTC:TCB',
  ]);
  const [tickerInput, setTickerInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<DiverseRiskResponse | null>(null);

  const addTicker = (raw: string) => {
    const clean = raw.trim().toUpperCase();
    if (!clean) return;
    if (!clean.includes(':')) {
      setErrorMsg('Please use exchange-qualified format MIC:TICKER (e.g., XNAS:AAPL or XSTC:FPT).');
      return;
    }
    if (selected.includes(clean)) return;
    if (selected.length >= 10) {
      setErrorMsg('Maximum of 10 stocks allowed in Diverse-Risk check.');
      return;
    }
    setErrorMsg(null);
    setSelected((prev) => [...prev, clean]);
    setTickerInput('');
  };

  const removeTicker = (sym: string) => {
    setSelected((prev) => prev.filter((s) => s !== sym));
  };

  const handleCheck = async () => {
    if (selected.length < 2) {
      setErrorMsg('Please select at least 2 stocks (up to 10) to evaluate diversification.');
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      const fetchMap = async (ids: string[]) => {
        const maps: Record<string, Record<string, number>> = {};
        await Promise.all(
          ids.map(async (id) => {
            try {
              const resp = await quantApi.getOhlcv(id, { period: '1y', interval: '1d', allowEducationalFallback: true });
              if (resp.bars.length >= 10) {
                const m: Record<string, number> = {};
                resp.bars.forEach((b) => {
                  m[b.timestamp.slice(0, 10)] = b.adjusted_close ?? b.close;
                });
                maps[id] = m;
              }
            } catch {
              // Skip unavailable candidate gracefully
            }
          })
        );
        return maps;
      };

      const selectedMaps = await fetchMap(selected);
      if (Object.keys(selectedMaps).length < 2) {
        setErrorMsg('Could not retrieve sufficient historical bars for at least 2 selected stocks.');
        return;
      }

      const candidateIds = CROSS_MARKET_CANDIDATES.filter((c) => !selected.includes(c));
      const candidateMaps = await fetchMap(candidateIds);

      const analysis = await quantApi.analyzeDiverseRisk(selectedMaps, candidateMaps);
      setResult(analysis);
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setLoading(false);
    }
  };

  const verdictStyle =
    result?.verdict === 'STRONG_RISK_REDUCTION'
      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
      : result?.verdict === 'MODERATE_RISK_REDUCTION'
      ? 'border-blue-500/40 bg-blue-500/10 text-blue-300'
      : 'border-amber-500/40 bg-amber-500/10 text-amber-300';

  return (
    <div className="space-y-6">
      {/* Input & Stock Basket Builder (Max 10) */}
      <div className={`rounded-lg border p-4 space-y-4 ${panelBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Diverse-Risk — Diversification &amp; Risk-Reduction Check</h2>
            <p className="text-xs opacity-70">
              Select 2 to 10 stocks to test whether your basket genuinely reduces portfolio volatility and discover lower-risk combinations.
            </p>
          </div>
          <span className="font-mono text-xs px-2.5 py-1 rounded border border-blue-500/40 text-blue-300">
            {selected.length} / 10 Stocks
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') addTicker(tickerInput);
            }}
            placeholder="Add stock as MIC:TICKER (e.g. XSTC:MWG, XNAS:GOOGL)..."
            className={`flex-1 min-w-[260px] rounded border px-3 py-1.5 font-mono text-xs ${panelBg}`}
          />
          <button
            onClick={() => addTicker(tickerInput)}
            disabled={selected.length >= 10}
            className="rounded border border-slate-500/50 px-3 py-1.5 text-xs font-medium hover:border-blue-400 disabled:opacity-40"
          >
            + Add Stock
          </button>
          <button
            onClick={handleCheck}
            disabled={loading || selected.length < 2}
            className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {loading ? 'Analyzing...' : 'Check Risk Reduction'}
          </button>
        </div>

        {/* Selected Chips */}
        <div className="flex flex-wrap gap-2">
          {selected.map((sym) => (
            <span
              key={sym}
              className="inline-flex items-center gap-1.5 rounded border border-blue-500/40 bg-blue-600/15 px-2.5 py-1 font-mono text-xs text-blue-200"
            >
              {sym}
              <button onClick={() => removeTicker(sym)} className="text-slate-400 hover:text-rose-400">
                ×
              </button>
            </span>
          ))}
        </div>

        {/* Quick-Add Presets */}
        <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-terminal-border">
          <span className="text-[11px] opacity-60 mr-1">Quick add:</span>
          {QUICK_PRESETS.filter((p) => !selected.includes(p)).map((p) => (
            <button
              key={p}
              onClick={() => addTicker(p)}
              disabled={selected.length >= 10}
              className="rounded border border-slate-600/40 px-2 py-0.5 font-mono text-[10px] opacity-80 hover:opacity-100 hover:border-blue-400 disabled:opacity-30"
            >
              + {p}
            </button>
          ))}
        </div>

        {errorMsg && (
          <div className="rounded border border-rose-500/40 bg-rose-500/10 p-2.5 text-xs text-rose-400">
            {errorMsg}
          </div>
        )}
      </div>

      {/* Analysis Output */}
      {result && (
        <>
          {/* Verdict Banner */}
          <div className={`rounded-lg border p-4 ${verdictStyle}`}>
            <div className="font-mono text-xs font-bold tracking-wider uppercase">{result.verdict.replace(/_/g, ' ')}</div>
            <p className="mt-1 text-sm">{result.verdict_summary}</p>
          </div>

          {/* 4 Core Diversification KPIs */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="text-xs opacity-70">Risk Reduction (Equal Wt / GMV)</div>
              <div className="mt-1 font-mono text-lg font-bold text-emerald-400">
                -{result.risk_reduction_pct.toFixed(1)}% / -{result.gmv_risk_reduction_pct.toFixed(1)}%
              </div>
              <div className="text-[11px] opacity-65">Volatility cut vs standalone avg</div>
            </div>
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="text-xs opacity-70">Diversification Ratio (DR)</div>
              <div className="mt-1 font-mono text-lg font-bold text-blue-400">
                {result.diversification_ratio.toFixed(2)}x
              </div>
              <div className="text-[11px] opacity-65">DR &gt; 1.00 = risk-reducing</div>
            </div>
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="text-xs opacity-70">Portfolio Vol vs Standalone Avg</div>
              <div className="mt-1 font-mono text-lg font-bold">
                {fmtPct(result.equal_weight_volatility)} vs {fmtPct(result.standalone_weighted_volatility)}
              </div>
              <div className="text-[11px] opacity-65">GMV Vol: {fmtPct(result.gmv_volatility)}</div>
            </div>
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="text-xs opacity-70">Avg Correlation / Eff. Bets</div>
              <div className="mt-1 font-mono text-lg font-bold">
                {result.avg_pairwise_correlation.toFixed(2)} / {result.effective_num_bets.toFixed(1)}
              </div>
              <div className="text-[11px] opacity-65">Aligned days: {result.aligned_return_observations}</div>
            </div>
          </div>

          {/* Correlation Pair Diagnostics */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <h3 className="text-xs font-semibold mb-2 text-rose-400">Highest Correlation Pairs (Redundancy Risk)</h3>
              <div className="space-y-1.5 font-mono text-xs">
                {result.highest_correlation_pairs.map((p, idx) => (
                  <div key={idx} className="flex justify-between border-b border-terminal-border pb-1">
                    <span>{p.asset_a} ↔ {p.asset_b}</span>
                    <span className={p.correlation > 0.7 ? 'text-rose-400 font-bold' : ''}>{p.correlation.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <h3 className="text-xs font-semibold mb-2 text-emerald-400">Lowest Correlation Pairs (Strongest Diversifiers)</h3>
              <div className="space-y-1.5 font-mono text-xs">
                {result.lowest_correlation_pairs.map((p, idx) => (
                  <div key={idx} className="flex justify-between border-b border-terminal-border pb-1">
                    <span>{p.asset_a} ↔ {p.asset_b}</span>
                    <span className="text-emerald-400 font-bold">{p.correlation.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Suggested Risk-Reducing Combinations (Section 1: Optimal Subsets) */}
          <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
            <div className="p-4 border-b border-terminal-border">
              <h3 className="text-sm font-semibold">Suggested Risk-Reducing Stock Combinations (From Your Basket)</h3>
              <p className="text-xs opacity-70">
                Top minimum-variance combinations ranked by lowest annualized portfolio volatility and strongest diversification benefit.
              </p>
            </div>
            <table className="w-full text-left text-xs">
              <thead className="border-b border-terminal-border font-mono opacity-70">
                <tr>
                  <th className="p-3">Combination</th>
                  <th className="p-3">Portfolio Vol</th>
                  <th className="p-3">Risk Reduction</th>
                  <th className="p-3">DR</th>
                  <th className="p-3">Avg Corr</th>
                  <th className="p-3">Suggested Min-Var Weights</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-terminal-border font-mono">
                {result.suggested_combinations.map((c, idx) => (
                  <tr key={idx}>
                    <td className="p-3 font-semibold">{c.symbols.join(' + ')}</td>
                    <td className="p-3 text-emerald-400">{fmtPct(c.portfolio_volatility)}</td>
                    <td className="p-3">-{c.risk_reduction_pct.toFixed(1)}%</td>
                    <td className="p-3">{c.diversification_ratio.toFixed(2)}x</td>
                    <td className="p-3">{c.avg_pairwise_correlation.toFixed(2)}</td>
                    <td className="p-3 text-[11px] opacity-85">
                      {Object.entries(c.optimal_weights)
                        .map(([s, w]) => `${s}: ${(w * 100).toFixed(0)}%`)
                        .join(' · ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Suggested Risk-Reducing Additions (Section 2: Cross-Market Candidates) */}
          {result.candidate_additions.length > 0 && (
            <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
              <div className="p-4 border-b border-terminal-border">
                <h3 className="text-sm font-semibold">Suggested Cross-Market Additions to Further Reduce Portfolio Risk</h3>
                <p className="text-xs opacity-70">
                  Evaluates the exact marginal volatility impact of adding each low-correlation global/defensive stock to your current basket.
                </p>
              </div>
              <table className="w-full text-left text-xs">
                <thead className="border-b border-terminal-border font-mono opacity-70">
                  <tr>
                    <th className="p-3">Candidate Stock</th>
                    <th className="p-3">Avg Corr w/ Basket</th>
                    <th className="p-3">New Portfolio Vol</th>
                    <th className="p-3">Marginal Vol Change</th>
                    <th className="p-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-terminal-border font-mono">
                  {result.candidate_additions.map((cand) => (
                    <tr key={cand.symbol}>
                      <td className="p-3 font-semibold">{cand.symbol}</td>
                      <td className="p-3">{cand.avg_correlation_with_portfolio.toFixed(3)}</td>
                      <td className="p-3">{fmtPct(cand.new_portfolio_volatility)}</td>
                      <td className={`p-3 font-bold ${cand.is_risk_reducing ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {cand.volatility_change_pct > 0 ? '+' : ''}
                        {cand.volatility_change_pct.toFixed(2)}%
                      </td>
                      <td className="p-3">
                        <button
                          onClick={() => addTicker(cand.symbol)}
                          disabled={selected.length >= 10 || selected.includes(cand.symbol)}
                          className="rounded border border-emerald-500/40 px-2 py-0.5 text-[11px] text-emerald-300 hover:bg-emerald-500/15 disabled:opacity-30"
                        >
                          + Add to Basket
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className={`rounded-lg border p-3 text-[11px] opacity-75 space-y-1 ${panelBg}`}>
            {result.assumptions.map((a, i) => (
              <p key={i}>• {a}</p>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
