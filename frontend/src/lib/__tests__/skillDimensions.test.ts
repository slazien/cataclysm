import {
  getIdentityLabel,
  computeSkillDimensions,
  dimensionsToArray,
  SKILL_AXES,
} from '../skillDimensions';
import type { SkillDimensions } from '../skillDimensions';

describe('getIdentityLabel', () => {
  it('returns braking label when braking is highest', () => {
    const dims = { braking: 90, trailBraking: 60, throttle: 50, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['LATE BRAKER', 'BRAKE BOSS']).toContain(label);
  });

  it('returns trail braking label when trailBraking is highest', () => {
    const dims = { braking: 50, trailBraking: 95, throttle: 60, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['TRAIL WIZARD', 'SMOOTH OPERATOR']).toContain(label);
  });

  it('returns throttle label when throttle is highest', () => {
    const dims = { braking: 50, trailBraking: 60, throttle: 92, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['THROTTLE KING', 'POWER PLAYER']).toContain(label);
  });

  it('returns line label when line is highest', () => {
    const dims = { braking: 50, trailBraking: 60, throttle: 55, line: 95 };
    const label = getIdentityLabel(dims);
    expect(['LINE MASTER', 'APEX HUNTER']).toContain(label);
  });

  it('returns balanced label when all within 10pts', () => {
    const dims = { braking: 75, trailBraking: 80, throttle: 78, line: 72 };
    const label = getIdentityLabel(dims);
    expect(['COMPLETE DRIVER', 'WELL ROUNDED']).toContain(label);
  });

  it('returns fallback for null input', () => {
    expect(getIdentityLabel(null)).toBe('TRACK WARRIOR');
  });

  it('picks first dimension on tie (braking wins over trailBraking)', () => {
    const dims = { braking: 90, trailBraking: 90, throttle: 60, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['LATE BRAKER', 'BRAKE BOSS']).toContain(label);
  });
});

// ---------------------------------------------------------------------------
// SKILL_AXES
// ---------------------------------------------------------------------------

describe('SKILL_AXES', () => {
  it('contains the four skill axis labels', () => {
    expect(SKILL_AXES).toEqual(['Braking', 'Trail Braking', 'Throttle', 'Line']);
  });

  it('has length 4', () => {
    expect(SKILL_AXES).toHaveLength(4);
  });
});

// ---------------------------------------------------------------------------
// computeSkillDimensions (exercises gradeToScore internally)
// ---------------------------------------------------------------------------

describe('computeSkillDimensions', () => {
  it('returns null for empty array', () => {
    expect(computeSkillDimensions([])).toBeNull();
  });

  it('returns null for null/undefined input', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(computeSkillDimensions(null as any)).toBeNull();
  });

  it('computes averages from a single corner grade', () => {
    const grades = [
      {
        corner: 1,
        braking: 'A',
        trail_braking: 'B',
        min_speed: 'C',
        throttle: 'D',
        notes: '',
      },
    ];
    const result = computeSkillDimensions(grades);
    expect(result).not.toBeNull();
    // A=100, B=80, C=60, D=40
    expect(result!.braking).toBe(100);
    expect(result!.trailBraking).toBe(80);
    expect(result!.line).toBe(60); // min_speed maps to line
    expect(result!.throttle).toBe(40);
  });

  it('computes averages from multiple corner grades', () => {
    const grades = [
      { corner: 1, braking: 'A', trail_braking: 'A', min_speed: 'A', throttle: 'A', notes: '' },
      { corner: 2, braking: 'C', trail_braking: 'C', min_speed: 'C', throttle: 'C', notes: '' },
    ];
    const result = computeSkillDimensions(grades);
    expect(result).not.toBeNull();
    // (100 + 60) / 2 = 80
    expect(result!.braking).toBe(80);
    expect(result!.trailBraking).toBe(80);
    expect(result!.throttle).toBe(80);
    expect(result!.line).toBe(80);
  });

  it('handles F grades', () => {
    const grades = [
      { corner: 1, braking: 'F', trail_braking: 'F', min_speed: 'F', throttle: 'F', notes: '' },
    ];
    const result = computeSkillDimensions(grades);
    expect(result!.braking).toBe(20);
    expect(result!.trailBraking).toBe(20);
    expect(result!.throttle).toBe(20);
    expect(result!.line).toBe(20);
  });

  it('handles unknown grades with fallback score of 50', () => {
    const grades = [
      { corner: 1, braking: 'Z', trail_braking: 'X', min_speed: '?', throttle: '', notes: '' },
    ];
    const result = computeSkillDimensions(grades);
    // Unknown grades fall back to 50
    expect(result!.braking).toBe(50);
    expect(result!.trailBraking).toBe(50);
    expect(result!.throttle).toBe(50);
    expect(result!.line).toBe(50);
  });

  it('handles lowercase grade letters via charAt(0).toUpperCase()', () => {
    const grades = [
      { corner: 1, braking: 'a', trail_braking: 'b', min_speed: 'c', throttle: 'd', notes: '' },
    ];
    const result = computeSkillDimensions(grades);
    expect(result!.braking).toBe(100);
    expect(result!.trailBraking).toBe(80);
    expect(result!.line).toBe(60);
    expect(result!.throttle).toBe(40);
  });

  it('excludes N/A grades from skill dimension averages', () => {
    const grades = [
      { corner: 1, braking: 'A', trail_braking: 'N/A', min_speed: 'B', throttle: 'C', notes: '' },
      { corner: 2, braking: 'N/A', trail_braking: 'A', min_speed: 'A', throttle: 'N/A', notes: '' },
    ];
    const result = computeSkillDimensions(grades);
    expect(result).not.toBeNull();
    // braking: only corner 1 has A (100) → 100
    expect(result!.braking).toBe(100);
    // trailBraking: only corner 2 has A (100) → 100
    expect(result!.trailBraking).toBe(100);
    // line: B(80) + A(100) = 180/2 = 90
    expect(result!.line).toBe(90);
    // throttle: only corner 1 has C (60) → 60
    expect(result!.throttle).toBe(60);
  });

  it('handles grade strings like "A+" by taking first character', () => {
    const grades = [
      {
        corner: 1,
        braking: 'A+',
        trail_braking: 'B-',
        min_speed: 'C+',
        throttle: 'D-',
        notes: '',
      },
    ];
    const result = computeSkillDimensions(grades);
    expect(result!.braking).toBe(100); // 'A' from 'A+'
    expect(result!.trailBraking).toBe(80); // 'B' from 'B-'
    expect(result!.line).toBe(60);
    expect(result!.throttle).toBe(40);
  });
});

// ---------------------------------------------------------------------------
// dimensionsToArray
// ---------------------------------------------------------------------------

describe('dimensionsToArray', () => {
  it('returns [braking, trailBraking, throttle, line] in order', () => {
    const dims: SkillDimensions = {
      braking: 90,
      trailBraking: 75,
      throttle: 80,
      line: 70,
    };
    expect(dimensionsToArray(dims)).toEqual([90, 75, 80, 70]);
  });

  it('works with zero values', () => {
    const dims: SkillDimensions = {
      braking: 0,
      trailBraking: 0,
      throttle: 0,
      line: 0,
    };
    expect(dimensionsToArray(dims)).toEqual([0, 0, 0, 0]);
  });

  it('works with decimal values', () => {
    const dims: SkillDimensions = {
      braking: 85.5,
      trailBraking: 72.3,
      throttle: 66.7,
      line: 91.1,
    };
    expect(dimensionsToArray(dims)).toEqual([85.5, 72.3, 66.7, 91.1]);
  });
});
