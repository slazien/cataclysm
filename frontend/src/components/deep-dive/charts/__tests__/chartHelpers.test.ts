import { describe, it, expect } from 'vitest';
import {
  CHART_MARGINS,
  CHART_MARGINS_MOBILE,
  getChartMargins,
} from '../chartHelpers';

describe('CHART_MARGINS', () => {
  it('has the expected desktop margin values', () => {
    expect(CHART_MARGINS).toEqual({ top: 28, right: 16, bottom: 40, left: 56 });
  });
});

describe('CHART_MARGINS_MOBILE', () => {
  it('has the expected mobile margin values', () => {
    expect(CHART_MARGINS_MOBILE).toEqual({ top: 20, right: 8, bottom: 32, left: 40 });
  });

  it('mobile margins are strictly smaller than desktop margins', () => {
    // Ensures we never accidentally swap the objects
    expect(CHART_MARGINS_MOBILE.left).toBeLessThan(CHART_MARGINS.left);
    expect(CHART_MARGINS_MOBILE.right).toBeLessThan(CHART_MARGINS.right);
    expect(CHART_MARGINS_MOBILE.top).toBeLessThan(CHART_MARGINS.top);
    expect(CHART_MARGINS_MOBILE.bottom).toBeLessThan(CHART_MARGINS.bottom);
  });
});

describe('getChartMargins', () => {
  it('returns desktop margins when isMobile is false', () => {
    expect(getChartMargins(false)).toBe(CHART_MARGINS);
  });

  it('returns mobile margins when isMobile is true', () => {
    expect(getChartMargins(true)).toBe(CHART_MARGINS_MOBILE);
  });

  it('returns the same object reference (no new allocation per call)', () => {
    // Important for memoization: useMemo dependencies compare by reference
    expect(getChartMargins(false)).toBe(getChartMargins(false));
    expect(getChartMargins(true)).toBe(getChartMargins(true));
  });
});
