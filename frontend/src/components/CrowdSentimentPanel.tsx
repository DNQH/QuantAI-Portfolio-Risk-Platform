import React, { useEffect, useState } from 'react';
import { api, type CrowdSentimentResponse } from '../services/api';

interface Props {
  instrumentId: string;
  cleanTicker: string;
  companyName: string;
  recentReturn20d?: number | null;
  annualizedVol?: number | null;
  darkMode: boolean;
}

export const CrowdSentimentPanel: React.FC<Props> = ({
  instrumentId,
  cleanTicker,
  companyName,
  recentReturn20d,
  annualizedVol,
  darkMode,
}) => {
  const [horizon, setHorizon] = useState<'1W' | '1M' | '3M'>('1M');
  const [data, setData] = useState<CrowdSentimentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cardBg = darkMode
    ? 'bg-slate-900/70 border-slate-800'
    : 'bg-white border-slate-200 shadow-sm';

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    api
      .analyzeCrowdSentiment(
        instrumentId,
        companyName,
        horizon,
        recentReturn20d ?? undefined,
        annualizedVol ?? undefined
      )
      .then((res) => {
        if (active) setData(res);
      })
      .catch((err) => {
        if (active) setError(err?.message || 'Failed to load crowd sentiment.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [instrumentId, companyName, horizon, recentReturn20d, annualizedVol]);

  const verdictStyle =
    data?.verdict === 'POSITIVE'
      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40'
      : data?.verdict === 'NEGATIVE'
      ? 'bg-rose-500/15 text-rose-400 border-rose-500/40'
      : 'bg-amber-500/15 text-amber-300 border-amber-500/40';

  return (
    <div className="space-y-5">
      {/* Header & Horizon selector */}
      <div className={`rounded-xl border p-5 ${cardBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">
              What People Think? — <span className="text-blue-400">{cleanTicker}</span>
            </h2>
            <p className="text-xs opacity-70 mt-0.5">
              Live prediction markets (Polymarket), social discussions (Reddit), and company news combined into a horizon sentiment forecast for {companyName}.
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            {(['1W', '1M', '3M'] as const).map((h) => (
              <button
                key={h}
                type="button"
                onClick={() => setHorizon(h)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                  horizon === h
                    ? 'bg-blue-600 text-white border-blue-500'
                    : darkMode
                    ? 'bg-slate-950 border-slate-700 text-slate-300 hover:border-slate-500'
                    : 'bg-slate-100 border-slate-300 text-slate-700'
                }`}
              >
                {h === '1W' ? '1 Week' : h === '1M' ? '1 Month' : '3 Months'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && (
        <div className={`rounded-xl border p-8 text-center text-sm opacity-75 ${cardBg}`}>
          Scanning Polymarket prediction contracts, Reddit discussions, and news feeds for {cleanTicker}...
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-300">
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* Verdict & Model Prediction Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className={`rounded-xl border p-5 flex flex-col justify-between ${cardBg}`}>
              <div className="text-xs uppercase tracking-wider opacity-60">Crowd Verdict ({data.horizon})</div>
              <div className="mt-2 flex items-center gap-3">
                <span className={`px-3 py-1 rounded-full text-sm font-bold border ${verdictStyle}`}>
                  {data.verdict}
                </span>
                <span className="text-2xl font-bold font-mono">
                  {data.crowd_score >= 0 ? '+' : ''}
                  {data.crowd_score.toFixed(1)}
                  <span className="text-xs opacity-60 font-normal"> / 100</span>
                </span>
              </div>
              <div className="mt-2 text-xs opacity-70">
                Positive Outlook Probability:{' '}
                <span className="font-semibold text-blue-400">
                  {(data.predicted_positive_probability * 100).toFixed(1)}%
                </span>
              </div>
            </div>

            <div className={`rounded-xl border p-5 md:col-span-2 ${cardBg}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs uppercase tracking-wider opacity-60">{data.model_name}</div>
                <div className="flex flex-wrap gap-1.5">
                  {data.live_sources_connected.map((src) => (
                    <span
                      key={src}
                      className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/15 text-blue-300 border border-blue-500/30"
                    >
                      {src}
                    </span>
                  ))}
                </div>
              </div>
              <p className="text-sm mt-2 leading-relaxed opacity-90">{data.model_summary}</p>
              <div className="grid grid-cols-3 gap-3 mt-3 pt-3 border-t border-slate-800/70 text-xs">
                <div>
                  <div className="opacity-60">Polymarket Tilt</div>
                  <div className="font-mono font-semibold mt-0.5">
                    {data.component_scores.polymarket_tilt_pct >= 0 ? '+' : ''}
                    {data.component_scores.polymarket_tilt_pct}%
                  </div>
                </div>
                <div>
                  <div className="opacity-60">Social & News Polarity</div>
                  <div className="font-mono font-semibold mt-0.5">
                    {data.component_scores.social_news_polarity_pct >= 0 ? '+' : ''}
                    {data.component_scores.social_news_polarity_pct}%
                  </div>
                </div>
                <div>
                  <div className="opacity-60">20D Momentum Confirm</div>
                  <div className="font-mono font-semibold mt-0.5">
                    {data.component_scores.price_momentum_confirmation_pct >= 0 ? '+' : ''}
                    {data.component_scores.price_momentum_confirmation_pct}%
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Polymarket Prediction Markets */}
          <div className={`rounded-xl border p-5 ${cardBg}`}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold">Prediction Markets (Polymarket)</h3>
                <p className="text-xs opacity-65">
                  Real-money event probabilities reflecting what traders are betting on for {cleanTicker} and macro catalysts.
                </p>
              </div>
              <a
                href={`https://polymarket.com/markets?_q=${encodeURIComponent(cleanTicker)}`}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-400 hover:underline"
              >
                Explore on Polymarket →
              </a>
            </div>
            {data.polymarket_contracts.length === 0 ? (
              <div className="text-xs opacity-70 py-3">
                No active Polymarket contracts returned in this session (check internet connection or search directly on Polymarket).
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {data.polymarket_contracts.map((c, idx) => (
                  <a
                    key={idx}
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className={`block rounded-lg border p-3.5 transition ${
                      darkMode
                        ? 'bg-slate-950/70 border-slate-800 hover:border-blue-500/60'
                        : 'bg-slate-50 border-slate-200 hover:border-blue-400'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="text-xs font-medium leading-snug">{c.title}</div>
                      <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                        {c.relevance === 'direct_company' ? 'Direct' : 'Macro'}
                      </span>
                    </div>
                    <div className="mt-2.5 flex items-center gap-2 text-xs font-mono">
                      <span className="text-emerald-400 font-semibold">
                        YES {(c.yes_probability * 100).toFixed(0)}%
                      </span>
                      <div className="flex-1 h-2 rounded-full bg-rose-500/30 overflow-hidden">
                        <div
                          className="h-full bg-emerald-500"
                          style={{ width: `${Math.round(c.yes_probability * 100)}%` }}
                        />
                      </div>
                      <span className="text-rose-400 font-semibold">
                        NO {(c.no_probability * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[10px] opacity-65">
                      <span>Volume: ${c.volume_usd.toLocaleString()}</span>
                      {c.end_date && <span>Resolves: {c.end_date}</span>}
                    </div>
                  </a>
                ))}
              </div>
            )}
          </div>

          {/* Live Social & News Stream */}
          <div className={`rounded-xl border p-5 ${cardBg}`}>
            <h3 className="text-sm font-semibold mb-3">Live Social & News Pulse (Reddit & Market Wire)</h3>
            {data.social_posts.length === 0 ? (
              <div className="text-xs opacity-70 py-2">
                No recent public Reddit or news posts returned in this session.
              </div>
            ) : (
              <div className="divide-y divide-slate-800/60">
                {data.social_posts.map((post, i) => (
                  <a
                    key={i}
                    href={post.url}
                    target="_blank"
                    rel="noreferrer"
                    className="py-2.5 flex items-start justify-between gap-3 hover:opacity-100 opacity-90 transition"
                  >
                    <div className="min-w-0">
                      <div className="text-xs font-medium hover:text-blue-400">{post.title}</div>
                      <div className="text-[10px] opacity-60 mt-0.5">
                        {post.platform} · {post.source_channel} · {post.published_at}
                        {post.engagement > 0 ? ` · ▲ ${post.engagement}` : ''}
                      </div>
                    </div>
                    <span
                      className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                        post.label === 'POSITIVE'
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          : post.label === 'NEGATIVE'
                          ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                          : 'bg-slate-700/40 text-slate-300 border-slate-600/40'
                      }`}
                    >
                      {post.label}
                    </span>
                  </a>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
