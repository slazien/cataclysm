'use client';

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import type { LapData, IdealLapData } from '@/lib/types';

export type PlaybackSpeed = 0.5 | 1 | 2 | 4;

export interface OptimalReplayState {
  /** Current wall-clock time into the replay (seconds) */
  currentTime: number;
  /** Actual lap: index into lapData arrays */
  actualIndex: number;
  /** Ideal lap: distance travelled (metres) — used to derive GPS position */
  idealDistance: number;
  /** Ideal lap: index into idealLap arrays (for speed lookup) */
  idealIndex: number;
  playbackSpeed: PlaybackSpeed;
  isPlaying: boolean;
}

export interface OptimalReplayActions {
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  seek: (fraction: number) => void;
  setSpeed: (s: PlaybackSpeed) => void;
  reset: () => void;
}

/**
 * Build cumulative time array from distance + speed arrays.
 * time[i] = elapsed seconds at distance[i].
 */
function buildTimeArray(distance: number[], speedMph: number[]): Float64Array {
  const n = distance.length;
  const time = new Float64Array(n);
  for (let i = 1; i < n; i++) {
    const ds = distance[i] - distance[i - 1];
    const speedMps = speedMph[i] * 0.44704; // mph → m/s
    const dt = speedMps > 0.1 ? ds / speedMps : 0;
    time[i] = time[i - 1] + dt;
  }
  return time;
}

/**
 * Binary search to find index where arr[index] <= target < arr[index+1].
 */
function bisect(arr: Float64Array | number[], target: number): number {
  let lo = 0;
  let hi = arr.length - 1;
  if (target <= arr[0]) return 0;
  if (target >= arr[hi]) return hi;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (arr[mid] <= target) lo = mid;
    else hi = mid;
  }
  return lo;
}

/**
 * Given distance arrays from actual lap GPS, find the GPS index
 * for a given distance value (from ideal lap progression).
 */
function distanceToGpsIndex(
  distance: number,
  lapDistances: number[],
): number {
  return bisect(lapDistances as unknown as Float64Array, distance);
}

/**
 * Time-based dual replay hook for actual vs ideal lap comparison.
 *
 * Both laps share the same track GPS path (from lapData). A single
 * clock advances in real time × playbackSpeed. At each frame:
 * - Actual lap: time → distance → index in lapData arrays
 * - Ideal lap: time → distance → index in idealLap arrays + GPS index from lapData
 *
 * This creates the "racing ghost" effect where the ideal dot pulls
 * ahead in sections where it's faster.
 */
export function useOptimalReplay(
  lapData: LapData | null | undefined,
  idealLap: IdealLapData | null | undefined,
): OptimalReplayState & OptimalReplayActions {
  const [state, setState] = useState<OptimalReplayState>({
    currentTime: 0,
    actualIndex: 0,
    idealDistance: 0,
    idealIndex: 0,
    playbackSpeed: 1,
    isPlaying: false,
  });

  const stateRef = useRef(state);
  stateRef.current = state;

  const lastTimestampRef = useRef<number | null>(null);
  const rafIdRef = useRef<number>(0);

  // Pre-compute time arrays for both laps
  const actualTime = useMemo(() => {
    if (!lapData?.lap_time_s) return null;
    // lap_time_s is already cumulative time from the telemetry
    return lapData.lap_time_s;
  }, [lapData]);

  const idealTime = useMemo(() => {
    if (!idealLap) return null;
    return buildTimeArray(idealLap.distance_m, idealLap.speed_mph);
  }, [idealLap]);

  // Total duration is the LONGER of the two laps
  const totalDuration = useMemo(() => {
    const actualEnd = actualTime ? actualTime[actualTime.length - 1] : 0;
    const idealEnd = idealTime ? idealTime[idealTime.length - 1] : 0;
    return Math.max(actualEnd, idealEnd);
  }, [actualTime, idealTime]);

  // Animation tick
  const tick = useCallback(
    (timestamp: number) => {
      const s = stateRef.current;
      if (!s.isPlaying || !lapData || !idealLap || !actualTime || !idealTime) return;

      if (lastTimestampRef.current === null) {
        lastTimestampRef.current = timestamp;
        rafIdRef.current = requestAnimationFrame(tick);
        return;
      }

      const dtMs = timestamp - lastTimestampRef.current;
      lastTimestampRef.current = timestamp;

      // Cap dt to 100ms to avoid jumps after tab-switch
      const dtS = Math.min(dtMs / 1000, 0.1) * s.playbackSpeed;
      const newTime = s.currentTime + dtS;

      if (newTime >= totalDuration) {
        // Reached end — compute final state
        const aIdx = lapData.distance_m.length - 1;
        const iIdx = idealLap.distance_m.length - 1;
        setState((prev) => ({
          ...prev,
          currentTime: totalDuration,
          actualIndex: aIdx,
          idealDistance: idealLap.distance_m[iIdx],
          idealIndex: iIdx,
          isPlaying: false,
        }));
        lastTimestampRef.current = null;
        return;
      }

      // Actual lap: time → index via lap_time_s
      const aIdx = bisect(actualTime as unknown as Float64Array, newTime);
      // Ideal lap: time → index via idealTime, then get distance
      const iIdx = bisect(idealTime, newTime);
      const iDist = idealLap.distance_m[iIdx];

      setState((prev) => ({
        ...prev,
        currentTime: newTime,
        actualIndex: aIdx,
        idealDistance: iDist,
        idealIndex: iIdx,
      }));

      rafIdRef.current = requestAnimationFrame(tick);
    },
    [lapData, idealLap, actualTime, idealTime, totalDuration],
  );

  // Start/stop RAF loop
  useEffect(() => {
    if (state.isPlaying) {
      lastTimestampRef.current = null;
      rafIdRef.current = requestAnimationFrame(tick);
    }
    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
  }, [state.isPlaying, tick]);

  const play = useCallback(() => {
    if (!lapData || !idealLap) return;
    setState((prev) => {
      const atEnd = prev.currentTime >= totalDuration - 0.01;
      return { ...prev, isPlaying: true, currentTime: atEnd ? 0 : prev.currentTime };
    });
  }, [lapData, idealLap, totalDuration]);

  const pause = useCallback(() => {
    setState((prev) => ({ ...prev, isPlaying: false }));
  }, []);

  const togglePlay = useCallback(() => {
    setState((prev) => {
      if (prev.isPlaying) return { ...prev, isPlaying: false };
      if (!lapData || !idealLap) return prev;
      const atEnd = prev.currentTime >= totalDuration - 0.01;
      return { ...prev, isPlaying: true, currentTime: atEnd ? 0 : prev.currentTime };
    });
  }, [lapData, idealLap, totalDuration]);

  const seek = useCallback(
    (fraction: number) => {
      const t = Math.max(0, Math.min(fraction, 1)) * totalDuration;
      const aIdx = actualTime ? bisect(actualTime as unknown as Float64Array, t) : 0;
      const iIdx = idealTime ? bisect(idealTime, t) : 0;
      const iDist = idealLap ? idealLap.distance_m[iIdx] : 0;
      setState((prev) => ({
        ...prev,
        currentTime: t,
        actualIndex: aIdx,
        idealDistance: iDist,
        idealIndex: iIdx,
      }));
    },
    [totalDuration, actualTime, idealTime, idealLap],
  );

  const setSpeed = useCallback((speed: PlaybackSpeed) => {
    setState((prev) => ({ ...prev, playbackSpeed: speed }));
  }, []);

  const reset = useCallback(() => {
    setState({
      currentTime: 0,
      actualIndex: 0,
      idealDistance: 0,
      idealIndex: 0,
      playbackSpeed: 1,
      isPlaying: false,
    });
    lastTimestampRef.current = null;
  }, []);

  return {
    ...state,
    play,
    pause,
    togglePlay,
    seek,
    setSpeed,
    reset,
  };
}

/** Utility: map ideal distance to GPS index in actual lap data. */
export { distanceToGpsIndex, bisect, buildTimeArray };
