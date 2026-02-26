'use client';

import { useCallback } from 'react';
import { useUiStore } from '@/stores';
import { MPH_TO_KMH } from '@/lib/constants';

/**
 * Hook returning unit-aware formatters bound to the current unitPreference.
 * Components call these and automatically get the right units.
 */
export function useUnits() {
  const isMetric = useUiStore((s) => s.unitPreference === 'metric');

  const formatSpeed = useCallback(
    (mph: number, decimals = 1): string => {
      if (isMetric) {
        return `${(mph * MPH_TO_KMH).toFixed(decimals)} km/h`;
      }
      return `${mph.toFixed(decimals)} mph`;
    },
    [isMetric],
  );

  const formatDistance = useCallback(
    (meters: number, decimals = 0): string => {
      if (!isMetric) {
        // Convert m to ft
        return `${(meters * 3.28084).toFixed(decimals)} ft`;
      }
      return `${meters.toFixed(decimals)} m`;
    },
    [isMetric],
  );

  /** Speed unit label (for chart axes) */
  const speedUnit = isMetric ? 'km/h' : 'mph';

  /** Distance unit label */
  const distanceUnit = isMetric ? 'm' : 'ft';

  /** Convert mph value to display unit */
  const convertSpeed = useCallback(
    (mph: number): number => (isMetric ? mph * MPH_TO_KMH : mph),
    [isMetric],
  );

  /** Convert meters to display unit */
  const convertDistance = useCallback(
    (meters: number): number => (isMetric ? meters : meters * 3.28084),
    [isMetric],
  );

  /** Format a Celsius temperature with unit label */
  const formatTemp = useCallback(
    (celsius: number, decimals = 0): string => {
      if (!isMetric) {
        return `${(celsius * 9 / 5 + 32).toFixed(decimals)}°F`;
      }
      return `${celsius.toFixed(decimals)}°C`;
    },
    [isMetric],
  );

  /** Convert Celsius to display unit */
  const convertTemp = useCallback(
    (celsius: number): number => (isMetric ? celsius : celsius * 9 / 5 + 32),
    [isMetric],
  );

  /** Temperature unit label */
  const tempUnit = isMetric ? '°C' : '°F';

  return {
    isMetric,
    formatSpeed,
    formatDistance,
    formatTemp,
    speedUnit,
    distanceUnit,
    tempUnit,
    convertSpeed,
    convertDistance,
    convertTemp,
  };
}
