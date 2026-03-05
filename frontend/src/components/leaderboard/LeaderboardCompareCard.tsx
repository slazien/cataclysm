'use client';

import { X } from 'lucide-react';
import { useUnits } from '@/hooks/useUnits';
import { MPS_TO_MPH } from '@/lib/constants';
import type { CornerRecordEntry } from '@/lib/types';

interface LeaderboardCompareCardProps {
  yourEntry: CornerRecordEntry;
  theirEntry: CornerRecordEntry;
  cornerNumber: number;
  onClose: () => void;
}

function formatTime(seconds: number): string {
  return seconds.toFixed(3) + 's';
}

interface CompareRowProps {
  label: string;
  yours: string;
  theirs: string;
  /** Positive means you are better (lower is better for time, higher is better for speed) */
  advantage: number;
}

function CompareRow({ label, yours, theirs, advantage }: CompareRowProps) {
  const isYourAdvantage = advantage > 0;
  const isTheirAdvantage = advantage < 0;

  return (
    <div className="grid grid-cols-3 items-center gap-2 py-2">
      <span
        className={`text-right text-sm font-mono tabular-nums ${
          isYourAdvantage ? 'text-emerald-400 font-semibold' : 'text-[var(--text-primary)]'
        }`}
      >
        {yours}
      </span>
      <span className="text-center text-xs text-[var(--text-muted)]">{label}</span>
      <span
        className={`text-left text-sm font-mono tabular-nums ${
          isTheirAdvantage ? 'text-emerald-400 font-semibold' : 'text-[var(--text-primary)]'
        }`}
      >
        {theirs}
      </span>
    </div>
  );
}

export function LeaderboardCompareCard({
  yourEntry,
  theirEntry,
  cornerNumber,
  onClose,
}: LeaderboardCompareCardProps) {
  const { formatSpeed } = useUnits();
  const fmtSpd = (mps: number) => formatSpeed(mps * MPS_TO_MPH);
  // Time: lower is better, so advantage = their - yours (positive = you're faster)
  const timeAdvantage = theirEntry.sector_time_s - yourEntry.sector_time_s;
  // Speed: higher is better, so advantage = yours - theirs (positive = you're faster)
  const speedAdvantage = yourEntry.min_speed_mps - theirEntry.min_speed_mps;

  return (
    <div className="absolute inset-x-2 top-2 z-10 rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4 shadow-xl">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="font-[family-name:var(--font-display)] text-sm font-semibold text-[var(--text-primary)]">
          Corner {cornerNumber} Comparison
        </h4>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full p-1 text-[var(--text-muted)] transition hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-3 gap-2 border-b border-[var(--cata-border)] pb-1.5">
        <span className="text-right text-[10px] font-medium uppercase tracking-wider text-[var(--cata-accent)]">
          You
        </span>
        <span className="text-center text-[10px] text-[var(--text-muted)]">vs</span>
        <span className="text-left text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          {theirEntry.user_name}
        </span>
      </div>

      <div className="divide-y divide-[var(--cata-border)]/30">
        <CompareRow
          label="Sector Time"
          yours={formatTime(yourEntry.sector_time_s)}
          theirs={formatTime(theirEntry.sector_time_s)}
          advantage={timeAdvantage}
        />
        <CompareRow
          label="Min Speed"
          yours={fmtSpd(yourEntry.min_speed_mps)}
          theirs={fmtSpd(theirEntry.min_speed_mps)}
          advantage={speedAdvantage}
        />
      </div>

      {/* Delta summary */}
      <div className="mt-2 rounded-lg bg-[var(--bg-elevated)] p-2 text-center">
        {timeAdvantage > 0 ? (
          <span className="text-xs font-medium text-emerald-400">
            You are {timeAdvantage.toFixed(3)}s faster
          </span>
        ) : timeAdvantage < 0 ? (
          <span className="text-xs font-medium text-red-400">
            They are {Math.abs(timeAdvantage).toFixed(3)}s faster
          </span>
        ) : (
          <span className="text-xs font-medium text-[var(--text-muted)]">
            Identical times
          </span>
        )}
      </div>
    </div>
  );
}
