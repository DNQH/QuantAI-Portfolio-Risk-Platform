import React, { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import type { OHLCVBar } from '../types/market';

interface Props {
  bars: OHLCVBar[];
}

export const CandlestickChart: React.FC<Props> = ({ bars }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || bars.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#131822' },
        textColor: '#94A3B8',
      },
      grid: {
        vertLines: { color: '#1E293B' },
        horzLines: { color: '#1E293B' },
      },
      width: containerRef.current.clientWidth,
      height: 360,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10B981',
      downColor: '#EF4444',
      borderVisible: false,
      wickUpColor: '#10B981',
      wickDownColor: '#EF4444',
    });

    candleSeries.setData(
      bars.map((b) => ({
        time: b.timestamp.slice(0, 10),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }))
    );

    chart.timeScale().fitContent();

    const onResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      chart.remove();
    };
  }, [bars]);

  if (bars.length === 0) {
    return (
      <div className="flex h-[360px] items-center justify-center rounded-lg border border-terminal-border bg-terminal-bg text-sm text-slate-400">
        No verified historical OHLCV bars available for the selected instrument and date range.
      </div>
    );
  }

  return <div ref={containerRef} className="w-full overflow-hidden rounded-lg" />;
};
