'use client';

import { useCallback, useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { useUiStore, useSessionStore } from '@/stores';
import { useSessions, useUploadSessions, useDeleteAllSessions } from '@/hooks/useSession';
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

export function SessionDrawer() {
  const open = useUiStore((s) => s.sessionDrawerOpen);
  const toggleDrawer = useUiStore((s) => s.toggleSessionDrawer);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSession = useSessionStore((s) => s.setActiveSession);

  const { data: sessionsData } = useSessions();
  const sessions = sessionsData?.items ?? [];

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
    deleteAllMutation.mutate(undefined, {
      onSuccess: () => {
        setActiveSession(null);
      },
    });
  }

  return (
    <Sheet open={open} onOpenChange={toggleDrawer}>
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

        {/* Session list */}
        <ScrollArea className="min-h-0 flex-1 px-4">
          <div className="flex flex-col gap-2 pb-2">
            {sessions.length === 0 && (
              <p className="py-8 text-center text-sm text-[var(--text-muted)]">
                No sessions yet. Upload a CSV to get started.
              </p>
            )}
            {sessions.map((session) => (
              <button
                key={session.session_id}
                type="button"
                onClick={() => handleSelectSession(session.session_id)}
                className={cn(
                  'w-full rounded-lg border p-3 text-left transition-colors',
                  session.session_id === activeSessionId
                    ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/10'
                    : 'border-[var(--cata-border)] hover:border-[var(--text-muted)] hover:bg-[var(--bg-elevated)]',
                  session.consistency_score != null &&
                    Math.round(normalizeScore(session.consistency_score)) < 40 &&
                    'opacity-60',
                )}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">
                    {session.track_name}
                  </p>
                  <SessionScoreBadge score={session.consistency_score} />
                </div>
                <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                  {session.session_date}
                </p>
                <div className="mt-1 flex items-center gap-1.5">
                  <p className="text-xs text-[var(--text-muted)]">
                    {session.n_laps ?? 0} laps | Best: {formatLapTime(session.best_lap_time_s ?? 0)}
                  </p>
                  {session.tire_model && (
                    <span className="rounded bg-[var(--bg-elevated)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
                      {session.tire_model}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>

        {/* Footer */}
        {sessions.length > 0 && (
          <SheetFooter>
            <Button
              variant="destructive"
              size="sm"
              className="w-full"
              onClick={handleDeleteAll}
              disabled={deleteAllMutation.isPending}
            >
              {deleteAllMutation.isPending ? 'Removing...' : 'Remove All'}
            </Button>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
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
          ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
          : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
  return (
    <span
      className={cn(
        'inline-flex h-5 min-w-[28px] items-center justify-center rounded border px-1 text-[10px] font-bold',
        colors,
      )}
      title={normalized != null ? `Consistency: ${normalized}%` : 'No score available'}
    >
      {normalized != null ? normalized : '--'}
    </span>
  );
}
