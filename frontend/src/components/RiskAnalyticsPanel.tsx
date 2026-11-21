import React, { useEffect, useState } from 'react';
import { api, type BankruptcyPipelineResponse, type RiskAnalysisResponse } from '../services/api';

interface Props {
  instrumentId: string;
  cleanTicker: string;
  riskData: RiskAnalysisResponse | null;
  darkMode: boolean;
}

const METHOD_LABELS: Record<string, string> = {
  historical: 'Historical Simulation (Actual Past Returns)',
  parametric_normal: 'Parametric Normal (Bell-Curve Estimate)',
  monte_carlo_normal: 'Monte Carlo (10,000 Simulated Days)',
};

const ZONE_BADGE: Record<string, string> = {
  SAFE: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40',
  WATCH: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  DISTRESS: 'bg-rose-500/15 text-rose-400 border-rose-500/40',
};

export const RiskAnalyticsPanel: React.FC<Props> = ({
  instrumentId,
  cleanTicker,
  riskData,
  darkMode,
}) => {
  const [bankruptcy, setBankruptcy] = useState<BankruptcyPipelineResponse | null>(null);
  const [loadingPd, setLoadingPd] = useState(false);

  const cardBg = darkMode
    ? 'bg-slate-900/75 border-slate-800'
    : 'bg-white border-slate-200 shadow-sm';
  const subBoxBg = darkMode
    ? 'bg-slate-950/75 border-slate-800'
    : 'bg-slate-50 border-slate-200';

  useEffect(() => {
    let active = true;
    setLoadingPd(true);
    api
      .runBankruptcyPipeline(instrumentId, riskData?.annualized_volatility)
      .then((res) => {
        if (active) setBankruptcy(res);
      })
      .catch(() => {
        if (active) setBankruptcy(null);
      })
      .finally(() => {
        if (active) setLoadingPd(false);
      });
    return () => {
      active = false;
    };
  }, [instrumentId, riskData?.annualized_volatility]);

  const hist95 = riskData?.var_results.find(
    (v) => v.method === 'historical' && Math.round(v.confidence_level * 100) === 95
  );
  const hist99 = riskData?.var_results.find(
    (v) => v.method === 'historical' && Math.round(v.confidence_level * 100) === 99
  );

  const fmtMoney = (n: number) =>
    n >= 1e9
      ? `${(n / 1e9).toFixed(2)}B`
      : n >= 1e6
      ? `${(n / 1e6).toFixed(1)}M`
      : n.toLocaleString(undefined, { maximumFractionDigits: 0 });

  return (
    <div className="space-y-6">
      {/* SECTION 1: PLAIN-ENGLISH DOWNSIDE RISK (VaR / CVaR & STRESS TESTS) */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div>
            <h2 className="text-base font-semibold">
              Market Downside Risk — <span className="text-blue-400">{cleanTicker}</span>
            </h2>
            <p className="text-xs opacity-70 mt-0.5">
              Plain-English translation of how much a $100,000 position could lose on a bad day or during a market crash.
            </p>
          </div>
        </div>

        {riskData && hist95 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            <div className={`rounded-lg border p-4 ${subBoxBg}`}>
              <div className="text-xs opacity-65">Normal Bad Day (95% 1-Day VaR)</div>
              <div className="text-2xl font-bold text-amber-400 font-mono mt-1">
                -${hist95.var_amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                <span className="text-xs opacity-70 font-normal ml-1">({(hist95.var_pct * 100).toFixed(2)}%)</span>
              </div>
              <p className="text-[11px] opacity-75 mt-1.5 leading-relaxed">
                On <strong>19 out of 20</strong> trading days, your daily loss on $100k should stay smaller than this amount.
              </p>
            </div>
            <div className={`rounded-lg border p-4 ${subBoxBg}`}>
              <div className="text-xs opacity-65">Worst 5% Tail Average (95% CVaR)</div>
              <div className="text-2xl font-bold text-rose-400 font-mono mt-1">
                -${hist95.cvar_amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                <span className="text-xs opacity-70 font-normal ml-1">({(hist95.cvar_pct * 100).toFixed(2)}%)</span>
              </div>
              <p className="text-[11px] opacity-75 mt-1.5 leading-relaxed">
                When a rare <strong>1-in-20 bad day</strong> happens, this is the average loss you should prepare for.
              </p>
            </div>
            <div className={`rounded-lg border p-4 ${subBoxBg}`}>
              <div className="text-xs opacity-65">Extreme Shock Day (99% 1-Day VaR)</div>
              <div className="text-2xl font-bold text-rose-300 font-mono mt-1">
                -${(hist99?.var_amount ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                <span className="text-xs opacity-70 font-normal ml-1">
                  ({((hist99?.var_pct ?? 0) * 100).toFixed(2)}%)
                </span>
              </div>
              <p className="text-[11px] opacity-75 mt-1.5 leading-relaxed">
                A <strong>1-in-100</strong> severe single-day drop. Historical Max Drawdown:{' '}
                <span className="text-rose-400 font-semibold">{(riskData.max_drawdown * 100).toFixed(1)}%</span>.
              </p>
            </div>
          </div>
        )}

        {/* VaR Methodology Comparison Table */}
        {riskData && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="opacity-60 border-b border-slate-800">
                <tr>
                  <th className="py-2 pr-3">Risk Model</th>
                  <th className="py-2 px-3">Confidence</th>
                  <th className="py-2 px-3">1-Day VaR (%)</th>
                  <th className="py-2 px-3">Tail Avg CVaR (%)</th>
                  <th className="py-2 px-3">Est. Loss ($100k)</th>
                  <th className="py-2 pl-3">Tail Loss ($100k)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {riskData.var_results.map((v, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-3 font-medium">{METHOD_LABELS[v.method] || v.method}</td>
                    <td className="py-2 px-3 font-mono">{Math.round(v.confidence_level * 100)}%</td>
                    <td className="py-2 px-3 font-mono text-amber-400">{(v.var_pct * 100).toFixed(2)}%</td>
                    <td className="py-2 px-3 font-mono text-rose-400">{(v.cvar_pct * 100).toFixed(2)}%</td>
                    <td className="py-2 px-3 font-mono">-${v.var_amount.toLocaleString()}</td>
                    <td className="py-2 pl-3 font-mono text-rose-300">-${v.cvar_amount.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Stress Test Visual Bars */}
        {riskData && (
          <div className="mt-5 pt-4 border-t border-slate-800/70">
            <div className="text-xs font-semibold mb-2.5">Historical Crisis Stress Tests (Impact on $100,000)</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {riskData.stress_scenarios.map((s, i) => (
                <div key={i} className={`rounded-lg border p-3 ${subBoxBg}`}>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium">{s.scenario_name}</span>
                    <span className="font-mono text-rose-400 font-semibold">{(s.shock_pct * 100).toFixed(0)}%</span>
                  </div>
                  <div className="mt-1.5 h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-rose-500/80"
                      style={{ width: `${Math.min(100, Math.abs(s.shock_pct) * 200)}%` }}
                    />
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[11px] opacity-75">
                    <span>Est. P&L: ${s.estimated_pnl.toLocaleString()}</span>
                    <span>Remaining: ${s.post_shock_value.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* SECTION 2: 4-STAGE CORPORATE BANKRUPTCY & DEFAULT PROBABILITY PIPELINE */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div>
            <h2 className="text-base font-semibold">
              Corporate Bankruptcy & 12-Month Default Probability Pipeline —{' '}
              <span className="text-blue-400">{cleanTicker}</span>
            </h2>
            <p className="text-xs opacity-70 mt-0.5">
              4-stage credit risk architecture combining Altman Z-Score, Ohlson O-Score, Merton Structural Model, DSCR, Interest Coverage, Logistic Regression, and XGBoost/GBDT.
            </p>
          </div>
          {bankruptcy && (
            <span className="text-[10px] px-2.5 py-1 rounded-full bg-blue-500/15 text-blue-300 border border-blue-500/30">
              Source: {bankruptcy.data_source.replace(/_/g, ' ')}
            </span>
          )}
        </div>

        {loadingPd && (
          <div className="py-8 text-center text-xs opacity-70">
            Running 7-model corporate credit & bankruptcy pipeline for {cleanTicker}...
          </div>
        )}

        {bankruptcy && !loadingPd && (
          <div className="space-y-3">
            {/* STAGE 1 */}
            <div className={`rounded-xl border p-4 ${subBoxBg}`}>
              <div className="text-center mb-3">
                <div className="text-sm font-bold">1. Corporate Financial Statements</div>
                <div className="text-xs opacity-65">
                  Balance Sheet · Income Statement · Cash Flow Statement ({bankruptcy.currency})
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                <div className="p-2.5 rounded-lg bg-slate-900/50 border border-slate-800/70">
                  <div className="opacity-60 text-[10px]">Total Assets</div>
                  <div className="font-mono font-semibold mt-0.5">{fmtMoney(bankruptcy.financials.total_assets)}</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-900/50 border border-slate-800/70">
                  <div className="opacity-60 text-[10px]">Total Debt</div>
                  <div className="font-mono font-semibold mt-0.5">{fmtMoney(bankruptcy.financials.total_debt)}</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-900/50 border border-slate-800/70">
                  <div className="opacity-60 text-[10px]">Revenue / EBIT</div>
                  <div className="font-mono font-semibold mt-0.5">
                    {fmtMoney(bankruptcy.financials.revenue)} / {fmtMoney(bankruptcy.financials.ebit)}
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-900/50 border border-slate-800/70">
                  <div className="opacity-60 text-[10px]">Operating Cash Flow</div>
                  <div className="font-mono font-semibold mt-0.5">{fmtMoney(bankruptcy.financials.operating_cash_flow)}</div>
                </div>
              </div>
            </div>

            <div className="text-center text-lg opacity-50 leading-none">↓</div>

            {/* STAGE 2 */}
            <div className={`rounded-xl border p-4 ${subBoxBg}`}>
              <div className="text-center mb-3">
                <div className="text-sm font-bold">2. Financial Risk Variables</div>
                <div className="text-xs opacity-65">Liquidity · Leverage · Profitability · Cash Flow</div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                {bankruptcy.variables.map((v, i) => (
                  <div key={i} className="p-2.5 rounded-lg bg-slate-900/50 border border-slate-800/70">
                    <div className="flex items-center justify-between text-[10px] opacity-60">
                      <span>{v.category}</span>
                    </div>
                    <div className="text-xs font-medium mt-0.5">{v.name}</div>
                    <div className="text-sm font-bold font-mono text-blue-400 mt-0.5">{v.formatted}</div>
                    <div className="text-[10px] opacity-65 mt-0.5">{v.interpretation}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="text-center text-lg opacity-50 leading-none">↓</div>

            {/* STAGE 3 */}
            <div className={`rounded-xl border p-4 ${subBoxBg}`}>
              <div className="text-center mb-3">
                <div className="text-sm font-bold">3. Bankruptcy & Credit Prediction Models</div>
                <div className="text-xs opacity-65">
                  Altman Z-Score · Ohlson O-Score · Merton Model · DSCR · Interest Coverage · Logistic Regression · XGBoost
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {bankruptcy.models.map((m, i) => (
                  <div key={i} className="p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold">{m.model_name}</span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${ZONE_BADGE[m.zone]}`}>
                          {m.zone}
                        </span>
                      </div>
                      <div className="mt-1.5 flex items-baseline justify-between">
                        <span className="text-sm font-bold font-mono text-blue-300">{m.raw_score_formatted}</span>
                        <span className="text-[11px] font-mono opacity-80">
                          Implied 12M PD: <strong>{(m.implied_pd_12m * 100).toFixed(1)}%</strong>
                        </span>
                      </div>
                      <p className="text-[11px] opacity-75 mt-1.5 leading-snug">{m.plain_english}</p>
                    </div>
                    <div className="text-[10px] opacity-50 font-mono mt-2 pt-1.5 border-t border-slate-800/60 truncate" title={m.formula_summary}>
                      {m.formula_summary}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="text-center text-lg opacity-50 leading-none">↓</div>

            {/* STAGE 4: FINAL PD RESULT CARD (Matching reference diagram) */}
            <div
              className={`rounded-xl border p-6 text-center ${
                bankruptcy.risk_zone === 'SAFE'
                  ? 'bg-emerald-950/40 border-emerald-500/40'
                  : bankruptcy.risk_zone === 'WATCH'
                  ? 'bg-amber-950/40 border-amber-500/40'
                  : 'bg-rose-950/40 border-rose-500/40'
              }`}
            >
              <div className="text-sm font-semibold opacity-90">4. Ensemble Default Forecast Result</div>
              <div
                className={`text-4xl font-extrabold font-mono mt-2 ${
                  bankruptcy.risk_zone === 'SAFE'
                    ? 'text-emerald-400'
                    : bankruptcy.risk_zone === 'WATCH'
                    ? 'text-amber-300'
                    : 'text-rose-400'
                }`}
              >
                PD = {bankruptcy.ensemble_pd_pct.toFixed(1)}%
              </div>
              <div className="text-xs font-semibold mt-1.5 opacity-90">
                12-Month Probability of Default · {bankruptcy.risk_grade}
              </div>
              <p className="text-xs opacity-80 max-w-2xl mx-auto mt-2.5 leading-relaxed">
                {bankruptcy.executive_summary}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
