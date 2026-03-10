import {
  resolveSpeedMarkers,
  extractActionTitle,
  extractDetailText,
  formatCoachingText,
} from '../textUtils';

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

  describe('range markers {{speed:N-M}}', () => {
    it('resolves range marker to "N-M mph" in imperial', () => {
      expect(resolveSpeedMarkers('within {{speed:1-2}} of your best', false)).toBe(
        'within 1-2 mph of your best',
      );
    });

    it('converts range marker to km/h in metric', () => {
      // 1*1.60934=2, 2*1.60934=3
      expect(resolveSpeedMarkers('within {{speed:1-2}} of your best', true)).toBe(
        'within 2-3 km/h of your best',
      );
    });

    it('handles decimal range marker', () => {
      // 1.5*1.60934=2.4, 2.5*1.60934=4.0
      expect(resolveSpeedMarkers('gap of {{speed:1.5-2.5}}', true)).toBe(
        'gap of 2.4-4.0 km/h',
      );
    });
  });

  describe('legacy fallback (bare "N km/h") in imperial mode', () => {
    it('converts single "N km/h" → mph in imperial mode', () => {
      // 20 km/h / 1.60934 = 12.427 → 12 (0 decimal in original)
      expect(resolveSpeedMarkers('Wind was 20 km/h today', false)).toBe(
        'Wind was 12 mph today',
      );
    });

    it('converts range "N-M km/h" → mph in imperial mode', () => {
      // 20/1.60934=12, 30/1.60934=19
      expect(resolveSpeedMarkers('Speed between 20-30 km/h', false)).toBe(
        'Speed between 12-19 mph',
      );
    });

    it('preserves decimal precision for km/h in imperial', () => {
      // 80.0 km/h / 1.60934 = 49.709... → "49.7" (1 decimal)
      const result = resolveSpeedMarkers('Speed was 80.0 km/h', false);
      expect(result).toBe('Speed was 49.7 mph');
    });

    it('does not convert km/h in metric mode (already correct unit)', () => {
      expect(resolveSpeedMarkers('Wind was 20 km/h today', true)).toBe(
        'Wind was 20 km/h today',
      );
    });
  });

  describe('legacy fallback (distance units in coaching text)', () => {
    it('converts "Nm" to feet in imperial mode', () => {
      expect(resolveSpeedMarkers('Brake 98m past the bridge.', false)).toBe(
        'Brake 322 ft past the bridge.',
      );
    });

    it('converts "N meters" to feet in imperial mode', () => {
      expect(resolveSpeedMarkers('Move turn-in 10 meters later.', false)).toBe(
        'Move turn-in 33 ft later.',
      );
    });

    it('converts feet to meters in metric mode', () => {
      expect(resolveSpeedMarkers('Brake 322 ft before apex.', true)).toBe(
        'Brake 98 m before apex.',
      );
    });

    it('does not convert m/s values as distance markers', () => {
      expect(resolveSpeedMarkers('Entry speed is 30 m/s.', false)).toBe(
        'Entry speed is 30 m/s.',
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

  describe('time markers', () => {
    it('resolves {{time:N}} to "Ns"', () => {
      expect(resolveSpeedMarkers('gained {{time:0.18}} on average', false)).toBe(
        'gained 0.18s on average',
      );
    });

    it('resolves {{time:N}} in metric mode too (no conversion)', () => {
      expect(resolveSpeedMarkers('saved {{time:1.5}} per lap', true)).toBe(
        'saved 1.5s per lap',
      );
    });

    it('handles both speed and time markers in same string', () => {
      expect(
        resolveSpeedMarkers('Carry {{speed:3}} more to save {{time:0.2}}', false),
      ).toBe('Carry 3 mph more to save 0.2s');
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

  describe('temperature conversion (legacy)', () => {
    it('converts "N°C" → °F in imperial mode', () => {
      // 22 * 9/5 + 32 = 71.6 → 72
      expect(resolveSpeedMarkers('Temp was 22°C today', false)).toBe('Temp was 72°F today');
    });

    it('converts "N°F" → °C in metric mode', () => {
      // (72 - 32) * 5/9 = 22.2 → 22
      expect(resolveSpeedMarkers('Temp was 72°F today', true)).toBe('Temp was 22°C today');
    });

    it('leaves °F unchanged in imperial mode', () => {
      expect(resolveSpeedMarkers('Temp was 72°F today', false)).toBe('Temp was 72°F today');
    });

    it('leaves °C unchanged in metric mode', () => {
      expect(resolveSpeedMarkers('Temp was 22°C today', true)).toBe('Temp was 22°C today');
    });
  });

  describe('precipitation conversion (legacy)', () => {
    it('converts "Nmm" → in in imperial mode', () => {
      // 3.5 / 25.4 = 0.138 → 0.14
      expect(resolveSpeedMarkers('Precipitation 3.5mm', false)).toBe('Precipitation 0.14in');
    });

    it('leaves "Nmm" unchanged in metric mode', () => {
      expect(resolveSpeedMarkers('Precipitation 3.5mm', true)).toBe('Precipitation 3.5mm');
    });
  });

  describe('distance conversion (legacy)', () => {
    it('converts compact metric distance to feet in imperial mode', () => {
      expect(resolveSpeedMarkers('Try braking at 98m past the bridge.', false)).toBe(
        'Try braking at 322 ft past the bridge.',
      );
    });

    it('converts word-form metric distance to feet in imperial mode', () => {
      expect(resolveSpeedMarkers('Brake 10 meters later.', false)).toBe(
        'Brake 33 ft later.',
      );
    });

    it('converts feet to meters in metric mode', () => {
      expect(resolveSpeedMarkers('Brake at 322 ft.', true)).toBe('Brake at 98 m.');
    });

    it('does not convert m/s values as distance markers', () => {
      const text = 'Apex speed change was 2 m/s lap to lap.';
      expect(resolveSpeedMarkers(text, false)).toBe(text);
      expect(resolveSpeedMarkers(text, true)).toBe(text);
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

  it('extracts full bold title when text starts with **bold**', () => {
    const text = '**Throttle commit scatter is your second-biggest time cost:** You are losing 0.3s per lap.';
    expect(extractActionTitle(text)).toBe('**Throttle commit scatter is your second-biggest time cost**');
  });

  it('extracts full bold title regardless of length', () => {
    const text = '**Early braker archetype across the track:** Your driving shows consistent early braking.';
    expect(extractActionTitle(text)).toBe('**Early braker archetype across the track**');
  });

  it('falls back to clause extraction when no bold prefix', () => {
    expect(extractActionTitle('Late braking into T5, causing overshoot')).toBe('Late braking into T5');
  });
});

describe('extractDetailText', () => {
  it('extracts text after bold title with colon separator', () => {
    const text = '**Brake consistency is strong:** However, T5 shows 15m variance.';
    expect(extractDetailText(text)).toBe('However, T5 shows 15m variance.');
  });

  it('extracts text after bold title without separator', () => {
    const text = '**Early apex habit** You are turning in too soon.';
    expect(extractDetailText(text)).toBe('You are turning in too soon.');
  });

  it('returns empty string when no detail exists', () => {
    expect(extractDetailText('Short text no bold')).toBe('');
  });

  it('handles bold title with dash separator', () => {
    const text = '**T5 Brake Drill** - Pick T5 as your focus. Laps 1-3: brake at the 2-board.';
    expect(extractDetailText(text)).toBe('Pick T5 as your focus. Laps 1-3: brake at the 2-board.');
  });

  it('falls back to clause-based split when no bold', () => {
    const text = 'Late braking into T5, causing consistent overshoot at the apex.';
    expect(extractDetailText(text)).toBe('causing consistent overshoot at the apex.');
  });
});

// ---------------------------------------------------------------------------
// formatCoachingText
// ---------------------------------------------------------------------------

describe('formatCoachingText', () => {
  it('returns text unchanged when it already has paragraph breaks', () => {
    const text = 'First paragraph.\n\nSecond paragraph.';
    expect(formatCoachingText(text)).toBe(text);
  });

  it('inserts break before "Lap N:" markers', () => {
    const text = 'Do something. Lap 1-2: brake later. Lap 3-4: try trail braking.';
    const result = formatCoachingText(text);
    expect(result).toContain('\n\nLap 1-2:');
    expect(result).toContain('\n\nLap 3-4:');
  });

  it('inserts break before "On Laps N" markers', () => {
    const text = 'Warm up first. On Laps 1-2 focus on braking.';
    const result = formatCoachingText(text);
    expect(result).toContain('\n\nOn Laps 1-2');
  });

  it('inserts break before section headers like Measure:/Target:/Goal:', () => {
    const text = 'Focus on entry speed. Measure: brake-to-apex delta. Target: under 0.5s.';
    const result = formatCoachingText(text);
    expect(result).toContain('\n\nMeasure:');
    expect(result).toContain('\n\nTarget:');
  });

  it('inserts break before evidence sentences like "Early laps"', () => {
    const text = 'Braking is consistent. Early laps show good brake points.';
    const result = formatCoachingText(text);
    expect(result).toContain('\n\nEarly laps');
  });

  it('inserts break before "This" sentences (not "This is")', () => {
    const text = 'Speed drops by 5mph. This suggests tire degradation.';
    const result = formatCoachingText(text);
    expect(result).toContain('\n\nThis suggests');
  });

  it('does not insert break before "This is"', () => {
    const text = 'Speed drops by 5mph. This is normal.';
    const result = formatCoachingText(text);
    expect(result).not.toContain('\n\nThis is');
  });

  it('inserts break before Focus:/Setup:/Key: headers', () => {
    const text = 'Go faster. Focus: corner entry. Setup: lower tire pressure.';
    const result = formatCoachingText(text);
    expect(result).toContain('\n\nFocus:');
    expect(result).toContain('\n\nSetup:');
  });

  it('inserts break before action instructions like "Focus on"', () => {
    const text = 'Speed is good. Focus on trail braking next.';
    const result = formatCoachingText(text);
    expect(result).toContain('\n\nFocus on');
  });

  it('inserts break before numbered steps', () => {
    const text = 'Here is the drill. 1. Brake at the 2-board. 2. Trail brake to apex.';
    const result = formatCoachingText(text);
    expect(result).toContain('\n\n1. Brake');
    expect(result).toContain('\n\n2. Trail');
  });

  it('inserts break before "Throttle is"', () => {
    const text = 'Summary of findings. Throttle is consistent across the session.';
    const result = formatCoachingText(text);
    expect(result).toContain('\n\nThrottle is');
  });

  it('returns text unchanged when no patterns match', () => {
    const text = 'Simple text without any coaching markers';
    expect(formatCoachingText(text)).toBe(text);
  });
});

// ---------------------------------------------------------------------------
// closeMarkdown (tested via extractActionTitle)
// ---------------------------------------------------------------------------

describe('closeMarkdown via extractActionTitle', () => {
  it('closes unclosed bold markers in truncated text', () => {
    // Build text where first clause has an unclosed **
    // "**Bold start but no close, overflow text" -> clause extraction gets "**Bold start but no close"
    // which has 1 ** -> odd count -> should append **
    const text = '**Bold start but no close, overflow text that continues.';
    const result = extractActionTitle(text);
    // The bold match regex won't match since there's no closing **
    // So it falls through to clause extraction: "**Bold start but no close"
    // closeMarkdown sees 1 ** (odd) -> appends **
    expect(result).toContain('**');
    // Count ** occurrences - should be even
    const boldCount = (result.match(/\*\*/g) || []).length;
    expect(boldCount % 2).toBe(0);
  });

  it('closes unclosed italic markers in truncated text', () => {
    // Text with a lone * that gets truncated by clause extraction
    const text = '*italic start here, then continues with more text.';
    const result = extractActionTitle(text);
    // closeMarkdown should close the lone *
    const withoutBold = result.replace(/\*\*/g, '');
    const italicCount = (withoutBold.match(/\*/g) || []).length;
    expect(italicCount % 2).toBe(0);
  });

  it('does not add extra markers when markdown is already balanced', () => {
    const text = '**Good bold title**, then more text follows here.';
    const result = extractActionTitle(text);
    // Bold title is properly extracted with matching markers
    expect(result).toBe('**Good bold title**');
  });
});
