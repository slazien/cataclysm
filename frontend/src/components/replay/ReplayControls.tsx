'use client';

import { useCallback } from 'react';
import { Play, Pause, SkipBack, Video, Square, Download } from 'lucide-react';
import { useUnits } from '@/hooks/useUnits';
import type { PlaybackSpeed, ReplayActions, ReplayState } from '@/hooks/useReplay';

interface RecordingProps {
  /** Whether MediaRecorder is supported in this browser. */
  isRecordingSupported: boolean;
  /** Whether a recording is currently in progress. */
  isRecording: boolean;
  /** Blob URL for the completed recording download. */
  downloadUrl: string | null;
  /** File extension for the download filename (e.g. "webm"). */
  fileExtension: string;
  /** Called when user clicks Record. */
  onStartRecording: () => void;
  /** Called when user clicks Stop Recording. */
  onStopRecording: () => void;
  /** Called to clear the download after user downloads. */
  onClearRecording: () => void;
}

interface ReplayControlsProps extends ReplayState, ReplayActions {
  maxIndex: number;
  currentDistance: number;
  totalDistance: number;
  currentTime: number;
  recording?: RecordingProps;
}

const SPEED_OPTIONS: PlaybackSpeed[] = [0.5, 1, 2, 4];

// formatDistance defined via useUnits hook in the component

function formatTime(s: number): string {
  const mins = Math.floor(s / 60);
  const secs = s - mins * 60;
  return `${mins}:${secs.toFixed(1).padStart(4, '0')}`;
}

/**
 * Playback controls bar for the lap replay feature.
 *
 * - Play / Pause toggle button
 * - Reset (skip back) button
 * - Scrubber (range input) mapped to distance index
 * - Speed selector buttons (0.5x / 1x / 2x / 4x)
 * - Current distance and time readout
 * - Record / Stop Recording / Download buttons (when recording props provided)
 */
export function ReplayControls({
  isPlaying,
  playbackSpeed,
  currentIndex,
  maxIndex,
  currentDistance,
  totalDistance,
  currentTime,
  togglePlay,
  seek,
  setSpeed,
  reset,
  recording,
}: ReplayControlsProps) {
  const { formatLength } = useUnits();
  const handleScrub = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      seek(parseInt(e.target.value, 10));
    },
    [seek],
  );

  const progress = maxIndex > 0 ? (currentIndex / maxIndex) * 100 : 0;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3">
      {/* Scrubber */}
      <div className="relative">
        <input
          type="range"
          min={0}
          max={maxIndex}
          value={currentIndex}
          onChange={handleScrub}
          className="replay-scrubber w-full cursor-pointer"
          style={
            {
              '--progress': `${progress}%`,
            } as React.CSSProperties
          }
        />
      </div>

      {/* Controls row — stacks to two rows on narrow viewports */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        {/* Row 1 (mobile) / Left (desktop): play controls + distance/time */}
        <div className="flex items-center gap-2">
          <button
            onClick={reset}
            className="flex h-11 w-11 items-center justify-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
            title="Reset"
          >
            <SkipBack size={16} />
          </button>
          <button
            onClick={togglePlay}
            className="flex h-11 w-11 items-center justify-center rounded-full bg-[var(--cata-accent,#3b82f6)] text-white transition-transform hover:scale-105 active:scale-95"
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
          </button>

          {/* Distance / time readout — inline with play controls on mobile */}
          <div className="flex items-center gap-1.5 font-mono text-xs text-[var(--text-secondary)]">
            <span>{formatLength(currentDistance)}</span>
            <span>/</span>
            <span>{formatLength(totalDistance)}</span>
            <span className="mx-0.5">|</span>
            <span>{formatTime(currentTime)}</span>
          </div>
        </div>

        {/* Row 2 (mobile) / Right (desktop): speed selector + recording controls */}
        {/* pr-16 sm:pr-0: reserve space on the right on mobile so the FAB doesn't overlap Record */}
        <div className="flex items-center gap-2 pr-16 sm:pr-0">
          <div className="flex items-center gap-1">
            {SPEED_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`flex min-h-[44px] items-center rounded px-2 font-mono text-xs transition-colors ${
                  playbackSpeed === s
                    ? 'bg-[var(--cata-accent,#3b82f6)] text-white'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>

          {/* Recording controls */}
          {recording?.isRecordingSupported && (
            <div className="flex items-center gap-1.5 border-l border-[var(--cata-border)] pl-2">
              {recording.isRecording ? (
                <button
                  onClick={recording.onStopRecording}
                  className="flex min-h-[44px] items-center gap-1.5 rounded-md bg-red-600/20 px-2.5 text-red-400 transition-colors hover:bg-red-600/30"
                  title="Stop Recording"
                >
                  <Square size={14} fill="currentColor" />
                  <span className="text-xs font-medium">Stop</span>
                </button>
              ) : recording.downloadUrl ? (
                <a
                  href={recording.downloadUrl}
                  download={`lap-replay.${recording.fileExtension}`}
                  className="flex min-h-[44px] items-center gap-1.5 rounded-md bg-green-600/20 px-2.5 text-green-400 transition-colors hover:bg-green-600/30"
                  title="Download Recording"
                  onClick={recording.onClearRecording}
                >
                  <Download size={14} />
                  <span className="text-xs font-medium">Save</span>
                </a>
              ) : (
                <button
                  onClick={recording.onStartRecording}
                  className="flex min-h-[44px] items-center gap-1.5 rounded-md px-2.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                  title="Record Replay"
                >
                  <Video size={14} />
                  <span className="text-xs font-medium">Record</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
