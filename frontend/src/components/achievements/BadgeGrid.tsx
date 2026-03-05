'use client';

import { useMemo } from 'react';
import { motion as m } from 'motion/react';
import {
  X, Trophy, Flame, Target, Zap, Wind, MapPin, Repeat, Lock, Award,
  Calendar, Crown, Layers, Hash, Infinity, Gauge, Crosshair, Sparkles,
  Compass, Globe,
} from 'lucide-react';
import { useAchievements } from '@/hooks/useAchievements';
import { motion as motionTokens } from '@/lib/design-tokens';
import type { Achievement } from '@/lib/types';

const TIER_COLORS: Record<string, string> = {
  bronze: '#cd7f32',
  silver: '#c0c0c0',
  gold: '#ffd700',
  platinum: '#00e5ff',
};

const ICON_MAP: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  trophy: Trophy,
  flame: Flame,
  target: Target,
  zap: Zap,
  wind: Wind,
  'map-pin': MapPin,
  repeat: Repeat,
  award: Award,
  calendar: Calendar,
  crown: Crown,
  layers: Layers,
  hash: Hash,
  infinity: Infinity,
  gauge: Gauge,
  crosshair: Crosshair,
  sparkles: Sparkles,
  compass: Compass,
  globe: Globe,
};

const CATEGORY_LABELS: Record<string, string> = {
  milestones: 'Milestones',
  laps: 'Lap Count',
  consistency: 'Consistency',
  braking: 'Braking',
  trail_braking: 'Trail Braking',
  exploration: 'Exploration',
};

const CATEGORY_ORDER = ['milestones', 'laps', 'consistency', 'braking', 'trail_braking', 'exploration'];

const badgeVariants = {
  initial: { opacity: 0, scale: 0.8 },
  animate: { opacity: 1, scale: 1 },
};

function AchievementBadge({ achievement }: { achievement: Achievement }) {
  const Icon = ICON_MAP[achievement.icon] ?? Trophy;
  const color = TIER_COLORS[achievement.tier] ?? '#c0c0c0';

  return (
    <m.div
      variants={badgeVariants}
      transition={motionTokens.cardEntrance}
      className={`flex flex-col items-center gap-2 rounded-xl p-4 transition ${
        achievement.unlocked
          ? 'bg-[var(--bg-elevated)]'
          : 'bg-[var(--bg-surface)] opacity-40 grayscale'
      }`}
    >
      <div
        className="relative flex h-12 w-12 items-center justify-center rounded-full border-2"
        style={{
          borderColor: achievement.unlocked ? color : 'var(--cata-border)',
          backgroundColor: achievement.unlocked ? `${color}15` : 'transparent',
        }}
      >
        {achievement.unlocked ? (
          <Icon className="h-6 w-6" style={{ color }} />
        ) : (
          <Lock className="h-5 w-5 text-[var(--text-secondary)]" />
        )}
        {achievement.tier === 'platinum' && achievement.unlocked && (
          <div
            className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full text-[8px] font-bold"
            style={{ backgroundColor: color, color: '#0a0a0f' }}
          >
            P
          </div>
        )}
      </div>
      <span className="text-center text-xs font-medium text-[var(--text-primary)]">
        {achievement.name}
      </span>
      <span className="text-center text-[10px] text-[var(--text-secondary)]">
        {achievement.description}
      </span>
      {achievement.unlocked && achievement.unlocked_at && (
        <span className="text-[10px] text-[var(--text-muted)]">
          {new Date(achievement.unlocked_at).toLocaleDateString()}
        </span>
      )}
    </m.div>
  );
}

function CategorySection({
  category,
  achievements,
}: {
  category: string;
  achievements: Achievement[];
}) {
  const unlocked = achievements.filter((a) => a.unlocked).length;
  const label = CATEGORY_LABELS[category] ?? category;

  return (
    <div className="mb-4 last:mb-0">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          {label}
        </h3>
        <span className="text-xs tabular-nums text-[var(--text-secondary)]">
          {unlocked}/{achievements.length}
        </span>
      </div>
      <m.div
        className="grid grid-cols-3 gap-3"
        initial="initial"
        animate="animate"
        variants={{ animate: { transition: motionTokens.stagger } }}
      >
        {achievements.map((a) => (
          <AchievementBadge key={a.id} achievement={a} />
        ))}
      </m.div>
    </div>
  );
}

interface BadgeGridProps {
  open: boolean;
  onClose: () => void;
}

export function BadgeGrid({ open, onClose }: BadgeGridProps) {
  const { data, isLoading, isError, refetch } = useAchievements(open);

  const grouped = useMemo(() => {
    if (!data?.achievements) return [];
    const map = new Map<string, Achievement[]>();
    for (const a of data.achievements) {
      const cat = a.category ?? 'milestones';
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(a);
    }
    return CATEGORY_ORDER
      .filter((cat) => map.has(cat))
      .map((cat) => ({ category: cat, achievements: map.get(cat)! }));
  }, [data]);

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
      <div className="flex w-[min(90vw,520px)] max-h-[85vh] flex-col rounded-2xl bg-[var(--bg-surface)] shadow-2xl">
        {/* Sticky header — stays visible when scrolling */}
        <div className="flex items-start justify-between px-6 pt-6 pb-2">
          <div className="flex-1">
            <h2 className="mb-1 text-xl font-semibold text-[var(--text-primary)]">Achievements</h2>
            <div className="flex items-center gap-3">
              <p className="text-sm text-[var(--text-secondary)]">
                {unlocked} / {total} unlocked
              </p>
              <div className="h-1.5 flex-1 rounded-full bg-[var(--bg-elevated)]">
                <div
                  className="h-full rounded-full bg-[var(--cata-accent)] transition-all duration-500"
                  style={{ width: total > 0 ? `${(unlocked / total) * 100}%` : '0%' }}
                />
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ml-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-black/40 text-white/70 hover:bg-black/60"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto px-6 pb-6">
          {isLoading && (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--cata-accent)] border-t-transparent" />
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <p className="text-sm text-[var(--text-secondary)]">
                Couldn&apos;t load achievements
              </p>
              <button
                type="button"
                onClick={() => refetch()}
                className="rounded-lg bg-[var(--bg-elevated)] px-4 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--cata-border)]"
              >
                Tap to retry
              </button>
            </div>
          )}

          {data && grouped.map(({ category, achievements }) => (
            <CategorySection key={category} category={category} achievements={achievements} />
          ))}
        </div>
      </div>
    </div>
  );
}
