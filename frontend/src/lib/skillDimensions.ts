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
