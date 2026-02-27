'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { LapData } from '@/lib/types';

export type PlaybackSpeed = 0.5 | 1 | 2 | 4;

export interface ReplayState {
  currentIndex: number;
  playbackSpeed: PlaybackSpeed;
  isPlaying: boolean;
}

export interface ReplayActions {
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  seek: (index: number) => void;
  setSpeed: (speed: PlaybackSpeed) => void;
  reset: () => void;
}

/**
 * State machine hook for animated lap replay.
 *
 * Uses requestAnimationFrame to advance `currentIndex` through the lap data
 * based on real elapsed time multiplied by playback speed, mapped to the
 * distance domain (each index is ~0.7m).
 *
 * The hook computes how many metres of distance should have been covered
 * given the car's speed at the current position, then advances the index
 * by the corresponding number of data points.
 */
export function useReplay(lapData: LapData | null | undefined): ReplayState & ReplayActions {
  const [state, setState] = useState<ReplayState>({
    currentIndex: 0,
    playbackSpeed: 1,
    isPlaying: false,
  });

  const stateRef = useRef(state);
  stateRef.current = state;

  const lastTimestampRef = useRef<number | null>(null);
  const rafIdRef = useRef<number>(0);
  // Fractional index accumulator for sub-index precision at low speeds
  const fractionalRef = useRef(0);

  const maxIndex = lapData ? lapData.distance_m.length - 1 : 0;

  // Animation loop
  const tick = useCallback(
    (timestamp: number) => {
      const s = stateRef.current;
      if (!s.isPlaying || !lapData || lapData.distance_m.length < 2) return;

      if (lastTimestampRef.current === null) {
        lastTimestampRef.current = timestamp;
        rafIdRef.current = requestAnimationFrame(tick);
        return;
      }

      const dtMs = timestamp - lastTimestampRef.current;
      lastTimestampRef.current = timestamp;

      // Cap dt to 100ms to avoid jumps after tab-switch
      const dtS = Math.min(dtMs / 1000, 0.1) * s.playbackSpeed;

      // speed_mph at current index -> metres per second
      const speedMph = lapData.speed_mph[s.currentIndex] ?? 0;
      const speedMps = speedMph * 0.44704; // 1 mph = 0.44704 m/s

      // How many metres the car travels in dtS seconds
      const distanceCovered = speedMps * dtS;

      // Distance per index (roughly constant at 0.7m, but compute from data)
      const idx = s.currentIndex;
      const nextIdx = Math.min(idx + 1, lapData.distance_m.length - 1);
      const stepM = lapData.distance_m[nextIdx] - lapData.distance_m[idx];
      const effectiveStep = stepM > 0 ? stepM : 0.7;

      // Advance fractional index
      fractionalRef.current += distanceCovered / effectiveStep;
      const steps = Math.floor(fractionalRef.current);
      fractionalRef.current -= steps;

      if (steps > 0) {
        const newIndex = Math.min(s.currentIndex + steps, lapData.distance_m.length - 1);
        if (newIndex >= lapData.distance_m.length - 1) {
          // Reached end
          setState((prev) => ({
            ...prev,
            currentIndex: lapData.distance_m.length - 1,
            isPlaying: false,
          }));
          lastTimestampRef.current = null;
          fractionalRef.current = 0;
          return;
        }
        setState((prev) => ({ ...prev, currentIndex: newIndex }));
      }

      rafIdRef.current = requestAnimationFrame(tick);
    },
    [lapData],
  );

  // Start/stop RAF loop based on isPlaying
  useEffect(() => {
    if (state.isPlaying) {
      lastTimestampRef.current = null;
      fractionalRef.current = 0;
      rafIdRef.current = requestAnimationFrame(tick);
    }
    return () => {
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [state.isPlaying, tick]);

  const play = useCallback(() => {
    if (!lapData || lapData.distance_m.length < 2) return;
    setState((prev) => {
      // If at end, restart from beginning
      const atEnd = prev.currentIndex >= lapData.distance_m.length - 1;
      return { ...prev, isPlaying: true, currentIndex: atEnd ? 0 : prev.currentIndex };
    });
  }, [lapData]);

  const pause = useCallback(() => {
    setState((prev) => ({ ...prev, isPlaying: false }));
  }, []);

  const togglePlay = useCallback(() => {
    setState((prev) => {
      if (prev.isPlaying) {
        return { ...prev, isPlaying: false };
      }
      if (!lapData || lapData.distance_m.length < 2) return prev;
      const atEnd = prev.currentIndex >= lapData.distance_m.length - 1;
      return { ...prev, isPlaying: true, currentIndex: atEnd ? 0 : prev.currentIndex };
    });
  }, [lapData]);

  const seek = useCallback(
    (index: number) => {
      const clamped = Math.max(0, Math.min(index, maxIndex));
      setState((prev) => ({ ...prev, currentIndex: clamped }));
      fractionalRef.current = 0;
    },
    [maxIndex],
  );

  const setSpeed = useCallback((speed: PlaybackSpeed) => {
    setState((prev) => ({ ...prev, playbackSpeed: speed }));
  }, []);

  const reset = useCallback(() => {
    setState({ currentIndex: 0, playbackSpeed: 1, isPlaying: false });
    fractionalRef.current = 0;
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
