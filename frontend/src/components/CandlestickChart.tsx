import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, type UTCTimestamp } from 'lightweight-charts';
import type { OHLCVBar } from '../types/market';

interface Props {
  bars: OHLCVBar[];
  interval?: string;
}

const INTRADAY_INTERVALS = new Set(['1m', '2m', '5m', '15m', '30m', '60m', '1h']);

export const CandlestickChart: React.FC<Props> = ({ bars, interval = '1d' }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || bars.length === 0) return;

    const isIntraday = INTRADAY_INTERVALS.has(interval.toLowerCase());

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#131822' },
        textColor: '#94A3B8',
      },
      grid: {
        vertLines: { color: '#1E293B' },
        horzLines: { color: '#1E293B' },
      },
      timeScale: {
        timeVisible: isIntraday,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height: 400,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10B981',
      downColor: '#EF4444',
      borderVisible: false,
      wickUpColor: '#10B981',
      wickDownColor: '#EF4444',
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    const seen = new Set<string | number>();
    const candleData: Array<{
      time: string | UTCTimestamp;
      open: number;
      high: number;
      low: number;
      close: number;
    }> = [];
    const volData: Array<{
      time: string | UTCTimestamp;
      value: number;
      color: string;
    }> = [];

    for (const b of bars) {
      const t: string | UTCTimestamp = isIntraday
        ? (Math.floor(new Date(b.timestamp).getTime() / 1000) as UTCTimestamp)
        : b.timestamp.slice(0, 10);
      if (seen.has(t)) continue;
      seen.add(t);
      candleData.push({ time: t, open: b.open, high: b.high, low: b.low, close: b.close });
      volData.push({
        time: t,
        value: b.volume,
        color: b.close >= b.open ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)',
      });
    }

    candleSeries.setData(candleData as never);
    volumeSeries.setData(volData as never);
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
  }, [bars, interval]);

  if (bars.length === 0) {
    return (
      <div className="flex h-[400px] items-center justify-center rounded-lg border border-terminal-border bg-terminal-bg text-sm text-slate-400">
        No verified OHLCV bars available for the selected instrument and interval.
      </div>
    );
  }

  return <div ref={containerRef} className="w-full overflow-hidden rounded-lg" />;
};
