import React, { useEffect, useState } from 'react';
import {
  quantApi,
  type DiverseRiskAdvisorResponse,
  type DiverseRiskResponse,
  type MarketBlueprintResponse,
} from '../services/api';

interface Props {
  panelBg: string;
}

type MarketScope = 'US' | 'VN' | 'US_VN' | 'GLOBAL';

const MARKET_OPTIONS: Array<{ key: MarketScope; label: string; desc: string }> = [
  { key: 'US', label: 'United States', desc: 'NYSE & NASDAQ' },
  { key: 'VN', label: 'Vietnam', desc: 'HOSE & HNX' },
  { key: 'US_VN', label: 'Cross-Market (US + VN)', desc: 'Dual-market hedge' },
  { key: 'GLOBAL', label: 'Global Multi-Market', desc: 'US, VN, EU, Asia, AU' },
];

const CROSS_MARKET_CANDIDATES: Record<MarketScope, string[]> = {
  US: ['XNYS:SPY', 'XNYS:BRK.B', 'XNYS:JPM', 'XNAS:MSFT', 'XNAS:GOOGL'],
  VN: ['XSTC:VNM', 'XSTC:GAS', 'XSTC:POW', 'XSTC:REE', 'XSTC:VCB', 'XSTC:DGC'],
  US_VN: ['XSTC:VNM', 'XSTC:GAS', 'XSTC:POW', 'XNYS:SPY', 'XNYS:BRK.B', 'XSTC:FPT'],
  GLOBAL: ['XSWX:NESN', 'XMIL:ENEL', 'XSTC:VNM', 'XSTC:GAS', 'XSES:D05', 'XTKS:7203', 'XASX:BHP'],
};

const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;

export const DiverseRiskPanel: React.FC<Props> = ({ panelBg }) => {
  // Step 1: Market Scope (NO pre-selected default stocks!)
  const [marketScope, setMarketScope] = useState<MarketScope>('VN');
  const [blueprint, setBlueprint] = useState<MarketBlueprintResponse | null>(null);

  // Step 2: Industry / Sector Selection
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);

  // Step 3: Selected Stocks (starts empty — user picks via blueprint, industry list, or custom input)
  const [selected, setSelected] = useState<string[]>([]);
  const [tickerInput, setTickerInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<DiverseRiskResponse | null>(null);

  // Step 4: Interactive AI Refinement Chat
  const [question, setQuestion] = useState('');
  const [advisorLoading, setAdvisorLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<
    Array<{ q: string; res: DiverseRiskAdvisorResponse }>
  >([]);

  useEffect(() => {
    setSelected([]);
    setSelectedSectors([]);
    setResult(null);
    setChatHistory([]);
    setErrorMsg(null);
    quantApi
      .getMarketBlueprint(marketScope)
      .then((bp) => {
        setBlueprint(bp);
        if (bp.recommended_blueprints.length > 0) {
          setSelectedSectors(bp.recommended_blueprints[0].sectors);
        }
      })
      .catch((err) => setErrorMsg(String(err)));
  }, [marketScope]);

  const toggleSector = (sec: string) => {
    setSelectedSectors((prev) =>
      prev.includes(sec) ? prev.filter((s) => s !== sec) : [...prev, sec]
    );
  };

  const applyBlueprint = (sectors: string[], tickers: string[]) => {
    setSelectedSectors(sectors);
    setSelected(tickers.slice(0, 10));
    setErrorMsg(null);
  };

  const addTicker = (raw: string) => {
    const clean = raw.trim().toUpperCase();
    if (!clean) return;
    if (!clean.includes(':')) {
      setErrorMsg('Use exchange-qualified format MIC:TICKER (e.g., XSTC:FPT or XNAS:AAPL).');
      return;
    }
    if (selected.includes(clean)) return;
    if (selected.length >= 10) {
      setErrorMsg('Maximum of 10 stocks allowed in Diverse-Risk.');
      return;
    }
    setErrorMsg(null);
    setSelected((prev) => [...prev, clean]);
    setTickerInput('');
  };

  const removeTicker = (sym: string) => {
    setSelected((prev) => prev.filter((s) => s !== sym));
  };

  const runAnalysis = async (stockList: string[], autoAskAi = false) => {
    if (stockList.length < 2) {
      setErrorMsg('Select at least 2 stocks (or click a Recommended Industry Blueprint) to analyze.');
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    setChatHistory([]);
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
              // Skip unavailable ticker
            }
          })
        );
        return maps;
      };

      const selectedMaps = await fetchMap(stockList);
      if (Object.keys(selectedMaps).length < 2) {
        setErrorMsg('Could not retrieve sufficient historical prices for at least 2 selected stocks.');
        return;
      }

      const candidateIds = (CROSS_MARKET_CANDIDATES[marketScope] || []).filter(
        (c) => !stockList.includes(c)
      );
      const candidateMaps = await fetchMap(candidateIds);

      const analysis = await quantApi.analyzeDiverseRisk(selectedMaps, candidateMaps);
      setResult(analysis);

      if (autoAskAi) {
        setAdvisorLoading(true);
        const initPrompt = `Design a minimum-risk portfolio proposal for the ${marketScope} market combining these industries (${selectedSectors.join(', ')}) and explain recommended weights and any adjustments.`;
        try {
          const aiRes = await quantApi.askDiverseRiskAdvisor(
            initPrompt,
            analysis,
            marketScope,
            selectedSectors
          );
          setChatHistory([{ q: 'AI Portfolio Proposal (Based on Selected Market & Industries)', res: aiRes }]);
        } finally {
          setAdvisorLoading(false);
        }
      }
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateAiPortfolio = async () => {
    if (!blueprint) return;
    let chosen = [...selected];
    // If user hasn't picked stocks yet, auto-pick 1–2 leaders from each selected industry (up to 6 stocks)
    if (chosen.length < 2) {
      const targetSectors = selectedSectors.length > 0 ? selectedSectors : blueprint.sectors.slice(0, 4).map((s) => s.sector);
      const autoPicked: string[] = [];
      for (const grp of blueprint.sectors) {
        if (targetSectors.includes(grp.sector) && grp.stocks.length > 0) {
          autoPicked.push(grp.stocks[0].instrument_id);
          if (autoPicked.length >= 6) break;
        }
      }
      chosen = autoPicked;
      setSelected(chosen);
    }
    await runAnalysis(chosen, true);
  };

  const handleAskAdvisor = async (promptText?: string) => {
    if (!result) return;
    const q = (promptText ?? question).trim();
    if (!q) return;
    setAdvisorLoading(true);
    setErrorMsg(null);
    try {
      const res = await quantApi.askDiverseRiskAdvisor(q, result, marketScope, selectedSectors);
      setChatHistory((prev) => [...prev, { q, res }]);
      if (!promptText) setQuestion('');
    } catch (err) {
      setErrorMsg(String(err));
    } finally {
      setAdvisorLoading(false);
    }
  };

  const visibleSectorGroups = (blueprint?.sectors ?? []).filter(
    (g) => selectedSectors.length === 0 || selectedSectors.includes(g.sector)
  );

  const verdictStyle =
    result?.verdict === 'STRONG_RISK_REDUCTION'
      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
      : result?.verdict === 'MODERATE_RISK_REDUCTION'
      ? 'border-blue-500/40 bg-blue-500/10 text-blue-300'
      : 'border-amber-500/40 bg-amber-500/10 text-amber-300';

  return (
    <div className="space-y-6">
      {/* STEP 1: Market Universe Selection */}
      <div className={`rounded-lg border p-4 space-y-3 ${panelBg}`}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Step 1 · Choose Target Market Universe</h2>
          <span className="font-mono text-[11px] opacity-65">Top-Down Risk Diversification</span>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {MARKET_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              onClick={() => setMarketScope(opt.key)}
              className={`rounded-lg border p-3 text-left transition ${
                marketScope === opt.key
                  ? 'border-emerald-500 bg-emerald-600/15 text-emerald-200'
                  : 'border-slate-600/40 opacity-80 hover:opacity-100'
              }`}
            >
              <div className="text-xs font-semibold">{opt.label}</div>
              <div className="text-[11px] opacity-70 mt-0.5">{opt.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* STEP 2: Recommended Industry Combinations */}
      {blueprint && (
        <div className={`rounded-lg border p-4 space-y-4 ${panelBg}`}>
          <div>
            <h2 className="text-sm font-semibold">Step 2 · Recommended Industry Combinations ({blueprint.market_label})</h2>
            <p className="text-xs opacity-70">
              Select a recommended low-correlation industry pairing or toggle individual sectors below.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {blueprint.recommended_blueprints.map((bp) => (
              <div key={bp.name} className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-3.5 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-semibold text-blue-300">{bp.name}</div>
                  <button
                    onClick={() => applyBlueprint(bp.sectors, bp.suggested_tickers)}
                    className="rounded bg-blue-600/80 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-blue-500"
                  >
                    Use This Pairing
                  </button>
                </div>
                <div className="text-[11px] opacity-80">{bp.rationale}</div>
                <div className="flex flex-wrap gap-1">
                  {bp.sectors.map((s) => (
                    <span key={s} className="rounded bg-slate-700/60 px-2 py-0.5 font-mono text-[10px]">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Individual Sector Toggle Pills */}
          <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-terminal-border">
            <span className="text-[11px] opacity-70 mr-1">Filter Industries:</span>
            {blueprint.sectors.map((grp) => {
              const active = selectedSectors.includes(grp.sector);
              return (
                <button
                  key={grp.sector}
                  onClick={() => toggleSector(grp.sector)}
                  className={`rounded border px-2.5 py-1 text-[11px] transition ${
                    active
                      ? 'border-emerald-500 bg-emerald-600/20 text-emerald-300'
                      : 'border-slate-600/40 opacity-75 hover:opacity-100'
                  }`}
                >
                  {grp.sector} ({grp.stocks.length})
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* STEP 3: Stock Selection Within Chosen Industries (Max 10) */}
      <div className={`rounded-lg border p-4 space-y-4 ${panelBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Step 3 · Select Stocks (Up to 10) or Generate AI Portfolio</h2>
            <p className="text-xs opacity-70">
              Pick stocks from your selected industries below, type any custom MIC:TICKER, or let AI build a minimum-risk portfolio automatically.
            </p>
          </div>
          <span className="font-mono text-xs px-2.5 py-1 rounded border border-blue-500/40 text-blue-300">
            {selected.length} / 10 Stocks
          </span>
        </div>

        {/* Industry-grouped clickable stock picker */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {visibleSectorGroups.map((grp) => (
            <div key={grp.sector} className="rounded border border-terminal-border p-2.5 space-y-1.5">
              <div className="text-[11px] font-semibold opacity-80">{grp.sector}</div>
              <div className="flex flex-wrap gap-1.5">
                {grp.stocks.slice(0, 8).map((st) => {
                  const isPicked = selected.includes(st.instrument_id);
                  return (
                    <button
                      key={st.instrument_id}
                      onClick={() => (isPicked ? removeTicker(st.instrument_id) : addTicker(st.instrument_id))}
                      className={`rounded border px-2 py-0.5 font-mono text-[11px] transition ${
                        isPicked
                          ? 'border-blue-500 bg-blue-600/25 text-blue-200'
                          : 'border-slate-600/40 opacity-80 hover:border-blue-400'
                      }`}
                    >
                      {isPicked ? '✓ ' : '+ '}
                      {st.instrument_id}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Custom ticker + Action Buttons */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-terminal-border">
          <input
            type="text"
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') addTicker(tickerInput);
            }}
            placeholder="Or type custom MIC:TICKER (e.g. XSTC:MWG, XNAS:NVDA)..."
            className={`flex-1 min-w-[240px] rounded border px-3 py-1.5 font-mono text-xs ${panelBg}`}
          />
          <button
            onClick={() => addTicker(tickerInput)}
            disabled={selected.length >= 10}
            className="rounded border border-slate-500/50 px-3 py-1.5 text-xs hover:border-blue-400 disabled:opacity-40"
          >
            + Add
          </button>
          <button
            onClick={handleGenerateAiPortfolio}
            disabled={loading}
            className="rounded bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? 'Building...' : 'Generate AI Risk-Minimizing Portfolio'}
          </button>
          <button
            onClick={() => runAnalysis(selected, false)}
            disabled={loading || selected.length < 2}
            className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            Check Risk Reduction
          </button>
        </div>

        {selected.length > 0 && (
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
        )}

        {errorMsg && (
          <div className="rounded border border-rose-500/40 bg-rose-500/10 p-2.5 text-xs text-rose-400">
            {errorMsg}
          </div>
        )}
      </div>

      {/* RESULTS & STEP 4: AI REFINEMENT CHAT */}
      {result && (
        <>
          <div className={`rounded-lg border p-4 ${verdictStyle}`}>
            <div className="font-mono text-xs font-bold tracking-wider uppercase">
              {result.verdict.replace(/_/g, ' ')}
            </div>
            <p className="mt-1 text-sm">{result.verdict_summary}</p>
          </div>

          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="text-xs opacity-70">Risk Reduction (Eq / GMV)</div>
              <div className="mt-1 font-mono text-lg font-bold text-emerald-400">
                -{result.risk_reduction_pct.toFixed(1)}% / -{result.gmv_risk_reduction_pct.toFixed(1)}%
              </div>
            </div>
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="text-xs opacity-70">Diversification Ratio (DR)</div>
              <div className="mt-1 font-mono text-lg font-bold text-blue-400">
                {result.diversification_ratio.toFixed(2)}x
              </div>
            </div>
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="text-xs opacity-70">Portfolio Vol vs Standalone</div>
              <div className="mt-1 font-mono text-lg font-bold">
                {fmtPct(result.equal_weight_volatility)} vs {fmtPct(result.standalone_weighted_volatility)}
              </div>
            </div>
            <div className={`rounded-lg border p-4 ${panelBg}`}>
              <div className="text-xs opacity-70">Avg Corr / Eff. Bets</div>
              <div className="mt-1 font-mono text-lg font-bold">
                {result.avg_pairwise_correlation.toFixed(2)} / {result.effective_num_bets.toFixed(1)}
              </div>
            </div>
          </div>

          {/* STEP 4: Interactive AI Portfolio Refinement */}
          <div className={`rounded-lg border p-4 space-y-4 ${panelBg}`}>
            <div className="border-b border-terminal-border pb-3">
              <h3 className="text-sm font-semibold text-blue-300">
                Step 4 · Customize &amp; Refine Portfolio with QuantAI Strategist
              </h3>
              <p className="text-xs opacity-70">
                Ask follow-up questions to swap sectors, add defensive hedges, adjust weights, or tailor the portfolio to your risk tolerance.
              </p>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleAskAdvisor();
                }}
                placeholder="Ask e.g. 'How can I make this even more defensive?' or 'What if I add Healthcare or Gold ETF?'"
                className={`flex-1 rounded border px-3 py-2 text-xs ${panelBg}`}
              />
              <button
                onClick={() => handleAskAdvisor()}
                disabled={advisorLoading || !question.trim()}
                className="rounded bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {advisorLoading ? 'Analyzing...' : 'Ask Strategist'}
              </button>
            </div>

            {chatHistory.length > 0 && (
              <div className="space-y-3 pt-1">
                {chatHistory.map((item, idx) => (
                  <div key={idx} className="rounded-lg border border-terminal-border bg-terminal-bg/60 p-3.5 space-y-2">
                    <div className="text-xs font-semibold text-blue-300">{item.q}</div>
                    <div className="whitespace-pre-line text-xs leading-relaxed opacity-90">
                      {item.res.answer}
                    </div>
                    <div className="flex items-center justify-between border-t border-terminal-border pt-2 text-[10px] opacity-60">
                      <span>{item.res.engine_used}</span>
                      <span>Grounded on verified portfolio metrics</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Optimal Risk-Reducing Combinations Table */}
          <div className={`overflow-x-auto rounded-lg border ${panelBg}`}>
            <div className="p-4 border-b border-terminal-border">
              <h3 className="text-sm font-semibold">Optimal Minimum-Variance Stock Combinations</h3>
            </div>
            <table className="w-full text-left text-xs">
              <thead className="border-b border-terminal-border font-mono opacity-70">
                <tr>
                  <th className="p-3">Combination</th>
                  <th className="p-3">Portfolio Vol</th>
                  <th className="p-3">Risk Reduction</th>
                  <th className="p-3">DR</th>
                  <th className="p-3">Min-Var Weights</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-terminal-border font-mono">
                {result.suggested_combinations.map((c, idx) => (
                  <tr key={idx}>
                    <td className="p-3 font-semibold">{c.symbols.join(' + ')}</td>
                    <td className="p-3 text-emerald-400">{fmtPct(c.portfolio_volatility)}</td>
                    <td className="p-3">-{c.risk_reduction_pct.toFixed(1)}%</td>
                    <td className="p-3">{c.diversification_ratio.toFixed(2)}x</td>
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
        </>
      )}
    </div>
  );
};
