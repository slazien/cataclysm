import {
  normalizeScore,
  formatLapTime,
  formatDelta,
  formatSpeed,
  formatTimeShort,
  parseSessionDate,
} from '../formatters';

// ---------------------------------------------------------------------------
// normalizeScore
// ---------------------------------------------------------------------------
describe('normalizeScore', () => {
  it('multiplies values <= 1 by 100 to convert 0-1 range to 0-100', () => {
    expect(normalizeScore(0.75)).toBe(75);
  });

  it('returns values > 1 unchanged (already in 0-100 range)', () => {
    expect(normalizeScore(75)).toBe(75);
  });

  it('treats exactly 1.0 as 0-1 range and returns 100', () => {
    expect(normalizeScore(1)).toBe(100);
  });

  it('treats exactly 0 as 0-1 range and returns 0', () => {
    expect(normalizeScore(0)).toBe(0);
  });

  it('handles 0.5 correctly (boundary mid-point in 0-1 range)', () => {
    expect(normalizeScore(0.5)).toBe(50);
  });

  it('handles 100 (maximum 0-100 range value) unchanged', () => {
    expect(normalizeScore(100)).toBe(100);
  });

  it('handles decimal 0-1 values with precision', () => {
    expect(normalizeScore(0.123)).toBeCloseTo(12.3);
  });

  it('passes through values greater than 1 even when fractional-looking', () => {
    // e.g. 1.5 is > 1 so passes through
    expect(normalizeScore(1.5)).toBe(1.5);
  });
});

// ---------------------------------------------------------------------------
// formatLapTime
// ---------------------------------------------------------------------------
describe('formatLapTime', () => {
  it('formats a sub-minute lap time', () => {
    // 45.678s -> "0:45.678"
    expect(formatLapTime(45.678)).toBe('0:45.678');
  });

  it('formats a typical 1-minute+ lap time', () => {
    // 90.5s -> 1 min, 30.5s -> "1:30.500"
    expect(formatLapTime(90.5)).toBe('1:30.500');
  });

  it('pads seconds to 6 characters (including decimal point and 3 decimals)', () => {
    // 61.001s -> 1 min, 1.001s -> "1:01.001"
    expect(formatLapTime(61.001)).toBe('1:01.001');
  });

  it('formats exactly 60 seconds', () => {
    expect(formatLapTime(60)).toBe('1:00.000');
  });

  it('formats exactly 0 seconds', () => {
    expect(formatLapTime(0)).toBe('0:00.000');
  });

  it('formats a 2-minute lap time', () => {
    // 125.999s -> 2 min, 5.999s -> "2:05.999"
    expect(formatLapTime(125.999)).toBe('2:05.999');
  });

  it('handles fractional seconds with 3-decimal precision', () => {
    expect(formatLapTime(73.1)).toBe('1:13.100');
  });
});

// ---------------------------------------------------------------------------
// formatDelta
// ---------------------------------------------------------------------------
describe('formatDelta', () => {
  it('prefixes positive values with "+"', () => {
    expect(formatDelta(0.543)).toBe('+0.543s');
  });

  it('does not prefix negative values (sign is included by the number itself)', () => {
    expect(formatDelta(-0.543)).toBe('-0.543s');
  });

  it('prefixes zero with "+" (non-negative)', () => {
    expect(formatDelta(0)).toBe('+0.000s');
  });

  it('formats to 3 decimal places', () => {
    expect(formatDelta(1.1)).toBe('+1.100s');
  });

  it('handles large positive deltas', () => {
    expect(formatDelta(12.345)).toBe('+12.345s');
  });

  it('handles large negative deltas', () => {
    expect(formatDelta(-12.345)).toBe('-12.345s');
  });

  it('handles very small positive delta', () => {
    expect(formatDelta(0.001)).toBe('+0.001s');
  });
});

// ---------------------------------------------------------------------------
// formatSpeed
// ---------------------------------------------------------------------------
describe('formatSpeed', () => {
  it('formats speed with 1 decimal place and mph unit', () => {
    expect(formatSpeed(87.3)).toBe('87.3 mph');
  });

  it('rounds to 1 decimal place (JS toFixed banker-rounding: 87.35 -> 87.3)', () => {
    // JS toFixed uses IEEE 754 representation; 87.35 is stored slightly below
    // the mathematical value so toFixed(1) produces "87.3" not "87.4".
    expect(formatSpeed(87.35)).toBe('87.3 mph');
  });

  it('formats zero speed', () => {
    expect(formatSpeed(0)).toBe('0.0 mph');
  });

  it('formats integer speed with trailing zero decimal', () => {
    expect(formatSpeed(100)).toBe('100.0 mph');
  });

  it('formats negative speed (reverse/edge case)', () => {
    expect(formatSpeed(-5)).toBe('-5.0 mph');
  });

  it('formats very small fractional speed', () => {
    expect(formatSpeed(0.05)).toBe('0.1 mph');
  });

  it('formats large speed values', () => {
    expect(formatSpeed(200.9)).toBe('200.9 mph');
  });
});

// ---------------------------------------------------------------------------
// formatTimeShort
// ---------------------------------------------------------------------------
describe('formatTimeShort', () => {
  it('formats sub-minute time as "SS.SSs"', () => {
    expect(formatTimeShort(45.67)).toBe('45.67s');
  });

  it('formats time >= 60s as "M:SS.S"', () => {
    // 90s -> 1 min, 30s -> "1:30.0"
    expect(formatTimeShort(90)).toBe('1:30.0');
  });

  it('formats exactly 0 seconds as "0.00s"', () => {
    expect(formatTimeShort(0)).toBe('0.00s');
  });

  it('formats exactly 60 seconds as "1:00.0"', () => {
    expect(formatTimeShort(60)).toBe('1:00.0');
  });

  it('pads seconds to 4 chars in minute-mode (e.g. "1:05.0")', () => {
    expect(formatTimeShort(65)).toBe('1:05.0');
  });

  it('formats sub-minute with 2 decimal places', () => {
    expect(formatTimeShort(9.5)).toBe('9.50s');
  });

  it('formats 2-minute times correctly', () => {
    // 125s -> 2 min, 5s -> "2:05.0"
    expect(formatTimeShort(125)).toBe('2:05.0');
  });

  it('sub-minute fractional precision rounds at 2 decimals', () => {
    expect(formatTimeShort(59.999)).toBe('60.00s');
  });
});

// ---------------------------------------------------------------------------
// parseSessionDate
// ---------------------------------------------------------------------------
describe('parseSessionDate', () => {
  it('parses a "DD/MM/YYYY HH:MM" string into a Date', () => {
    const d = parseSessionDate('15/06/2024 14:30');
    expect(d.getFullYear()).toBe(2024);
    expect(d.getMonth()).toBe(5); // 0-indexed June
    expect(d.getDate()).toBe(15);
    expect(d.getHours()).toBe(14);
    expect(d.getMinutes()).toBe(30);
  });

  it('parses date with time "00:00" correctly', () => {
    const d = parseSessionDate('01/01/2025 00:00');
    expect(d.getFullYear()).toBe(2025);
    expect(d.getMonth()).toBe(0); // January
    expect(d.getDate()).toBe(1);
  });

  it('parses single-digit day and month (zero-padded)', () => {
    const d = parseSessionDate('03/07/2023 09:15');
    expect(d.getFullYear()).toBe(2023);
    expect(d.getMonth()).toBe(6); // July
    expect(d.getDate()).toBe(3);
    expect(d.getHours()).toBe(9);
    expect(d.getMinutes()).toBe(15);
  });

  it('falls back to midnight when time part is absent', () => {
    // "DD/MM/YYYY" with no time — uses '00:00' fallback
    const d = parseSessionDate('20/11/2022');
    expect(d.getFullYear()).toBe(2022);
    expect(d.getMonth()).toBe(10); // November
    expect(d.getDate()).toBe(20);
    expect(d.getHours()).toBe(0);
    expect(d.getMinutes()).toBe(0);
  });

  it('returns a valid Date instance', () => {
    const d = parseSessionDate('31/12/2024 23:59');
    expect(d).toBeInstanceOf(Date);
    expect(isNaN(d.getTime())).toBe(false);
  });

  it('parses end-of-year date correctly', () => {
    const d = parseSessionDate('31/12/2024 23:59');
    expect(d.getFullYear()).toBe(2024);
    expect(d.getMonth()).toBe(11); // December
    expect(d.getDate()).toBe(31);
  });
});
