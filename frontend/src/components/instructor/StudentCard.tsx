'use client';

import { User, ChevronRight } from 'lucide-react';
import { FlagBadge } from './FlagBadge';
import { cn } from '@/lib/utils';
import type { StudentSummary } from '@/lib/types';

interface StudentCardProps {
  student: StudentSummary;
  isSelected: boolean;
  onClick: () => void;
}

export function StudentCard({ student, isSelected, onClick }: StudentCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors',
        isSelected
          ? 'border-[var(--color-throttle)]/40 bg-[var(--color-throttle)]/5'
          : 'border-[var(--cata-border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)]',
      )}
    >
      {/* Avatar */}
      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)]">
        {student.avatar_url ? (
          <img
            src={student.avatar_url}
            alt={student.name}
            className="h-9 w-9 rounded-full object-cover"
          />
        ) : (
          <User className="h-4 w-4 text-[var(--text-muted)]" />
        )}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[var(--text-primary)]">
          {student.name}
        </p>
        <p className="truncate text-xs text-[var(--text-muted)]">{student.email}</p>
        {student.recent_flags.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {student.recent_flags.slice(0, 3).map((flag, i) => (
              <FlagBadge key={i} flagType={flag} />
            ))}
          </div>
        )}
      </div>

      <ChevronRight className="h-4 w-4 flex-shrink-0 text-[var(--text-muted)]" />
    </button>
  );
}
