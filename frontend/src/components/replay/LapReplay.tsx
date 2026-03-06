'use client';

import { useCallback, useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useLapData, useSessionLaps } from '@/hooks/useSession';
import { useReplay } from '@/hooks/useReplay';
import { useReplayRecorder } from '@/hooks/useReplayRecorder';
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
 *
 * Supports video recording of the track map canvas via the MediaRecorder API.
 * When recording, a red dot indicator appears in the top-left corner of the
 * track map viewport.
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
  const recorder = useReplayRecorder();
  const gTrailRef = useRef<Array<{ lat: number; lon: number }>>([]);
  const trackCanvasRef = useRef<HTMLCanvasElement>(null);

  // Track whether we started recording (to auto-stop when replay ends)
  const wasRecordingRef = useRef(false);

  // Auto-stop recording when replay reaches the end
  const { isRecording, stopRecording: stopRec } = recorder;
  useEffect(() => {
    if (isRecording && wasRecordingRef.current) {
      // Replay stopped playing and we were recording -- replay has ended
      if (!replay.isPlaying && replay.currentIndex >= (lapData?.distance_m.length ?? 1) - 1) {
        stopRec();
        wasRecordingRef.current = false;
      }
    }
  }, [replay.isPlaying, replay.currentIndex, isRecording, stopRec, lapData]);

  // Handle start recording: reset to beginning, start recording, then play
  const handleStartRecording = useCallback(() => {
    const canvas = trackCanvasRef.current;
    if (!canvas) return;

    // Clear any previous download
    recorder.clearRecording();

    // Reset replay to beginning
    replay.reset();

    // Small delay to ensure reset takes effect before starting recording
    requestAnimationFrame(() => {
      recorder.startRecording(canvas);
      wasRecordingRef.current = true;
      // Start playback
      replay.play();
    });
  }, [recorder, replay]);

  // Handle stop recording manually
  const handleStopRecording = useCallback(() => {
    recorder.stopRecording();
    wasRecordingRef.current = false;
    replay.pause();
  }, [recorder, replay]);

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
      lateralG: lapData.lateral_g?.[idx] ?? 0,
      longitudinalG: lapData.longitudinal_g?.[idx] ?? 0,
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
        <div className="relative min-h-[300px] flex-[3] rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-0">
          <ReplayTrackMap
            lapData={lapData}
            currentIndex={replay.currentIndex}
            canvasRef={trackCanvasRef}
          />

          {/* Recording indicator -- pulsing red dot */}
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
