'use client';

import { Lightbulb } from 'lucide-react';

interface QuickTipProps {
  drill: string;
}

export function QuickTip({ drill }: QuickTipProps) {
  return (
    <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4">
      <div className="flex items-start gap-3">
        <Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-indigo-400" />
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-indigo-400">
            Quick Drill
          </h3>
          <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{drill}</p>
        </div>
      </div>
    </div>
  );
}
