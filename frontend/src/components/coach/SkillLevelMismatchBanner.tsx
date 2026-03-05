'use client';

import { AlertTriangle } from 'lucide-react';

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

interface SkillLevelMismatchBannerProps {
  reportLevel: string;
  currentLevel: string;
  onRegenerate: () => void;
}

export function SkillLevelMismatchBanner({
  reportLevel,
  currentLevel,
  onRegenerate,
}: SkillLevelMismatchBannerProps) {
  return (
    <div className="mx-4 mb-2 flex items-start gap-2 rounded-md bg-amber-500/10 border border-amber-500/30 px-3 py-2">
      <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-amber-400 leading-relaxed">
          This report was generated for{' '}
          <span className="font-medium">{capitalize(reportLevel)}</span>.
          Your current level is{' '}
          <span className="font-medium">{capitalize(currentLevel)}</span>.
        </p>
        <button
          onClick={onRegenerate}
          className="mt-1 text-xs font-medium text-amber-400 hover:text-amber-300 underline underline-offset-2 transition-colors"
        >
          Regenerate Report
        </button>
      </div>
    </div>
  );
}
