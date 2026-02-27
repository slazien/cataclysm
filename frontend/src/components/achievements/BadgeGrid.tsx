'use client';

import { X, Trophy, Flame, Target, Zap, Wind, MapPin, Repeat, Lock } from 'lucide-react';
import { useAchievements } from '@/hooks/useAchievements';
import type { Achievement } from '@/lib/types';

const TIER_COLORS: Record<string, string> = {
  bronze: '#cd7f32',
  silver: '#c0c0c0',
  gold: '#ffd700',
};

const ICON_MAP: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  trophy: Trophy,
  flame: Flame,
  target: Target,
  zap: Zap,
  wind: Wind,
  'map-pin': MapPin,
  repeat: Repeat,
};

function AchievementBadge({ achievement }: { achievement: Achievement }) {
  const Icon = ICON_MAP[achievement.icon] ?? Trophy;
  const color = TIER_COLORS[achievement.tier] ?? '#c0c0c0';

  return (
    <div
      className={`flex flex-col items-center gap-2 rounded-xl p-4 transition ${
        achievement.unlocked
          ? 'bg-[var(--bg-elevated)]'
          : 'bg-[var(--bg-surface)] opacity-40 grayscale'
      }`}
    >
      <div
        className="flex h-12 w-12 items-center justify-center rounded-full border-2"
        style={{
          borderColor: achievement.unlocked ? color : 'var(--cata-border)',
          backgroundColor: achievement.unlocked ? `${color}15` : 'transparent',
        }}
      >
        {achievement.unlocked ? (
          <Icon className="h-6 w-6" style={{ color }} />
        ) : (
          <Lock className="h-5 w-5 text-[var(--text-muted)]" />
        )}
      </div>
      <span className="text-center text-xs font-medium text-[var(--text-primary)]">
        {achievement.name}
      </span>
      <span className="text-center text-[10px] text-[var(--text-muted)]">
        {achievement.description}
      </span>
      {achievement.unlocked && achievement.unlocked_at && (
        <span className="text-[10px] text-[var(--text-muted)]">
          {new Date(achievement.unlocked_at).toLocaleDateString()}
        </span>
      )}
    </div>
  );
}

interface BadgeGridProps {
  open: boolean;
  onClose: () => void;
}

export function BadgeGrid({ open, onClose }: BadgeGridProps) {
  const { data, isLoading } = useAchievements(open);

  if (!open) return null;

  const unlocked = data?.achievements.filter((a) => a.unlocked).length ?? 0;
  const total = data?.achievements.length ?? 0;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-[min(90vw,480px)] max-h-[80vh] overflow-y-auto rounded-2xl bg-[var(--bg-surface)] p-6 shadow-2xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 rounded-full bg-black/40 p-1.5 text-white/70 hover:bg-black/60"
        >
          <X className="h-4 w-4" />
        </button>

        <h2 className="mb-1 text-xl font-semibold text-[var(--text-primary)]">Achievements</h2>
        <p className="mb-4 text-sm text-[var(--text-muted)]">
          {unlocked} / {total} unlocked
        </p>

        {isLoading && (
          <div className="flex justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--cata-accent)] border-t-transparent" />
          </div>
        )}

        {data && (
          <div className="grid grid-cols-3 gap-3">
            {data.achievements.map((a) => (
              <AchievementBadge key={a.id} achievement={a} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
