'use client';

import { useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useLapData, useSessionLaps } from '@/hooks/useSession';
import { useReplay } from '@/hooks/useReplay';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { ReplayTrackMap } from './ReplayTrackMap';
import { SpeedGauge } from './SpeedGauge';
import { GForceDisplay } from './GForceDisplay';
import { ReplayControls } from './ReplayControls';

const G_TRAIL_LENGTH = 30; // number of recent g-force positions to show

/**
 * Main container for the animated lap replay feature.
 *
 * Layout:
 * - Track map (60% width) + side panel (speed gauge + g-force display, 40% width)
 * - Controls bar at the bottom
 *
 * Uses the first selected lap, or the best lap if none selected.
 */
export function LapReplay() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const { data: laps } = useSessionLaps(sessionId);

  // Determine which lap to replay
  const replayLapNumber = useMemo(() => {
    if (selectedLaps.length > 0) return selectedLaps[0];
    if (!laps || laps.length === 0) return null;
    // Find best (shortest) lap
    let best = laps[0];
    for (const lap of laps) {
      if (lap.lap_time_s < best.lap_time_s) best = lap;
    }
    return best.lap_number;
  }, [selectedLaps, laps]);

  const { data: lapData, isLoading } = useLapData(sessionId, replayLapNumber);
  const replay = useReplay(lapData);
  const gTrailRef = useRef<Array<{ lat: number; lon: number }>>([]);

  // Derive current values from lap data + current index
  const current = useMemo(() => {
    if (!lapData || lapData.distance_m.length === 0) {
      return {
        speed: 0,
        maxSpeed: 1,
        lateralG: 0,
        longitudinalG: 0,
        currentDistance: 0,
        totalDistance: 0,
        currentTime: 0,
      };
    }
    const idx = replay.currentIndex;
    return {
      speed: lapData.speed_mph[idx] ?? 0,
      maxSpeed: d3.max(lapData.speed_mph) ?? 1,
      lateralG: lapData.lateral_g[idx] ?? 0,
      longitudinalG: lapData.longitudinal_g[idx] ?? 0,
      currentDistance: lapData.distance_m[idx] ?? 0,
      totalDistance: lapData.distance_m[lapData.distance_m.length - 1] ?? 0,
      currentTime: lapData.lap_time_s[idx] ?? 0,
    };
  }, [lapData, replay.currentIndex]);

  // Build g-force trail (keep last N positions)
  const gTrail = useMemo(() => {
    const trail = gTrailRef.current;
    trail.push({ lat: current.lateralG, lon: current.longitudinalG });
    if (trail.length > G_TRAIL_LENGTH) {
      trail.splice(0, trail.length - G_TRAIL_LENGTH);
    }
    return [...trail];
  }, [current.lateralG, current.longitudinalG]);

  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">No session loaded</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <CircularProgress size={32} />
      </div>
    );
  }

  if (!lapData || lapData.distance_m.length < 2) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">
          {replayLapNumber !== null
            ? 'Insufficient lap data for replay'
            : 'Select a lap to replay'}
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3">
      {/* Main content area */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        {/* Track map -- 60% on desktop */}
        <div className="min-h-[300px] flex-[3] rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-0">
          <ReplayTrackMap lapData={lapData} currentIndex={replay.currentIndex} />
        </div>

        {/* Side panel -- 40% on desktop */}
        <div className="flex flex-[2] flex-col gap-3">
          {/* Speed gauge */}
          <div className="flex items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
            <SpeedGauge speed={current.speed} maxSpeed={current.maxSpeed} />
          </div>

          {/* G-force display */}
          <div className="flex flex-1 items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
            <GForceDisplay
              lateralG={current.lateralG}
              longitudinalG={current.longitudinalG}
              trail={gTrail}
            />
          </div>

          {/* Lap info badge */}
          <div className="flex items-center justify-center gap-2 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-3 py-2">
            <span className="text-xs text-[var(--text-muted)]">Lap</span>
            <span className="font-mono text-sm font-semibold text-[var(--text-primary)]">
              {replayLapNumber}
            </span>
          </div>
        </div>
      </div>

      {/* Controls bar */}
      <ReplayControls
        isPlaying={replay.isPlaying}
        playbackSpeed={replay.playbackSpeed}
        currentIndex={replay.currentIndex}
        maxIndex={lapData.distance_m.length - 1}
        currentDistance={current.currentDistance}
        totalDistance={current.totalDistance}
        currentTime={current.currentTime}
        play={replay.play}
        pause={replay.pause}
        togglePlay={replay.togglePlay}
        seek={replay.seek}
        setSpeed={replay.setSpeed}
        reset={replay.reset}
      />
    </div>
  );
}
