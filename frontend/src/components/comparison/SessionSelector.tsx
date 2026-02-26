'use client';

import { useState } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useSessions } from '@/hooks/useSession';
import { cn } from '@/lib/utils';
import { formatLapTime, parseSessionDate } from '@/lib/formatters';
import { Button } from '@/components/ui/button';
import { CircularProgress } from '@/components/shared/CircularProgress';

interface SessionSelectorProps {
  currentSessionId: string;
}

export function SessionSelector({ currentSessionId }: SessionSelectorProps) {
  const router = useRouter();
  const { data: sessionsData, isLoading } = useSessions();
  const [selectedOtherId, setSelectedOtherId] = useState<string | null>(null);

  const sessions = sessionsData?.items ?? [];
  const otherSessions = sessions.filter((s) => s.session_id !== currentSessionId);
  const currentSession = sessions.find((s) => s.session_id === currentSessionId);

  function handleCompare() {
    if (selectedOtherId) {
      router.push(`/compare/${currentSessionId}?with=${selectedOtherId}`);
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 p-8">
        <CircularProgress size={32} />
        <p className="text-sm text-[var(--text-secondary)]">Loading sessions...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-4 lg:p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => router.back()}
          title="Go back"
          className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">Compare Sessions</h1>
          <p className="text-sm text-[var(--text-secondary)]">
            Select another session to compare against{' '}
            {currentSession ? (
              <span className="font-medium text-[var(--text-primary)]">
                {currentSession.track_name}
              </span>
            ) : (
              <span className="font-mono text-[var(--text-muted)]">
                {currentSessionId.slice(0, 8)}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Current Session Info */}
      {currentSession && (
        <div className="rounded-lg border border-[var(--cata-accent)]/30 bg-[var(--cata-accent)]/5 px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Current Session
          </p>
          <p className="mt-1 text-sm font-medium text-[var(--text-primary)]">
            {currentSession.track_name} &mdash; {currentSession.session_date}
          </p>
          <p className="mt-0.5 font-mono text-lg font-semibold text-[var(--text-primary)]">
            {formatLapTime(currentSession.best_lap_time_s)}
          </p>
        </div>
      )}

      {/* Session List */}
      {otherSessions.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="text-sm text-[var(--text-secondary)]">
            No other sessions available for comparison.
          </p>
          <p className="text-xs text-[var(--text-muted)]">
            Upload more sessions to enable comparison.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Select a session to compare
          </p>
          <div className="flex flex-col gap-1">
            {otherSessions
              .sort((a, b) => {
                const dateA = parseSessionDate(a.session_date).getTime();
                const dateB = parseSessionDate(b.session_date).getTime();
                return dateB - dateA;
              })
              .map((s) => (
                <button
                  key={s.session_id}
                  type="button"
                  onClick={() => setSelectedOtherId(s.session_id)}
                  className={cn(
                    'flex items-center justify-between rounded-lg border px-4 py-3 text-left transition-all',
                    selectedOtherId === s.session_id
                      ? 'border-[var(--cata-accent)]/50 bg-[var(--cata-accent)]/10'
                      : 'border-[var(--cata-border)] bg-[var(--bg-surface)] hover:border-[var(--text-muted)]/30 hover:bg-[var(--bg-elevated)]',
                  )}
                >
                  <div>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {s.track_name}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                      {s.session_date} &middot; {s.n_clean_laps}/{s.n_laps} clean laps
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-sm font-semibold text-[var(--text-primary)]">
                      {formatLapTime(s.best_lap_time_s)}
                    </p>
                    <p className="font-mono text-xs text-[var(--text-muted)]">
                      {s.session_id.slice(0, 8)}
                    </p>
                  </div>
                </button>
              ))}
          </div>
        </div>
      )}

      {/* Compare Button */}
      {selectedOtherId && (
        <div className="flex justify-end">
          <Button onClick={handleCompare} className="gap-1.5">
            Compare
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
