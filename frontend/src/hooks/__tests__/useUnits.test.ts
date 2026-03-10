import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useUnits } from '../useUnits';
import { useUiStore } from '@/stores';

// MPH_TO_KMH constant matches the value in @/lib/constants
const MPH_TO_KMH = 1.60934;

// Helpers for expected values
const toKmh = (mph: number) => mph * MPH_TO_KMH;
const toFt = (m: number) => m * 3.28084;
const toF = (c: number) => (c * 9) / 5 + 32;

describe('useUnits', () => {
  beforeEach(() => {
    // Reset to imperial (the store default) before each test
    useUiStore.setState({ unitPreference: 'imperial' });
  });

  // ---------------------------------------------------------------------------
  // isMetric flag
  // ---------------------------------------------------------------------------
  describe('isMetric', () => {
    it('returns false when unit preference is imperial', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.isMetric).toBe(false);
    });

    it('returns true when unit preference is metric', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.isMetric).toBe(true);
    });
  });

  // ---------------------------------------------------------------------------
  // Unit label properties
  // ---------------------------------------------------------------------------
  describe('unit label strings', () => {
    it('returns mph and ft labels in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.speedUnit).toBe('mph');
      expect(result.current.distanceUnit).toBe('ft');
      expect(result.current.tempUnit).toBe('°F');
    });

    it('returns km/h and m labels in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.speedUnit).toBe('km/h');
      expect(result.current.distanceUnit).toBe('m');
      expect(result.current.tempUnit).toBe('°C');
    });
  });

  // ---------------------------------------------------------------------------
  // formatSpeed
  // ---------------------------------------------------------------------------
  describe('formatSpeed', () => {
    it('formats speed in mph with default 1 decimal in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatSpeed(100)).toBe('100.0 mph');
    });

    it('formats speed in km/h with default 1 decimal in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      const expected = `${toKmh(100).toFixed(1)} km/h`;
      expect(result.current.formatSpeed(100)).toBe(expected);
    });

    it('respects custom decimals parameter in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatSpeed(80.555, 2)).toBe('80.56 mph');
    });

    it('respects custom decimals parameter in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatSpeed(80, 0)).toBe(`${Math.round(toKmh(80))} km/h`);
    });

    it('handles zero speed in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatSpeed(0)).toBe('0.0 mph');
    });

    it('handles zero speed in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatSpeed(0)).toBe('0.0 km/h');
    });

    it('handles negative speed values', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatSpeed(-10)).toBe('-10.0 mph');
    });
  });

  // ---------------------------------------------------------------------------
  // formatDistance
  // ---------------------------------------------------------------------------
  describe('formatDistance', () => {
    it('formats distance in ft with 0 decimals in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatDistance(100)).toBe(`${Math.round(toFt(100))} ft`);
    });

    it('formats distance in m with 0 decimals in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatDistance(100)).toBe('100 m');
    });

    it('respects custom decimals in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatDistance(10, 2)).toBe(`${toFt(10).toFixed(2)} ft`);
    });

    it('respects custom decimals in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatDistance(10.5, 1)).toBe('10.5 m');
    });

    it('handles zero distance', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatDistance(0)).toBe('0 ft');
    });

    it('handles zero distance in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatDistance(0)).toBe('0 m');
    });
  });

  // ---------------------------------------------------------------------------
  // convertSpeed
  // ---------------------------------------------------------------------------
  describe('convertSpeed', () => {
    it('returns mph value unchanged in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertSpeed(60)).toBe(60);
    });

    it('converts mph to km/h in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertSpeed(60)).toBeCloseTo(toKmh(60), 5);
    });

    it('handles zero in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertSpeed(0)).toBe(0);
    });

    it('handles zero in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertSpeed(0)).toBe(0);
    });

    it('handles fractional mph values', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertSpeed(0.5)).toBeCloseTo(toKmh(0.5), 5);
    });
  });

  // ---------------------------------------------------------------------------
  // convertDistance
  // ---------------------------------------------------------------------------
  describe('convertDistance', () => {
    it('returns meters unchanged in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertDistance(200)).toBe(200);
    });

    it('converts meters to feet in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertDistance(100)).toBeCloseTo(toFt(100), 5);
    });

    it('handles zero distance', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertDistance(0)).toBe(0);
    });
  });

  // ---------------------------------------------------------------------------
  // formatTemp
  // ---------------------------------------------------------------------------
  describe('formatTemp', () => {
    it('formats temperature in Celsius with 0 decimals in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatTemp(20)).toBe('20°C');
    });

    it('formats temperature in Fahrenheit with 0 decimals in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatTemp(100)).toBe(`${toF(100).toFixed(0)}°F`);
    });

    it('converts 0 Celsius to 32 Fahrenheit', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatTemp(0)).toBe('32°F');
    });

    it('converts 100 Celsius to 212 Fahrenheit', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatTemp(100)).toBe('212°F');
    });

    it('respects custom decimals in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatTemp(36.6, 1)).toBe('36.6°C');
    });

    it('respects custom decimals in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatTemp(20, 1)).toBe(`${toF(20).toFixed(1)}°F`);
    });

    it('handles negative Celsius values', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatTemp(-10)).toBe('-10°C');
    });

    it('handles negative Celsius converted to Fahrenheit', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      // -40 C = -40 F (the crossover point)
      expect(result.current.formatTemp(-40)).toBe('-40°F');
    });
  });

  // ---------------------------------------------------------------------------
  // convertTemp
  // ---------------------------------------------------------------------------
  describe('convertTemp', () => {
    it('returns Celsius unchanged in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertTemp(25)).toBe(25);
    });

    it('converts Celsius to Fahrenheit in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertTemp(0)).toBeCloseTo(32, 5);
      expect(result.current.convertTemp(100)).toBeCloseTo(212, 5);
    });

    it('handles -40 crossover point', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.convertTemp(-40)).toBeCloseTo(-40, 5);
    });
  });

  // ---------------------------------------------------------------------------
  // resolveSpeed (coaching text marker substitution)
  // ---------------------------------------------------------------------------
  describe('resolveSpeed', () => {
    it('leaves imperial text unchanged in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      const text = 'Brake at {{speed:80}} before turn 5.';
      expect(result.current.resolveSpeed(text)).toBe('Brake at 80 mph before turn 5.');
    });

    it('converts {{speed:N}} markers to km/h in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      const text = 'Target {{speed:60}} through the corner.';
      const expected = `Target ${(60 * MPH_TO_KMH).toFixed(0)} km/h through the corner.`;
      expect(result.current.resolveSpeed(text)).toBe(expected);
    });

    it('converts legacy bare "N mph" text to km/h in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      const text = 'Entry speed of 42 mph is optimal.';
      const kmh = (42 * MPH_TO_KMH).toFixed(0);
      expect(result.current.resolveSpeed(text)).toContain(`${kmh} km/h`);
    });

    it('leaves legacy "N mph" text unchanged in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      const text = 'Entry speed of 42 mph is optimal.';
      expect(result.current.resolveSpeed(text)).toBe('Entry speed of 42 mph is optimal.');
    });

    it('handles text with no speed markers', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.resolveSpeed('Turn in earlier.')).toBe('Turn in earlier.');
    });

    it('handles empty string', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.resolveSpeed('')).toBe('');
    });

    it('handles multiple speed markers in a single string', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      const text = 'Brake at {{speed:80}}, entry {{speed:50}}.';
      const r = result.current.resolveSpeed(text);
      expect(r).toContain('km/h');
      expect(r).not.toContain('{{speed:');
    });

    it('converts meter distances in imperial mode coaching text', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      const text = 'Try braking 98m past the pedestrian bridge.';
      expect(result.current.resolveSpeed(text)).toBe(
        'Try braking 322 ft past the pedestrian bridge.',
      );
    });
  });

  // ---------------------------------------------------------------------------
  // formatLength
  // ---------------------------------------------------------------------------
  describe('formatLength', () => {
    it('formats >= 1000m as km in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatLength(2500)).toBe('2.50 km');
    });

    it('formats < 1000m as rounded meters in metric mode', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatLength(750)).toBe('750 m');
    });

    it('formats >= 0.1 mi as miles in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      // 500m = 0.3107 mi
      expect(result.current.formatLength(500)).toBe('0.31 mi');
    });

    it('formats < 0.1 mi as feet in imperial mode', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      // 10m = 32.8084 ft, < 0.1 mi
      expect(result.current.formatLength(10)).toBe('33 ft');
    });

    it('respects custom decimals for km', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatLength(3500, 1)).toBe('3.5 km');
    });

    it('respects custom decimals for miles', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      // 2000m = 1.24274 mi
      expect(result.current.formatLength(2000, 1)).toBe('1.2 mi');
    });

    it('formats exactly 1000m in metric', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatLength(1000)).toBe('1.00 km');
    });

    it('handles zero distance in metric', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatLength(0)).toBe('0 m');
    });

    it('handles zero distance in imperial', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      expect(result.current.formatLength(0)).toBe('0 ft');
    });
  });

  // ---------------------------------------------------------------------------
  // Memoization — callbacks must not change when isMetric is unchanged
  // ---------------------------------------------------------------------------
  describe('memoization', () => {
    it('formatSpeed callback is stable across re-renders when preference unchanged', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result, rerender } = renderHook(() => useUnits());
      const first = result.current.formatSpeed;
      rerender();
      expect(result.current.formatSpeed).toBe(first);
    });

    it('formatSpeed callback changes when preference changes', () => {
      useUiStore.setState({ unitPreference: 'imperial' });
      const { result } = renderHook(() => useUnits());
      const imperialFn = result.current.formatSpeed;
      act(() => {
        useUiStore.setState({ unitPreference: 'metric' });
      });
      // The new preference produces a different memoized function
      expect(result.current.formatSpeed).not.toBe(imperialFn);
    });

    it('convertSpeed callback is stable across re-renders', () => {
      useUiStore.setState({ unitPreference: 'metric' });
      const { result, rerender } = renderHook(() => useUnits());
      const first = result.current.convertSpeed;
      rerender();
      expect(result.current.convertSpeed).toBe(first);
    });
  });
});
