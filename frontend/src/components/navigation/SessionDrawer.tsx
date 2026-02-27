'use client';

import { useCallback, useMemo, useRef, useState } from 'react';
import { Upload, Sun, CloudDrizzle, CloudRain, Cloud, CheckCircle2, Loader2, Star, AlertTriangle } from 'lucide-react';
import { useUiStore, useSessionStore } from '@/stores';
import { useSessions, useUploadSessions, useDeleteAllSessions } from '@/hooks/useSession';
import { useUnits } from '@/hooks/useUnits';
import { formatLapTime, normalizeScore } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { SessionSummary } from '@/lib/types';

interface TrackGroup {
  trackName: string;
  sessions: SessionSummary[];
  bestLapTime: number | null;
}

function groupSessionsByTrack(sessions: SessionSummary[]): TrackGroup[] {
  const map = new Map<string, SessionSummary[]>();
  for (const s of sessions) {
    const group = map.get(s.track_name) ?? [];
    group.push(s);
    map.set(s.track_name, group);
  }
  return Array.from(map.entries()).map(([trackName, trackSessions]) => {
    const bestLapTime = trackSessions.reduce<number | null>((best, s) => {
      if (s.best_lap_time_s == null) return best;
      return best == null ? s.best_lap_time_s : Math.min(best, s.best_lap_time_s);
    }, null);
    return { trackName, sessions: trackSessions, bestLapTime };
  });
}

function getDateCategory(dateStr: string): string {
  const today = new Date();
  const date = new Date(dateStr);
  const diffDays = Math.floor((today.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return 'This Week';
  if (diffDays < 30) return 'This Month';
  return 'Older';
}

export function SessionDrawer() {
  const open = useUiStore((s) => s.sessionDrawerOpen);
  const toggleDrawer = useUiStore((s) => s.toggleSessionDrawer);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: sessionsData } = useSessions();
  const sessions = sessionsData?.items ?? [];

  const trackGroups = useMemo(() => groupSessionsByTrack(sessions), [sessions]);

  const uploadMutation = useUploadSessions();
  const deleteAllMutation = useDeleteAllSessions();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const fileArray = Array.from(files);
      uploadMutation.mutate(fileArray, {
        onSuccess: (data) => {
          if (data.session_ids.length > 0 && !activeSessionId) {
            setActiveSession(data.session_ids[0]);
          }
        },
      });
    },
    [uploadMutation, activeSessionId, setActiveSession],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  function handleSelectSession(id: string) {
    setActiveSession(id);
    toggleDrawer();
  }

  function handleDeleteAll() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    deleteAllMutation.mutate(undefined, {
      onSuccess: () => {
        setActiveSession(null);
        setConfirmDelete(false);
      },
    });
  }

  return (
    <Sheet open={open} onOpenChange={(v) => { toggleDrawer(); if (!v) setConfirmDelete(false); }}>
      <SheetContent
        side="left"
        className="w-[380px] bg-[var(--bg-surface)] sm:max-w-[380px]"
      >
        <SheetHeader>
          <SheetTitle className="text-[var(--text-primary)]">Sessions</SheetTitle>
          <SheetDescription className="text-[var(--text-secondary)]">
            Upload CSV files or select a session to analyze.
          </SheetDescription>
        </SheetHeader>

        {/* Upload drop zone */}
        <div className="px-4">
          <div
            role="button"
            tabIndex={0}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            className={cn(
              'flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed p-4 transition-colors',
              isDragging
                ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/10'
                : 'border-[var(--cata-border)] hover:border-[var(--text-muted)]',
            )}
          >
            <Upload className="h-5 w-5 text-[var(--text-muted)]" />
            <p className="text-xs text-[var(--text-secondary)]">
              {uploadMutation.isPending
                ? 'Uploading...'
                : 'Drop CSV files here or click to browse'}
            </p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".csv"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>

        {/* Session list grouped by track */}
        <ScrollArea className="min-h-0 flex-1 px-4">
          {sessions.length === 0 && (
            <p className="py-8 text-center text-sm text-[var(--text-muted)]">
              No sessions yet. Upload a CSV to get started.
            </p>
          )}

          {trackGroups.map((group) => {
            // Group sessions within this track by date category
            const dateGroups = new Map<string, SessionSummary[]>();
            for (const s of group.sessions) {
              const cat = getDateCategory(s.session_date);
              const arr = dateGroups.get(cat) ?? [];
              arr.push(s);
              dateGroups.set(cat, arr);
            }

            return (
              <details key={group.trackName} open className="mb-3">
                <summary className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-1.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] transition-colors hover:text-[var(--text-secondary)]">
                  <span className="flex-1">{group.trackName}</span>
                  <span className="text-[10px] font-normal">{group.sessions.length} session{group.sessions.length !== 1 ? 's' : ''}</span>
                </summary>
                <div className="flex flex-col gap-1 pb-2 pl-1">
                  {Array.from(dateGroups.entries()).map(([dateCategory, dateSessions]) => (
                    <div key={dateCategory}>
                      <p className="mb-1 mt-1 text-[10px] font-medium text-[var(--text-muted)]">{dateCategory}</p>
                      {dateSessions.map((session) => {
                        const isPB = group.bestLapTime != null && session.best_lap_time_s === group.bestLapTime;
                        return (
                          <button
                            key={session.session_id}
                            type="button"
                            onClick={() => handleSelectSession(session.session_id)}
                            className={cn(
                              'mb-1 w-full rounded-lg border p-3 text-left transition-colors',
                              session.session_id === activeSessionId
                                ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/10'
                                : 'border-[var(--cata-border)] hover:border-[var(--text-muted)] hover:bg-[var(--bg-elevated)]',
                              (session.session_score ?? session.consistency_score) != null &&
                                Math.round(normalizeScore(session.session_score ?? session.consistency_score!)) < 40 &&
                                'opacity-60',
                            )}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1.5">
                                <p className="text-sm font-semibold text-[var(--text-primary)]">
                                  {session.session_date}
                                </p>
                                {isPB && (
                                  <Star className="h-3 w-3 fill-purple-400 text-purple-400" title="Personal best at this track" />
                                )}
                                <CoachingStatusIcon sessionId={session.session_id} />
                              </div>
                              <SessionScoreBadge score={session.session_score ?? session.consistency_score} />
                            </div>
                            <div className="mt-1 flex items-center gap-1.5">
                              <p className="text-xs text-[var(--text-muted)]">
                                {session.n_laps ?? 0} laps | Best: {formatLapTime(session.best_lap_time_s ?? 0)}
                              </p>
                              {session.tire_model && (
                                <span className="rounded bg-[var(--bg-elevated)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
                                  {session.tire_model}
                                </span>
                              )}
                              <WeatherBadge condition={session.weather_condition} tempC={session.weather_temp_c} />
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </details>
            );
          })}
        </ScrollArea>

        {/* Footer */}
        {sessions.length > 0 && (
          <SheetFooter>
            {confirmDelete ? (
              <div className="flex w-full items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 text-yellow-400" />
                <span className="flex-1 text-xs text-[var(--text-secondary)]">Remove all sessions?</span>
                <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleDeleteAll}
                  disabled={deleteAllMutation.isPending}
                >
                  {deleteAllMutation.isPending ? 'Removing...' : 'Confirm'}
                </Button>
              </div>
            ) : (
              <Button
                variant="destructive"
                size="sm"
                className="w-full"
                onClick={handleDeleteAll}
                disabled={deleteAllMutation.isPending}
              >
                Remove All
              </Button>
            )}
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  );
}

function CoachingStatusIcon({ sessionId }: { sessionId: string }) {
  // Read coaching report status from TanStack Query cache
  // The useCoachingReport hook would need to be per-session,
  // but for the drawer we just show a static icon based on cache state.
  // A full implementation would check queryClient.getQueryData.
  // For now, return null (can be enhanced later).
  return null;
}

function WeatherBadge({
  condition,
  tempC,
}: {
  condition: string | null | undefined;
  tempC: number | null | undefined;
}) {
  const { formatTemp } = useUnits();

  if (condition == null && tempC == null) return null;

  const condLower = (condition ?? '').toLowerCase();
  const Icon =
    condLower === 'clear' || condLower === 'sunny'
      ? Sun
      : condLower === 'drizzle' || condLower === 'light rain'
        ? CloudDrizzle
        : condLower === 'rain' || condLower === 'heavy rain'
          ? CloudRain
          : Cloud;

  return (
    <span className="inline-flex items-center gap-1 rounded bg-[var(--bg-elevated)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
      <Icon className="h-2.5 w-2.5" />
      {tempC != null && formatTemp(tempC)}
    </span>
  );
}

function SessionScoreBadge({ score }: { score: number | null }) {
  const normalized = score != null ? Math.round(normalizeScore(score)) : null;
  const colors =
    normalized == null || normalized < 40
      ? 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30'
      : normalized >= 80
        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
        : normalized >= 60
          ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
          : 'bg-orange-500/20 text-orange-400 border-orange-500/30';
  return (
    <span
      className={cn(
        'inline-flex h-5 min-w-[28px] items-center justify-center rounded border px-1 text-[10px] font-bold',
        colors,
      )}
      title={normalized != null ? `Session Score: ${normalized}` : 'No score available'}
    >
      {normalized != null ? normalized : '--'}
    </span>
  );
}
