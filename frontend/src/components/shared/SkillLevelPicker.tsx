'use client';

import { useCallback } from 'react';
import { motion } from 'motion/react';
import { useUiStore } from '@/stores';
import { updateUserProfile } from '@/lib/api';
import type { SkillLevel } from '@/stores/uiStore';

const SKILL_OPTIONS: {
  label: string;
  value: SkillLevel;
  colorClass: string;
  borderClass: string;
  bgClass: string;
}[] = [
  {
    label: 'Less than 5',
    value: 'novice',
    colorClass: 'text-emerald-400',
    borderClass: 'border-emerald-500/40 hover:border-emerald-400',
    bgClass: 'bg-emerald-500/10 hover:bg-emerald-500/20',
  },
  {
    label: '5 \u2013 20',
    value: 'intermediate',
    colorClass: 'text-amber-400',
    borderClass: 'border-amber-500/40 hover:border-amber-400',
    bgClass: 'bg-amber-500/10 hover:bg-amber-500/20',
  },
  {
    label: 'More than 20',
    value: 'advanced',
    colorClass: 'text-red-400',
    borderClass: 'border-red-500/40 hover:border-red-400',
    bgClass: 'bg-red-500/10 hover:bg-red-500/20',
  },
];

/** Returns true if the skill picker has not yet been shown to this user. */
export function shouldShowSkillPicker(): boolean {
  if (typeof window === 'undefined') return false;
  return !localStorage.getItem('cataclysm-skill-level-set');
}

interface SkillLevelPickerProps {
  onComplete: () => void;
}

export function SkillLevelPicker({ onComplete }: SkillLevelPickerProps) {
  const setSkillLevel = useUiStore((s) => s.setSkillLevel);

  const handleSelect = useCallback(
    (level: SkillLevel) => {
      setSkillLevel(level);
      localStorage.setItem('cataclysm-skill-level-set', '1');
      // Fire-and-forget PATCH to persist server-side
      updateUserProfile({ skill_level: level }).catch(() => {});
      onComplete();
    },
    [setSkillLevel, onComplete],
  );

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      role="dialog"
      aria-modal="true"
      aria-label="Skill level selection"
    >
      <motion.div
        className="mx-4 w-full max-w-sm rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 shadow-2xl"
        initial={{ opacity: 0, y: 24, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.35, delay: 0.05, ease: 'easeOut' }}
      >
        <h2 className="text-center font-[family-name:var(--font-display)] text-lg font-bold text-[var(--text-primary)]">
          How many trackdays have you done?
        </h2>
        <p className="mt-2 text-center text-sm text-[var(--text-secondary)]">
          This adjusts your coaching and which features we show you.
        </p>

        <div className="mt-6 flex flex-col gap-3">
          {SKILL_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => handleSelect(opt.value)}
              className={`min-h-[56px] w-full rounded-lg border px-4 py-3 text-base font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cata-accent)] ${opt.colorClass} ${opt.borderClass} ${opt.bgClass}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}
