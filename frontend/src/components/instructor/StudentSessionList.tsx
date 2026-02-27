'use client';

import { useStudentSessions } from '@/hooks/useInstructor';
import { formatLapTime } from '@/lib/formatters';
import { FlagBadge } from './FlagBadge';
import { Loader2, Calendar, Timer, Target } from 'lucide-react';

interface StudentSessionListProps {
  studentId: string;
  studentName: string;
}

export function StudentSessionList({ studentId, studentName }: StudentSessionListProps) {
  const { data, isLoading } = useStudentSessions(studentId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--text-muted)]" />
      </div>
    );
  }

  const sessions = data?.sessions ?? [];

  if (sessions.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-[var(--text-muted)]">
        No sessions found for {studentName}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {sessions.map((s) => (
        <div
          key={s.session_id}
          className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[var(--text-primary)]">
                {s.track_name}
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-[var(--text-muted)]">
                {s.session_date && (
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {s.session_date}
                  </span>
                )}
                {s.best_lap_time_s !== null && (
                  <span className="flex items-center gap-1">
                    <Timer className="h-3 w-3" />
                    {formatLapTime(s.best_lap_time_s)}
                  </span>
                )}
                {s.consistency_score !== null && (
                  <span className="flex items-center gap-1">
                    <Target className="h-3 w-3" />
                    {s.consistency_score.toFixed(0)}
                  </span>
                )}
                {s.n_laps !== null && (
                  <span>{s.n_laps} laps</span>
                )}
              </div>
            </div>
          </div>

          {s.flags.length > 0 && (
            <div className="mt-2 flex flex-col gap-1.5">
              {s.flags.map((f) => (
                <div key={f.id} className="flex items-start gap-2">
                  <FlagBadge flagType={f.flag_type} className="mt-0.5" />
                  <span className="text-xs text-[var(--text-secondary)]">
                    {f.description}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
