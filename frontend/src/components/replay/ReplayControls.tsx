'use client';

import { useCallback } from 'react';
import { Play, Pause, SkipBack } from 'lucide-react';
import type { PlaybackSpeed, ReplayActions, ReplayState } from '@/hooks/useReplay';

interface ReplayControlsProps extends ReplayState, ReplayActions {
  maxIndex: number;
  currentDistance: number;
  totalDistance: number;
  currentTime: number;
}

const SPEED_OPTIONS: PlaybackSpeed[] = [0.5, 1, 2, 4];

function formatDistance(m: number): string {
  if (m >= 1000) {
    return `${(m / 1000).toFixed(2)} km`;
  }
  return `${Math.round(m)} m`;
}

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
}: ReplayControlsProps) {
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

      {/* Controls row */}
      <div className="flex items-center justify-between gap-3">
        {/* Left: play controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={reset}
            className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
            title="Reset"
          >
            <SkipBack size={16} />
          </button>
          <button
            onClick={togglePlay}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--cata-accent,#3b82f6)] text-white transition-transform hover:scale-105 active:scale-95"
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
          </button>
        </div>

        {/* Center: distance / time readout */}
        <div className="flex items-center gap-3 font-mono text-xs text-[var(--text-secondary)]">
          <span>{formatDistance(currentDistance)}</span>
          <span className="text-[var(--text-muted)]">/</span>
          <span>{formatDistance(totalDistance)}</span>
          <span className="mx-1 text-[var(--text-muted)]">|</span>
          <span>{formatTime(currentTime)}</span>
        </div>

        {/* Right: speed selector */}
        <div className="flex items-center gap-1">
          {SPEED_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className={`rounded px-2 py-0.5 font-mono text-xs transition-colors ${
                playbackSpeed === s
                  ? 'bg-[var(--cata-accent,#3b82f6)] text-white'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]'
              }`}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
