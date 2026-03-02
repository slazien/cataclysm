import { resolveSpeedMarkers, extractActionTitle } from '../textUtils';

describe('resolveSpeedMarkers', () => {
  describe('imperial mode (isMetric=false)', () => {
    it('resolves markers to "N mph"', () => {
      expect(resolveSpeedMarkers('Carry {{speed:3}} more', false)).toBe(
        'Carry 3 mph more',
      );
    });

    it('handles decimal values', () => {
      expect(resolveSpeedMarkers('Min speed was {{speed:42.5}}', false)).toBe(
        'Min speed was 42.5 mph',
      );
    });

    it('handles multiple markers', () => {
      expect(
        resolveSpeedMarkers(
          '{{speed:2}}-{{speed:3}} more through apex',
          false,
        ),
      ).toBe('2 mph-3 mph more through apex');
    });
  });

  describe('metric mode (isMetric=true)', () => {
    it('resolves markers to "N km/h"', () => {
      expect(resolveSpeedMarkers('Carry {{speed:3}} more', true)).toBe(
        'Carry 5 km/h more',
      );
    });

    it('preserves decimal precision', () => {
      // 42.5 * 1.60934 = 68.39695
      expect(resolveSpeedMarkers('Min speed was {{speed:42.5}}', true)).toBe(
        'Min speed was 68.4 km/h',
      );
    });

    it('handles integer values (zero decimals)', () => {
      // 100 * 1.60934 = 160.934 -> 161 (0 decimals)
      expect(resolveSpeedMarkers('Top speed {{speed:100}}', true)).toBe(
        'Top speed 161 km/h',
      );
    });
  });

  describe('legacy fallback (bare "N mph")', () => {
    it('converts single "N mph" in metric mode', () => {
      // 42 * 1.60934 = 67.59228 -> 67.6 (1 decimal in original)
      expect(resolveSpeedMarkers('Min speed was 42 mph', true)).toBe(
        'Min speed was 68 km/h',
      );
    });

    it('converts range "N-M mph" in metric mode', () => {
      // 2 * 1.60934 = 3.21868 -> 3
      // 3 * 1.60934 = 4.82802 -> 5
      expect(resolveSpeedMarkers('Carry 2-3 mph more', true)).toBe(
        'Carry 3-5 km/h more',
      );
    });

    it('does not convert legacy in imperial mode', () => {
      expect(resolveSpeedMarkers('Min speed was 42 mph', false)).toBe(
        'Min speed was 42 mph',
      );
    });
  });

  describe('passthrough', () => {
    it('returns text unchanged when no markers present', () => {
      const text = 'No speed values here.';
      expect(resolveSpeedMarkers(text, false)).toBe(text);
      expect(resolveSpeedMarkers(text, true)).toBe(text);
    });

    it('handles empty string', () => {
      expect(resolveSpeedMarkers('', false)).toBe('');
      expect(resolveSpeedMarkers('', true)).toBe('');
    });

    it('returns raw value when marker value is not a valid number', () => {
      // The regex matches [\d.]+ so "abc" won't match. But "." matches
      // and parseFloat(".") returns NaN, exercising the isNaN guard.
      expect(resolveSpeedMarkers('{{speed:.}}', false)).toBe('.');
      expect(resolveSpeedMarkers('{{speed:.}}', true)).toBe('.');
    });
  });

  describe('legacy decimal handling', () => {
    it('preserves decimal precision in legacy single speed metric conversion', () => {
      // Exercise the decimal branch on line 32 — "42.5 mph" has 1 decimal
      expect(resolveSpeedMarkers('Speed was 42.5 mph', true)).toBe('Speed was 68.4 km/h');
    });

    it('converts legacy integer mph to integer km/h', () => {
      // No decimal in "42 mph" → 0 decimals in output
      expect(resolveSpeedMarkers('Speed was 42 mph', true)).toBe('Speed was 68 km/h');
    });
  });

  describe('mixed markers + legacy', () => {
    it('resolves both in same string', () => {
      const input = '{{speed:50}} at entry, then 42 mph at exit';
      // Metric: 50*1.60934=80, 42*1.60934=67.6->68
      expect(resolveSpeedMarkers(input, true)).toBe(
        '80 km/h at entry, then 68 km/h at exit',
      );
    });
  });
});

describe('extractActionTitle', () => {
  it('extracts first clause before punctuation', () => {
    expect(
      extractActionTitle('Late braking into T5, causing overshoot'),
    ).toBe('Late braking into T5');
  });

  it('falls back to first ~50 chars for long text without punctuation', () => {
    const long = 'A'.repeat(80);
    expect(extractActionTitle(long).length).toBeLessThanOrEqual(50);
  });

  it('returns first word when subsequent words would exceed 50 chars', () => {
    const text = 'Short ' + 'X'.repeat(60);
    const result = extractActionTitle(text);
    expect(result).toBe('Short');
    expect(result.length).toBeLessThanOrEqual(50);
  });

  it('falls back to text.slice(0, 50) when first word alone exceeds 50 chars', () => {
    const text = 'X'.repeat(60);
    const result = extractActionTitle(text);
    expect(result).toBe('X'.repeat(50));
  });

  it('returns full text when shorter than 50 chars with no punctuation', () => {
    expect(extractActionTitle('Brake later into T5')).toBe('Brake later into T5');
  });

  it('handles text with multiple words that fit within 50 chars', () => {
    const text = 'word1 word2 word3 word4 word5';
    expect(extractActionTitle(text)).toBe(text);
  });
});
