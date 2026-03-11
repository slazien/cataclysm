'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useLapData, useSessionLaps } from '@/hooks/useSession';
import { useCorners, useIdealLap } from '@/hooks/useAnalysis';
import { useReplay } from '@/hooks/useReplay';
import { useOptimalReplay } from '@/hooks/useOptimalReplay';
import { useReplayRecorder } from '@/hooks/useReplayRecorder';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { ReplayTrackMap } from './ReplayTrackMap';
import { OptimalReplayMap } from './OptimalReplayMap';
import { SpeedGauge } from './SpeedGauge';
import { GForceDisplay } from './GForceDisplay';
import { ReplayControls } from './ReplayControls';

const G_TRAIL_LENGTH = 30;

type ReplayMode = 'single' | 'optimal';

/**
 * Main container for the animated lap replay feature.
 *
 * Supports two modes:
 * - "Single Lap": Original replay of one lap with speed coloring + g-force
 * - "vs Ideal": Dual-trail animation showing actual vs ideal (stitched best
 *   segments) with racing ghost dots and distance gap indicator
 */
export function LapReplay() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const { data: laps } = useSessionLaps(sessionId);
  const [mode, setMode] = useState<ReplayMode>('single');

  // Determine which lap to replay
  const replayLapNumber = useMemo(() => {
    if (selectedLaps.length > 0) return selectedLaps[0];
    if (!laps || laps.length === 0) return null;
    let best = laps[0];
    for (const lap of laps) {
      if (lap.lap_time_s < best.lap_time_s) best = lap;
    }
    return best.lap_number;
  }, [selectedLaps, laps]);

  const { data: lapData, isLoading } = useLapData(sessionId, replayLapNumber);
  const { data: idealLap } = useIdealLap(mode === 'optimal' ? sessionId : null);
  const { data: corners } = useCorners(mode === 'optimal' ? sessionId : null);

  // Single-lap replay state
  const replay = useReplay(mode === 'single' ? lapData : null);
  // Optimal comparison replay state
  const optReplay = useOptimalReplay(
    mode === 'optimal' ? lapData : null,
    mode === 'optimal' ? idealLap : null,
  );

  const recorder = useReplayRecorder();
  const gTrailRef = useRef<Array<{ lat: number; lon: number }>>([]);
  const trackCanvasRef = useRef<HTMLCanvasElement>(null);
  const wasRecordingRef = useRef(false);

  // Active replay controls (shared interface)
  const activeReplay = mode === 'single' ? replay : optReplay;
  const activeIndex = mode === 'single' ? replay.currentIndex : optReplay.actualIndex;

  // Auto-stop recording when replay reaches the end
  const { isRecording, stopRecording: stopRec } = recorder;
  useEffect(() => {
    if (isRecording && wasRecordingRef.current) {
      if (!activeReplay.isPlaying) {
        stopRec();
        wasRecordingRef.current = false;
      }
    }
  }, [activeReplay.isPlaying, isRecording, stopRec]);

  const handleStartRecording = useCallback(() => {
    const canvas = trackCanvasRef.current;
    if (!canvas) return;
    recorder.clearRecording();
    activeReplay.reset();
    requestAnimationFrame(() => {
      recorder.startRecording(canvas);
      wasRecordingRef.current = true;
      activeReplay.play();
    });
  }, [recorder, activeReplay]);

  const handleStopRecording = useCallback(() => {
    recorder.stopRecording();
    wasRecordingRef.current = false;
    activeReplay.pause();
  }, [recorder, activeReplay]);

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
        idealSpeed: null as number | null,
      };
    }
    const idx = activeIndex;
    const idealSpd =
      mode === 'optimal' && idealLap
        ? (idealLap.speed_mph[optReplay.idealIndex] ?? null)
        : null;
    return {
      speed: lapData.speed_mph[idx] ?? 0,
      maxSpeed: d3.max(lapData.speed_mph) ?? 1,
      lateralG: lapData.lateral_g?.[idx] ?? 0,
      longitudinalG: lapData.longitudinal_g?.[idx] ?? 0,
      currentDistance: lapData.distance_m[idx] ?? 0,
      totalDistance: lapData.distance_m[lapData.distance_m.length - 1] ?? 0,
      currentTime: lapData.lap_time_s[idx] ?? 0,
      idealSpeed: idealSpd,
    };
  }, [lapData, activeIndex, mode, idealLap, optReplay.idealIndex]);

  // Build g-force trail
  const gTrail = useMemo(() => {
    const trail = gTrailRef.current;
    trail.push({ lat: current.lateralG, lon: current.longitudinalG });
    if (trail.length > G_TRAIL_LENGTH) {
      trail.splice(0, trail.length - G_TRAIL_LENGTH);
    }
    return [...trail];
  }, [current.lateralG, current.longitudinalG]);

  // Reset g-trail when switching modes
  useEffect(() => {
    gTrailRef.current = [];
  }, [mode]);

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

  // Build scrub props for ReplayControls based on mode
  const controlsMaxIndex = lapData.distance_m.length - 1;
  const controlsCurrentIndex = activeIndex;
  // For optimal mode, seek takes fraction (0-1); for single mode, seek takes index
  const handleSeek =
    mode === 'single'
      ? replay.seek
      : (idx: number) => optReplay.seek(idx / controlsMaxIndex);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3">
      {/* Mode toggle */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => { setMode('single'); activeReplay.reset(); }}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
            mode === 'single'
              ? 'bg-[var(--bg-elevated)] text-[var(--text-primary)]'
              : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
          }`}
        >
          Single Lap
        </button>
        <button
          type="button"
          onClick={() => { setMode('optimal'); activeReplay.reset(); }}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
            mode === 'optimal'
              ? 'bg-amber-500/20 text-amber-400'
              : 'text-[var(--text-secondary)] hover:text-amber-400'
          }`}
        >
          vs Ideal
        </button>
      </div>

      {/* Main content area */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        {/* Track map -- 60% on desktop */}
        <div className="relative min-h-[300px] flex-[3] rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-0">
          {mode === 'single' ? (
            <ReplayTrackMap
              lapData={lapData}
              currentIndex={replay.currentIndex}
              canvasRef={trackCanvasRef}
            />
          ) : idealLap && corners ? (
            <OptimalReplayMap
              lapData={lapData}
              idealLap={idealLap}
              corners={corners}
              actualIndex={optReplay.actualIndex}
              idealDistance={optReplay.idealDistance}
              idealIndex={optReplay.idealIndex}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <CircularProgress size={24} />
              <span className="ml-2 text-xs text-[var(--text-secondary)]">Loading ideal lap…</span>
            </div>
          )}

          {/* Recording indicator */}
          {recorder.isRecording && (
            <div className="absolute left-3 top-3 flex items-center gap-1.5">
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
              </span>
              <span className="text-xs font-medium text-red-400">REC</span>
            </div>
          )}
        </div>

        {/* Side panel -- 40% on desktop */}
        <div className="flex flex-[2] flex-col gap-3">
          {/* Speed gauge (with optional ideal speed) */}
          <div className="flex items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
            <div className="flex flex-col items-center gap-1">
              <SpeedGauge speed={current.speed} maxSpeed={current.maxSpeed} />
              {current.idealSpeed != null && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-amber-400">
                    Ideal: {Math.round(current.idealSpeed)} mph
                  </span>
                  <span
                    className={`font-semibold ${
                      current.speed >= current.idealSpeed
                        ? 'text-[var(--color-throttle)]'
                        : 'text-[var(--color-brake)]'
                    }`}
                  >
                    {current.speed >= current.idealSpeed ? '+' : ''}
                    {Math.round(current.speed - current.idealSpeed)} mph
                  </span>
                </div>
              )}
            </div>
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
            <span className="text-xs text-[var(--text-secondary)]">Lap</span>
            <span className="font-mono text-sm font-semibold text-[var(--text-primary)]">
              {replayLapNumber}
            </span>
            {mode === 'optimal' && (
              <span className="text-xs text-amber-400">vs Ideal</span>
            )}
          </div>
        </div>
      </div>

      {/* Controls bar */}
      <ReplayControls
        isPlaying={activeReplay.isPlaying}
        playbackSpeed={activeReplay.playbackSpeed}
        currentIndex={controlsCurrentIndex}
        maxIndex={controlsMaxIndex}
        currentDistance={current.currentDistance}
        totalDistance={current.totalDistance}
        currentTime={current.currentTime}
        play={activeReplay.play}
        pause={activeReplay.pause}
        togglePlay={activeReplay.togglePlay}
        seek={handleSeek}
        setSpeed={activeReplay.setSpeed}
        reset={activeReplay.reset}
        recording={{
          isRecordingSupported: recorder.isSupported,
          isRecording: recorder.isRecording,
          downloadUrl: recorder.downloadUrl,
          fileExtension: recorder.fileExtension,
          onStartRecording: handleStartRecording,
          onStopRecording: handleStopRecording,
          onClearRecording: recorder.clearRecording,
        }}
      />
    </div>
  );
}
