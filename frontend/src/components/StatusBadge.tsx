import React from 'react';
import { en } from '../i18n/en';
import type { DataStatus } from '../types/market';

const STATUS_STYLES: Record<DataStatus, string> = {
  LIVE: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  DELAYED: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  HISTORICAL: 'bg-blue-500/15 text-blue-300 border-blue-500/40',
  DAILY_REFERENCE: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/40',
  DATA_UNAVAILABLE: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
};

export const StatusBadge: React.FC<{ status: DataStatus; delayMinutes?: number | null }> = ({
  status,
  delayMinutes,
}) => {
  const label = en.status[status] || status;
  const suffix =
    status === 'DELAYED' && typeof delayMinutes === 'number' && delayMinutes > 0
      ? ` (${delayMinutes}m)`
      : '';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-xs font-semibold ${STATUS_STYLES[status]}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === 'LIVE' ? 'bg-emerald-400' : 'bg-current opacity-80'
        }`}
      />
      {label}
      {suffix}
    </span>
  );
};
