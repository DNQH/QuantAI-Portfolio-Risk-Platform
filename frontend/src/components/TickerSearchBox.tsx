import React, { useEffect, useRef, useState } from 'react';
import { quantApi } from '../services/api';
import type { Instrument } from '../types/market';

interface Props {
  onSelect: (instrument: Instrument) => void;
  placeholder?: string;
  country?: string;
  exchangeMic?: string;
  darkMode: boolean;
  className?: string;
}

export const TickerSearchBox: React.FC<Props> = ({
  onSelect,
  placeholder = 'Searching...',
  country,
  exchangeMic,
  darkMode,
  className = 'w-80',
}) => {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<Instrument[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    const timer = setTimeout(() => {
      setLoading(true);
      quantApi
        .searchInstruments({
          q: trimmed,
          country: country && country !== 'ALL' ? country : undefined,
          exchange: exchangeMic && exchangeMic !== 'ALL' ? exchangeMic : undefined,
        })
        .then((res) => {
          setSuggestions(res.slice(0, 12));
          setOpen(true);
        })
        .catch(() => setSuggestions([]))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(timer);
  }, [query, country, exchangeMic]);

  const handlePick = (inst: Instrument) => {
    onSelect(inst);
    setQuery('');
    setOpen(false);
  };

  return (
    <div ref={boxRef} className={`relative ${className}`}>
      <input
        type="text"
        value={query}
        onFocus={() => query.trim() && setOpen(true)}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && suggestions.length > 0) {
            e.preventDefault();
            handlePick(suggestions[0]);
          }
        }}
        placeholder={placeholder}
        className={`w-full rounded-lg border px-3 py-1.5 text-xs focus:border-blue-500 focus:outline-none ${
          darkMode
            ? 'bg-slate-900 border-slate-700 text-slate-100 placeholder-slate-500'
            : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
        }`}
      />

      {open && (
        <div
          className={`absolute right-0 left-0 mt-1.5 z-50 rounded-xl border shadow-2xl max-h-80 overflow-y-auto ${
            darkMode
              ? 'bg-slate-900 border-slate-700 text-slate-100'
              : 'bg-white border-slate-200 text-slate-900'
          }`}
        >
          {loading && (
            <div className="px-3 py-2 text-[11px] opacity-65">Searching global exchanges...</div>
          )}
          {!loading && suggestions.length === 0 && (
            <div className="px-3 py-2 text-[11px] opacity-65">
              No matching tickers found for &ldquo;{query}&rdquo;.
            </div>
          )}
          {!loading &&
            suggestions.map((inst) => (
              <button
                key={inst.instrument_id}
                type="button"
                onClick={() => handlePick(inst)}
                className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between gap-2 transition ${
                  darkMode ? 'hover:bg-blue-600/25' : 'hover:bg-blue-50'
                }`}
              >
                <div className="min-w-0">
                  <span className="font-mono font-bold text-blue-400">{inst.ticker}</span>
                  <span className="ml-2 opacity-80 truncate inline-block max-w-[180px] align-bottom">
                    {inst.company_name}
                  </span>
                </div>
                <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 font-mono">
                  {inst.exchange_acronym}
                </span>
              </button>
            ))}
        </div>
      )}
    </div>
  );
};
