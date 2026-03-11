'use client';

import { useSkillLevel } from '@/hooks/useSkillLevel';

const BENCHMARKS = {
  novice: { label: 'Novice', min: 40, max: 55 },
  intermediate: { label: 'Intermediate', min: 60, max: 75 },
  advanced: { label: 'Advanced', min: 78, max: 90 },
  instructor: { label: 'Instructor', min: 88, max: 100 },
} as const;

type BenchmarkLevel = keyof typeof BENCHMARKS;

const LEVEL_ORDER: BenchmarkLevel[] = ['novice', 'intermediate', 'advanced', 'instructor'];

function getNextLevel(current: string): BenchmarkLevel | null {
  const idx = LEVEL_ORDER.indexOf(current as BenchmarkLevel);
  if (idx === -1 || idx >= LEVEL_ORDER.length - 1) return null;
  return LEVEL_ORDER[idx + 1];
}

interface ConsistencyBenchmarkProps {
  score: number;
  /** Compact mode: single line for MetricsGrid subtitle */
  compact?: boolean;
}

/**
 * Shows how a driver's consistency score compares to typical ranges
 * for their skill level + what's needed for the next level.
 */
export function ConsistencyBenchmark({ score, compact = false }: ConsistencyBenchmarkProps) {
  const { skillLevel } = useSkillLevel();
  const currentBench = BENCHMARKS[skillLevel as BenchmarkLevel] ?? BENCHMARKS.intermediate;
  const nextLevelKey = getNextLevel(skillLevel);
  const nextBench = nextLevelKey ? BENCHMARKS[nextLevelKey] : null;

  const inRange = score >= currentBench.min && score <= currentBench.max;
  const aboveRange = score > currentBench.max;

  if (compact) {
    if (aboveRange && nextBench) {
      return (
        <span className="text-[var(--color-throttle)]">
          Above {currentBench.label} range ({currentBench.min}–{currentBench.max})
        </span>
      );
    }
    if (inRange) {
      return (
        <span className="text-[var(--text-secondary)]">
          On target for {currentBench.label} ({currentBench.min}–{currentBench.max})
        </span>
      );
    }
    const gap = currentBench.min - score;
    return (
      <span className="text-[var(--text-secondary)]">
        {gap > 0 ? `+${Math.ceil(gap)} pts to ${currentBench.label} range` : `${currentBench.label} range: ${currentBench.min}–${currentBench.max}`}
      </span>
    );
  }

  // Full display (for DebriefHeroCard)
  return (
    <div className="flex flex-col items-center gap-0.5">
      <p className="text-[10px] text-[var(--text-secondary)]">
        {currentBench.label}: {currentBench.min}–{currentBench.max}
        {inRange && ' ✓'}
      </p>
      {nextBench && (
        <p className="text-[10px] text-[var(--text-secondary)]">
          {score >= nextBench.min ? (
            <span className="text-[var(--color-throttle)]">At {nextBench.label} level!</span>
          ) : (
            <>Next ({nextBench.label}): {nextBench.min}+</>
          )}
        </p>
      )}
    </div>
  );
}
