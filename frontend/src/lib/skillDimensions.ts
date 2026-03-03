import type { CornerGrade } from './types';

const GRADE_SCORES: Record<string, number> = {
  A: 100,
  B: 80,
  C: 60,
  D: 40,
  F: 20,
};

export interface SkillDimensions {
  braking: number;
  trailBraking: number;
  throttle: number;
  line: number; // derived from min_speed grades
}

export const SKILL_AXES = ['Braking', 'Trail Braking', 'Throttle', 'Line'] as const;

function gradeToScore(grade: string): number {
  const letter = grade?.charAt(0)?.toUpperCase();
  return GRADE_SCORES[letter] ?? 50;
}

export function computeSkillDimensions(grades: CornerGrade[]): SkillDimensions | null {
  if (!grades || grades.length === 0) return null;

  let brakingSum = 0;
  let trailSum = 0;
  let throttleSum = 0;
  let lineSum = 0;

  for (const g of grades) {
    brakingSum += gradeToScore(g.braking);
    trailSum += gradeToScore(g.trail_braking);
    throttleSum += gradeToScore(g.throttle);
    lineSum += gradeToScore(g.min_speed);
  }

  const n = grades.length;
  return {
    braking: brakingSum / n,
    trailBraking: trailSum / n,
    throttle: throttleSum / n,
    line: lineSum / n,
  };
}

export function dimensionsToArray(dims: SkillDimensions): number[] {
  return [dims.braking, dims.trailBraking, dims.throttle, dims.line];
}

const IDENTITY_LABELS: Record<string, string[]> = {
  braking: ['LATE BRAKER', 'BRAKE BOSS'],
  trailBraking: ['TRAIL WIZARD', 'SMOOTH OPERATOR'],
  throttle: ['THROTTLE KING', 'POWER PLAYER'],
  line: ['LINE MASTER', 'APEX HUNTER'],
  balanced: ['COMPLETE DRIVER', 'WELL ROUNDED'],
};

/** Map skill dimensions to an identity label for share cards. */
export function getIdentityLabel(dims: SkillDimensions | null): string {
  if (!dims) return 'TRACK WARRIOR';

  const entries: [string, number][] = [
    ['braking', dims.braking],
    ['trailBraking', dims.trailBraking],
    ['throttle', dims.throttle],
    ['line', dims.line],
  ];
  const max = Math.max(...entries.map(([, v]) => v));
  const min = Math.min(...entries.map(([, v]) => v));

  // If all dimensions within 10 points, driver is balanced
  const key = max - min <= 10
    ? 'balanced'
    : entries.find(([, v]) => v === max)![0];

  const pool = IDENTITY_LABELS[key];
  // Deterministic pick based on dimension values (not random, so same data = same label)
  const hash = Math.round(dims.braking + dims.throttle * 3 + dims.line * 7);
  return pool[hash % pool.length];
}
