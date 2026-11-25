import React, { useEffect, useRef, useState } from 'react';

export interface MarketSelection {
  country: string; // 'ALL' or country name
  exchangeMic: string; // 'ALL' or specific MIC: 'XNYS', 'XNAS', 'XSTC', 'XHAI', 'XUPC', 'XMIL'
  label: string;
}

interface ExchangeOption {
  mic: string;
  code: string;
  name: string;
}

interface CountryGroup {
  country: string;
  label: string;
  exchanges: ExchangeOption[];
}

export const COUNTRY_EXCHANGE_TREE: CountryGroup[] = [
  {
    country: 'United States',
    label: 'United States',
    exchanges: [
      { mic: 'XNYS', code: 'NYSE', name: 'New York Stock Exchange' },
      { mic: 'XNAS', code: 'NASDAQ', name: 'NASDAQ Stock Market' },
    ],
  },
  {
    country: 'Vietnam',
    label: 'Vietnam',
    exchanges: [
      { mic: 'XSTC', code: 'HOSE', name: 'Ho Chi Minh Stock Exchange' },
      { mic: 'XHAI', code: 'HNX', name: 'Hanoi Stock Exchange' },
      { mic: 'XUPC', code: 'UPCOM', name: 'Vietnam UPCoM Market' },
    ],
  },
  {
    country: 'Italy',
    label: 'Italy',
    exchanges: [{ mic: 'XMIL', code: 'Borsa Italiana', name: 'Borsa Italiana (Euronext Milan)' }],
  },
];

interface Props {
  value: MarketSelection;
  onChange: (sel: MarketSelection) => void;
  darkMode: boolean;
}

export const MarketSelectorDropdown: React.FC<Props> = ({ value, onChange, darkMode }) => {
  const [open, setOpen] = useState(false);
  const [hoveredCountry, setHoveredCountry] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setHoveredCountry(null);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const panelBg = darkMode
    ? 'bg-slate-900 border-slate-700 text-slate-100'
    : 'bg-white border-slate-200 text-slate-900';
  const itemHover = darkMode ? 'hover:bg-blue-600/25' : 'hover:bg-blue-50';

  const activeGroup = COUNTRY_EXCHANGE_TREE.find((g) => g.country === hoveredCountry);

  return (
    <div ref={containerRef} className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
          darkMode
            ? 'bg-slate-900 border-slate-700 text-slate-100 hover:border-blue-500'
            : 'bg-white border-slate-300 text-slate-800 hover:border-blue-500'
        }`}
      >
        <span>{value.label}</span>
        <span className="opacity-60 text-[10px]">▾</span>
      </button>

      {open && (
        <div
          className={`absolute right-0 mt-1.5 z-50 flex rounded-xl border shadow-2xl ${panelBg}`}
          onMouseLeave={() => setHoveredCountry(null)}
        >
          {/* Left column: Countries */}
          <div className="w-48 py-1.5 max-h-96 overflow-y-auto">
            <button
              type="button"
              onMouseEnter={() => setHoveredCountry(null)}
              onClick={() => {
                onChange({ country: 'ALL', exchangeMic: 'ALL', label: 'All Markets' });
                setOpen(false);
              }}
              className={`w-full text-left px-3 py-1.5 text-xs flex items-center justify-between ${itemHover} ${
                value.country === 'ALL' ? 'text-blue-400 font-semibold' : ''
              }`}
            >
              <span>All Markets</span>
              {value.country === 'ALL' && <span>✓</span>}
            </button>
            <div className="my-1 border-t border-slate-800/60" />
            {COUNTRY_EXCHANGE_TREE.map((group) => {
              const isSelected = value.country === group.country;
              const isHovered = hoveredCountry === group.country;
              return (
                <button
                  key={group.country}
                  type="button"
                  onMouseEnter={() => setHoveredCountry(group.country)}
                  onClick={() => {
                    onChange({
                      country: group.country,
                      exchangeMic: 'ALL',
                      label: group.label,
                    });
                    setOpen(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 text-xs flex items-center justify-between transition ${
                    isHovered
                      ? 'bg-blue-600/30 text-blue-300'
                      : isSelected
                      ? 'text-blue-400 font-semibold'
                      : ''
                  } ${itemHover}`}
                >
                  <span>{group.label}</span>
                  <span className="text-[10px] opacity-60">▸</span>
                </button>
              );
            })}
          </div>

          {/* Right flyout column: Exchanges for hovered country */}
          {activeGroup && (
            <div
              className={`w-56 border-l py-1.5 px-1.5 ${
                darkMode ? 'border-slate-800 bg-slate-950/95' : 'border-slate-200 bg-slate-50'
              } rounded-r-xl`}
            >
              <div className="px-2.5 py-1 text-[10px] uppercase tracking-wider opacity-60 font-semibold">
                {activeGroup.label} Exchanges
              </div>
              <button
                type="button"
                onClick={() => {
                  onChange({
                    country: activeGroup.country,
                    exchangeMic: 'ALL',
                    label: `${activeGroup.label} (All)`,
                  });
                  setOpen(false);
                }}
                className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs ${itemHover} flex items-center justify-between`}
              >
                <span className="font-medium">All {activeGroup.label}</span>
                {value.country === activeGroup.country && value.exchangeMic === 'ALL' && (
                  <span className="text-blue-400">✓</span>
                )}
              </button>
              {activeGroup.exchanges.map((ex) => {
                const active = value.exchangeMic === ex.mic;
                return (
                  <button
                    key={ex.mic}
                    type="button"
                    onClick={() => {
                      onChange({
                        country: activeGroup.country,
                        exchangeMic: ex.mic,
                        label: `${activeGroup.label} · ${ex.code}`,
                      });
                      setOpen(false);
                    }}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs mt-0.5 transition ${itemHover} ${
                      active ? 'bg-blue-600/20 text-blue-400 font-semibold' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">{ex.code}</span>
                      {active && <span>✓</span>}
                    </div>
                    <div className="text-[10px] opacity-60 truncate">{ex.name}</div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
