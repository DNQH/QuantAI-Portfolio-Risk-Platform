import React, { useEffect, useState } from 'react';
import { quantApi, type RiskTrackerResponse } from '../services/api';

interface Props {
  darkMode: boolean;
  onInspectStockRisk: (instrumentId: string) => void;
}

const MARKET_SCOPES = ['ALL', 'United States', 'Vietnam', 'Italy'] as const;

const TIER_STYLE: Record<string, string> = {
  SEVERE: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
  HIGH: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  MODERATE: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  'LOW / RESILIENT': 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40',
};

const DIR_STYLE: Record<string, string> = {
  HEADWIND: 'bg-rose-500/15 text-rose-300 border-rose-500/35',
  MIXED: 'bg-amber-500/15 text-amber-300 border-amber-500/35',
  'NATURAL HEDGE': 'bg-emerald-500/15 text-emerald-400 border-emerald-500/35',
};

export const RiskTrackerPanel: React.FC<Props> = ({ darkMode, onInspectStockRisk }) => {
  const [riskId, setRiskId] = useState<string>('rates_tightening');
  const [marketFilter, setMarketFilter] = useState<string>('ALL');
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [data, setData] = useState<RiskTrackerResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const cardBg = darkMode
    ? 'bg-slate-900/75 border-slate-800'
    : 'bg-white border-slate-200 shadow-sm';
  const subBg = darkMode
    ? 'bg-slate-950/75 border-slate-800'
    : 'bg-slate-50 border-slate-200';

  useEffect(() => {
    let active = true;
    setLoading(true);
    quantApi
      .getRiskTracker(riskId, marketFilter)
      .then((res) => {
        if (!active) return;
        setData(res);
        setSelectedSector((prev) =>
          prev && res.sector_impacts.some((s) => s.sector === prev)
            ? prev
            : res.sector_impacts[0]?.sector ?? null
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [riskId, marketFilter]);

  const activeSectorObj = data?.sector_impacts.find((s) => s.sector === selectedSector) || data?.sector_impacts[0];

  return (
    <div className="space-y-6">
      {/* ACTIVE MARKET RISK FACTORS SELECTOR */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-base font-bold">Active Market & Macro Risk Factors</h2>
            <p className="text-xs opacity-70 mt-0.5">
              Select a systemic risk factor to evaluate 10-year historical impact, forward outlook, and stock-level vulnerability across all 11 GICS sectors.
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {MARKET_SCOPES.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMarketFilter(m)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition ${
                  marketFilter === m
                    ? 'bg-blue-600/20 text-blue-300 border-blue-500/60'
                    : darkMode
                    ? 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-600'
                    : 'bg-slate-100 border-slate-300 text-slate-600'
                }`}
              >
                {m === 'ALL' ? 'All Markets' : m}
              </button>
            ))}
          </div>
        </div>

        {data && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-2.5">
            {data.active_risk_factors.map((rf) => {
              const active = rf.risk_id === riskId;
              return (
                <button
                  key={rf.risk_id}
                  type="button"
                  onClick={() => setRiskId(rf.risk_id)}
                  className={`text-left rounded-xl border p-3 transition ${
                    active
                      ? 'bg-blue-600/20 border-blue-500 text-slate-100'
                      : `${subBg} hover:border-slate-600 opacity-85 hover:opacity-100`
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 text-[10px] font-mono">
                    <span className="opacity-70">{rf.category}</span>
                    <span
                      className={
                        rf.current_intensity === 'HIGH'
                          ? 'text-rose-400 font-bold'
                          : rf.current_intensity === 'ELEVATED'
                          ? 'text-amber-300 font-bold'
                          : 'text-blue-300 font-bold'
                      }
                    >
                      {rf.current_intensity}
                    </span>
                  </div>
                  <div className="text-xs font-semibold mt-1 leading-snug">{rf.name}</div>
                  <div className="text-[10px] opacity-65 mt-1.5">Trend: {rf.trend}</div>
                </button>
              );
            })}
          </div>
        )}

        {/* Selected Risk 10-Year Evidence & Forward Outlook */}
        {data && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4 pt-4 border-t border-slate-800/70">
            <div className={`rounded-lg border p-3.5 ${subBg}`}>
              <div className="text-[11px] font-bold text-amber-300 uppercase tracking-wider">
                10-Year Historical Impact (2016–2026)
              </div>
              <p className="text-xs opacity-85 mt-1.5 leading-relaxed">
                {data.selected_risk.ten_year_episodes}
              </p>
            </div>
            <div className={`rounded-lg border p-3.5 ${subBg}`}>
              <div className="text-[11px] font-bold text-blue-400 uppercase tracking-wider">
                Forward Trajectory (Next 12–36 Months)
              </div>
              <p className="text-xs opacity-85 mt-1.5 leading-relaxed">
                {data.selected_risk.forward_outlook_12_36m}
              </p>
            </div>
          </div>
        )}
      </div>

      {loading && (
        <div className={`rounded-xl border p-8 text-center text-xs opacity-70 ${cardBg}`}>
          Analyzing systemic risk transmission across all 11 GICS sectors...
        </div>
      )}

      {/* ALL 11 GICS SECTORS RANKED MOST -> LEAST IMPACTED */}
      {data && !loading && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left: 11 GICS Sectors Ranking */}
          <div className={`lg:col-span-5 rounded-xl border p-5 ${cardBg}`}>
            <h3 className="text-sm font-bold mb-1">11 GICS Sectors (Most → Least Impacted)</h3>
            <p className="text-[11px] opacity-65 mb-3">
              Click any sector to inspect its 10-year sensitivity and ranked stocks.
            </p>
            <div className="space-y-2">
              {data.sector_impacts.map((sec) => {
                const isSel = activeSectorObj?.sector === sec.sector;
                return (
                  <button
                    key={sec.sector}
                    type="button"
                    onClick={() => setSelectedSector(sec.sector)}
                    className={`w-full text-left rounded-lg border p-3 transition ${
                      isSel
                        ? 'border-blue-500 bg-blue-600/15'
                        : `${subBg} hover:border-slate-600`
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-semibold">{sec.sector}</span>
                      <div className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${DIR_STYLE[sec.direction]}`}>
                          {sec.direction}
                        </span>
                        <span className="font-mono font-bold text-xs w-11 text-right">
                          {sec.severity_score}/100
                        </span>
                      </div>
                    </div>
                    <div className="mt-1.5 h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className={
                          sec.severity_score >= 70
                            ? 'h-full bg-rose-500'
                            : sec.severity_score >= 45
                            ? 'h-full bg-amber-400'
                            : 'h-full bg-emerald-500'
                        }
                        style={{ width: `${sec.severity_score}%` }}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: Selected Sector 10Y Evidence, Forward Forecast & Ranked Stocks */}
          <div className={`lg:col-span-7 rounded-xl border p-5 ${cardBg}`}>
            {activeSectorObj && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <div>
                    <h3 className="text-sm font-bold">
                      {activeSectorObj.sector} — Stock Vulnerability Ranking (Severe → Resilient)
                    </h3>
                    <p className="text-[11px] opacity-65">
                      Impact Score: {activeSectorObj.severity_score}/100 · {activeSectorObj.direction}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4 text-xs">
                  <div className={`rounded-lg border p-3 ${subBg}`}>
                    <div className="text-[10px] uppercase tracking-wider text-amber-300 font-semibold">
                      Sector 10-Year Historical Impact
                    </div>
                    <p className="mt-1 opacity-85 leading-relaxed">{activeSectorObj.historical_10y_behavior}</p>
                  </div>
                  <div className={`rounded-lg border p-3 ${subBg}`}>
                    <div className="text-[10px] uppercase tracking-wider text-blue-400 font-semibold">
                      Sector Forward Outlook
                    </div>
                    <p className="mt-1 opacity-85 leading-relaxed">{activeSectorObj.forward_impact_forecast}</p>
                  </div>
                </div>

                {activeSectorObj.stocks_ranked.length === 0 ? (
                  <div className="text-xs opacity-65 py-6 text-center">
                    No catalog stocks in {activeSectorObj.sector} for the selected market filter — switch to &ldquo;All Markets&rdquo; to see global leaders.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="opacity-60 border-b border-slate-800">
                        <tr>
                          <th className="py-2 pr-2">Ticker</th>
                          <th className="py-2 px-2">Vulnerability</th>
                          <th className="py-2 px-2">10Y Impact & Forward Outlook</th>
                          <th className="py-2 pl-2 text-right">Deep Dive</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {activeSectorObj.stocks_ranked.map((st) => (
                          <tr key={st.instrument_id}>
                            <td className="py-2.5 pr-2 align-top">
                              <div className="font-mono font-bold text-blue-400">{st.ticker}</div>
                              <div className="text-[10px] opacity-60">{st.exchange} · {st.country}</div>
                            </td>
                            <td className="py-2.5 px-2 align-top whitespace-nowrap">
                              <div className="font-mono font-bold">{st.vulnerability_score}/100</div>
                              <span className={`inline-block mt-1 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${TIER_STYLE[st.impact_tier]}`}>
                                {st.impact_tier}
                              </span>
                            </td>
                            <td className="py-2.5 px-2 align-top space-y-1">
                              <div className="text-[11px] opacity-85">
                                <span className="font-semibold text-amber-300">10Y:</span> {st.historical_10y_impact}
                              </div>
                              <div className="text-[11px] opacity-80">
                                <span className="font-semibold text-blue-400">Outlook:</span> {st.forward_outlook}
                              </div>
                            </td>
                            <td className="py-2.5 pl-2 align-top text-right whitespace-nowrap">
                              <button
                                type="button"
                                onClick={() => onInspectStockRisk(st.instrument_id)}
                                className="text-[11px] text-amber-300 hover:underline font-medium"
                              >
                                Risk Analytics →
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* EMERGING FUTURE RISK HYPOTHESES */}
      {data && !loading && (
        <div className={`rounded-xl border p-5 ${cardBg}`}>
          <h3 className="text-sm font-bold mb-1">Emerging Future Risk Hypotheses (What Could Hit Next?)</h3>
          <p className="text-xs opacity-65 mb-4">
            Forward-looking institutional scenarios outlining additional systemic risks that may materialize over the next 6–36 months and how to hedge them.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {data.emerging_hypotheses.map((h, idx) => (
              <div key={idx} className={`rounded-xl border p-4 flex flex-col justify-between ${subBg}`}>
                <div>
                  <div className="flex items-center justify-between gap-2 text-[10px] font-mono">
                    <span className="px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/30 font-bold">
                      {h.probability_tier}
                    </span>
                    <span className="opacity-65">{h.horizon}</span>
                  </div>
                  <div className="text-xs font-bold mt-2">{h.title}</div>
                  <p className="text-[11px] opacity-80 mt-1.5 leading-relaxed">{h.transmission_mechanism}</p>
                </div>
                <div className="mt-3 pt-2.5 border-t border-slate-800/70 space-y-1.5 text-[11px]">
                  <div>
                    <span className="text-rose-400 font-semibold">Most Exposed:</span>{' '}
                    <span className="opacity-85">{h.most_exposed_sectors.join(', ')}</span>
                  </div>
                  <div>
                    <span className="text-emerald-400 font-semibold">Defensive Hedge:</span>{' '}
                    <span className="opacity-85">{h.resilient_hedge_sectors.join(', ')}</span>
                  </div>
                  <div className="text-[10px] opacity-75 italic pt-1">{h.portfolio_defense}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
