import { describe, it, expect } from 'vitest';
import { computeGhostDistance, interpolateCursorPosition, computeProjection, applyProjection } from '../trackProjection';
import type { LapData } from '../types';

function makeLapData(overrides: Partial<LapData> = {}): LapData {
  return {
    lap_number: 1,
    distance_m: [0, 100, 200, 300, 400],
    speed_mph: [60, 80, 100, 90, 70],
    lat: [33.0, 33.001, 33.002, 33.003, 33.004],
    lon: [-86.0, -86.001, -86.002, -86.003, -86.004],
    heading_deg: [0, 10, 20, 30, 40],
    lateral_g: null,
    longitudinal_g: null,
    lap_time_s: [0, 5, 10, 15, 20],
    ...overrides,
  };
}

describe('computeGhostDistance', () => {
  it('returns null when lap data arrays are too short', () => {
    const short = makeLapData({ distance_m: [0], lap_time_s: [0] });
    const normal = makeLapData();
    expect(computeGhostDistance(100, short, normal)).toBeNull();
    expect(computeGhostDistance(100, normal, short)).toBeNull();
  });

  it('returns same distance when both laps have identical timing', () => {
    const lap1 = makeLapData();
    const lap2 = makeLapData();
    const ghost = computeGhostDistance(200, lap1, lap2);
    expect(ghost).toBeCloseTo(200);
  });

  it('ghost trails behind when comp lap is slower', () => {
    const refLap = makeLapData({ lap_time_s: [0, 5, 10, 15, 20] });
    // Comp lap takes twice as long per segment
    const compLap = makeLapData({ lap_time_s: [0, 10, 20, 30, 40] });

    // At cursor distance 200 on ref lap, elapsed time = 10s
    // On comp lap, 10s corresponds to distance 100 (halfway through segment 0→1)
    const ghost = computeGhostDistance(200, refLap, compLap);
    expect(ghost).toBeCloseTo(100);
  });

  it('ghost leads when comp lap is faster', () => {
    const refLap = makeLapData({ lap_time_s: [0, 10, 20, 30, 40] });
    // Comp lap is twice as fast
    const compLap = makeLapData({ lap_time_s: [0, 5, 10, 15, 20] });

    // At cursor distance 200 on ref lap, elapsed time = 20s
    // On comp lap, 20s corresponds to distance 400 (end)
    const ghost = computeGhostDistance(200, refLap, compLap);
    expect(ghost).toBeCloseTo(400);
  });

  it('clamps ghost to comp lap start when cursor is at distance 0', () => {
    const refLap = makeLapData();
    const compLap = makeLapData();
    const ghost = computeGhostDistance(0, refLap, compLap);
    expect(ghost).toBe(0);
  });

  it('clamps ghost to comp lap end when ref time exceeds comp lap duration', () => {
    const refLap = makeLapData({ lap_time_s: [0, 10, 20, 30, 40] });
    const compLap = makeLapData({ lap_time_s: [0, 5, 10, 15, 20] });

    // At cursor distance 400 on ref lap, elapsed time = 40s
    // Comp lap only goes to 20s → should clamp to end distance (400)
    const ghost = computeGhostDistance(400, refLap, compLap);
    expect(ghost).toBe(400);
  });

  it('handles cursor at exact sample boundary', () => {
    const refLap = makeLapData({ lap_time_s: [0, 4, 8, 12, 16] });
    const compLap = makeLapData({ lap_time_s: [0, 5, 10, 15, 20] });

    // At cursor distance exactly 100 (a sample point):
    // ref time = 4s, comp at 4s → between t=0 (d=0) and t=5 (d=100)
    // frac = 4/5 = 0.8 → distance = 0 + 0.8*100 = 80
    const ghost = computeGhostDistance(100, refLap, compLap);
    expect(ghost).toBeCloseTo(80);
  });

  it('interpolates between distance samples', () => {
    const refLap = makeLapData({ lap_time_s: [0, 4, 8, 12, 16] });
    const compLap = makeLapData({ lap_time_s: [0, 5, 10, 15, 20] });

    // At cursor distance 150 on ref lap (between 100 and 200):
    // ref time = 4 + 0.5 * (8-4) = 6s
    // On comp lap: 6s is between t=5 (d=100) and t=10 (d=200)
    // frac = (6-5)/(10-5) = 0.2 → distance = 100 + 0.2*100 = 120
    const ghost = computeGhostDistance(150, refLap, compLap);
    expect(ghost).toBeCloseTo(120);
  });
});

describe('interpolateCursorPosition', () => {
  it('returns first point when cursor is at or before start', () => {
    const lapData = makeLapData();
    const projected = { x: [10, 20, 30, 40, 50], y: [50, 40, 30, 20, 10] };
    const pos = interpolateCursorPosition(0, lapData, projected);
    expect(pos).toEqual({ cx: 10, cy: 50 });
  });

  it('returns last point when cursor is beyond end', () => {
    const lapData = makeLapData();
    const projected = { x: [10, 20, 30, 40, 50], y: [50, 40, 30, 20, 10] };
    const pos = interpolateCursorPosition(500, lapData, projected);
    expect(pos).toEqual({ cx: 50, cy: 10 });
  });

  it('interpolates between points', () => {
    const lapData = makeLapData();
    const projected = { x: [10, 20, 30, 40, 50], y: [50, 40, 30, 20, 10] };
    // Distance 150 is midway between 100 and 200
    const pos = interpolateCursorPosition(150, lapData, projected);
    expect(pos?.cx).toBeCloseTo(25);
    expect(pos?.cy).toBeCloseTo(35);
  });
});

describe('computeProjection + applyProjection', () => {
  it('projects points within SVG bounds', () => {
    const lats = [[33.0, 33.01, 33.02]];
    const lons = [[-86.0, -86.01, -86.02]];
    const params = computeProjection(lats, lons, 400, 400, 12);
    expect(params).not.toBeNull();

    const proj = applyProjection(lats[0], lons[0], params!);
    expect(proj.x.length).toBe(3);
    expect(proj.y.length).toBe(3);

    // All points should be within [12, 388] (padding)
    for (const val of [...proj.x, ...proj.y]) {
      expect(val).toBeGreaterThanOrEqual(12);
      expect(val).toBeLessThanOrEqual(388);
    }
  });
});
