import type { SkillLevel } from '@/stores/uiStore';

/**
 * Format a distance measurement based on skill level.
 * Novice: relative ("30m before corner entry")
 * Intermediate: both ("30m before entry (158m)")
 * Advanced: absolute only ("158m")
 */
export function formatDistance(
  distanceM: number,
  referenceM: number | null,
  skillLevel: SkillLevel,
): string {
  const abs = `${Math.round(distanceM)}m`;
  if (referenceM === null) return abs;

  const delta = Math.round(distanceM - referenceM);
  const relative = delta >= 0
    ? `${delta}m after entry`
    : `${Math.abs(delta)}m before entry`;

  switch (skillLevel) {
    case 'novice':
      return relative;
    case 'intermediate':
      return `${relative} (${abs})`;
    case 'advanced':
      return abs;
  }
}

/**
 * Get a human-readable explanation for a corner grade.
 * Returns null for intermediate+ (they don't need explanations).
 */
export function gradeExplanation(
  grade: string,
  category: string,
  skillLevel: SkillLevel,
): string | null {
  if (skillLevel !== 'novice') return null;

  const letter = grade.charAt(0).toUpperCase();
  const explanations: Record<string, Record<string, string>> = {
    A: {
      braking: 'Excellent brake point selection — consistent and well-timed.',
      trail_braking: 'Great trail braking technique — smooth transition into the corner.',
      min_speed: 'Carrying great minimum speed through the corner.',
      throttle: 'Strong throttle application — getting on power early and smoothly.',
    },
    B: {
      braking: 'Good braking but room for more consistency in brake point selection.',
      trail_braking: 'Decent trail braking — could hold brakes slightly longer into the corner.',
      min_speed: 'Reasonable corner speed but leaving some time on the table.',
      throttle: 'Good throttle timing — try getting on power just a fraction earlier.',
    },
    C: {
      braking: 'Braking is inconsistent — sometimes early, sometimes late.',
      trail_braking: 'Trail braking needs work — releasing brakes too abruptly before turn-in.',
      min_speed: 'Scrubbing too much speed in the corner — try carrying more entry speed.',
      throttle: 'Hesitating on throttle application — commit to power earlier.',
    },
    D: {
      braking: 'Braking much too early — losing significant time on the approach.',
      trail_braking: 'Very little trail braking happening — work on holding light brake pressure into the turn.',
      min_speed: 'Corner speed is well below potential — focus on smooth inputs to build confidence.',
      throttle: 'Very late on throttle — this is costing significant time on every corner exit.',
    },
    F: {
      braking: 'Braking needs fundamental work — consider a coaching session focused on brake markers.',
      trail_braking: 'No trail braking detected — this is an important technique to develop.',
      min_speed: 'Corner speed is very low — focus on looking further ahead and smooth steering.',
      throttle: 'Throttle application needs attention — work on progressive, confident power delivery.',
    },
  };

  return explanations[letter]?.[category] ?? null;
}

/**
 * Format a corner metric value with skill-appropriate detail level.
 */
export function formatCornerMetric(
  key: string,
  value: number,
  delta: number | null,
  skillLevel: SkillLevel,
): { label: string; display: string; detail: string | null } {
  const labels: Record<string, string> = {
    min_speed_kph: 'Min Speed',
    brake_point_m: 'Brake Point',
    peak_brake_g: 'Peak Brake G',
    throttle_commit_m: 'Throttle Point',
  };

  const label = labels[key] ?? key;

  let display: string;
  if (key === 'min_speed_kph') {
    display = `${value.toFixed(1)} km/h`;
  } else if (key === 'peak_brake_g') {
    display = `${value.toFixed(2)}g`;
  } else {
    display = `${Math.round(value)}m`;
  }

  let detail: string | null = null;
  if (delta !== null) {
    const sign = delta > 0 ? '+' : '';
    if (skillLevel === 'novice') {
      // Novice: show qualitative comparison
      if (key === 'min_speed_kph') {
        detail = delta > 0 ? 'Faster than best' : 'Slower than best';
      } else if (key === 'brake_point_m') {
        detail = delta > 0 ? 'Later than best (good!)' : 'Earlier than best';
      } else {
        detail = delta > 0 ? `${sign}${delta.toFixed(1)}` : `${sign}${delta.toFixed(1)}`;
      }
    } else {
      // Intermediate/Advanced: show numeric delta
      if (key === 'min_speed_kph') {
        detail = `${sign}${delta.toFixed(1)} km/h`;
      } else if (key === 'peak_brake_g') {
        detail = `${sign}${delta.toFixed(2)}g`;
      } else {
        detail = `${sign}${Math.round(delta)}m`;
      }
    }
  }

  return { label, display, detail };
}
