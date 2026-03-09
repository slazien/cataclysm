import type { CornerGrade } from './types';
import { isNAGrade } from './gradeUtils';

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

function gradeToScore(grade: string): number | null {
  if (!grade || isNAGrade(grade)) return null;
  const letter = grade.charAt(0).toUpperCase();
  return GRADE_SCORES[letter] ?? 50;
}

function avg(scores: (number | null)[]): number {
  const valid = scores.filter((s): s is number => s !== null);
  return valid.length > 0 ? valid.reduce((a, b) => a + b, 0) / valid.length : 50;
}

export function computeSkillDimensions(grades: CornerGrade[]): SkillDimensions | null {
  if (!grades || grades.length === 0) return null;

  return {
    braking: avg(grades.map((g) => gradeToScore(g.braking))),
    trailBraking: avg(grades.map((g) => gradeToScore(g.trail_braking))),
    throttle: avg(grades.map((g) => gradeToScore(g.throttle))),
    line: avg(grades.map((g) => gradeToScore(g.min_speed))),
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

  // If all dimensions within 10 points, driver is balanced.
  // On tie, first dimension in declaration order wins (braking > trailBraking > throttle > line).
  const dominant = entries.find(([, v]) => v === max);
  const key = max - min <= 10 ? 'balanced' : (dominant?.[0] ?? 'balanced');

  const pool = IDENTITY_LABELS[key];
  // Deterministic pick based on all dimension values (not random, so same data = same label)
  const hash = Math.round(dims.braking + dims.trailBraking * 2 + dims.throttle * 3 + dims.line * 7);
  return pool[hash % pool.length];
}
