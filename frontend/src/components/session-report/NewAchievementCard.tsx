'use client';

import { Award } from 'lucide-react';
import type { Achievement } from '@/lib/types';

interface NewAchievementCardProps {
  achievements: Achievement[];
  onViewAll: () => void;
}

export function NewAchievementCard({ achievements, onViewAll }: NewAchievementCardProps) {
  if (achievements.length === 0) return null;

  const latest = achievements[0];
  const tierColor =
    latest.tier === 'gold'
      ? 'text-yellow-400'
      : latest.tier === 'silver'
        ? 'text-gray-300'
        : 'text-amber-600';

  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      <div className="mb-2 flex items-center gap-2">
        <Award className={`h-5 w-5 ${tierColor}`} />
        <h3 className="font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-primary)]">
          New Achievement{achievements.length > 1 ? 's' : ''}
        </h3>
      </div>
      <p className="text-sm font-semibold text-[var(--text-primary)]">{latest.name}</p>
      <p className="text-xs text-[var(--text-secondary)]">{latest.description}</p>
      {achievements.length > 1 && (
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          +{achievements.length - 1} more
        </p>
      )}
      <button
        type="button"
        onClick={onViewAll}
        className="mt-2 text-xs font-medium text-[var(--cata-accent)] hover:underline"
      >
        View All Badges
      </button>
    </div>
  );
}
