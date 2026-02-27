'use client';

import { useState, useCallback } from 'react';
import { useStudents, useRemoveStudent, useCreateFlag } from '@/hooks/useInstructor';
import { StudentCard } from './StudentCard';
import { StudentSessionList } from './StudentSessionList';
import { InviteStudent } from './InviteStudent';
import { FlagBadge } from './FlagBadge';
import {
  Loader2,
  Users,
  ArrowLeft,
  Trash2,
  Plus,
  X,
  Flag,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StudentSummary } from '@/lib/types';

export function InstructorDashboard() {
  const { data, isLoading, error } = useStudents();
  const removeMutation = useRemoveStudent();
  const flagMutation = useCreateFlag();

  const [selectedStudent, setSelectedStudent] = useState<StudentSummary | null>(null);
  const [showFlagForm, setShowFlagForm] = useState(false);
  const [flagType, setFlagType] = useState('attention');
  const [flagDesc, setFlagDesc] = useState('');

  const handleRemoveStudent = useCallback(
    async (studentId: string) => {
      if (!confirm('Remove this student? They will need a new invite to rejoin.')) return;
      await removeMutation.mutateAsync(studentId);
      setSelectedStudent(null);
    },
    [removeMutation],
  );

  const handleCreateFlag = useCallback(async () => {
    if (!selectedStudent || !flagDesc.trim()) return;
    await flagMutation.mutateAsync({
      studentId: selectedStudent.student_id,
      flagType,
      description: flagDesc.trim(),
    });
    setFlagDesc('');
    setShowFlagForm(false);
  }, [selectedStudent, flagType, flagDesc, flagMutation]);

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--text-muted)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <p className="text-sm text-[var(--color-brake)]">
          Failed to load instructor data. Make sure you have instructor role.
        </p>
      </div>
    );
  }

  const students = data?.students ?? [];

  // Student detail view
  if (selectedStudent) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col gap-6 p-4 lg:p-8">
        {/* Header */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              setSelectedStudent(null);
              setShowFlagForm(false);
            }}
            className="rounded-lg p-1.5 text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">
              {selectedStudent.name}
            </h2>
            <p className="text-xs text-[var(--text-muted)]">{selectedStudent.email}</p>
          </div>
          <button
            type="button"
            onClick={() => setShowFlagForm(!showFlagForm)}
            className={cn(
              'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
              showFlagForm
                ? 'border-[var(--color-brake)]/30 bg-[var(--color-brake)]/5 text-[var(--color-brake)]'
                : 'border-[var(--cata-border)] bg-[var(--bg-surface)] text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]',
            )}
          >
            {showFlagForm ? <X className="h-3.5 w-3.5" /> : <Flag className="h-3.5 w-3.5" />}
            {showFlagForm ? 'Cancel' : 'Add Flag'}
          </button>
          <button
            type="button"
            onClick={() => handleRemoveStudent(selectedStudent.student_id)}
            disabled={removeMutation.isPending}
            className="rounded-lg border border-[var(--color-brake)]/30 bg-[var(--color-brake)]/5 p-1.5 text-[var(--color-brake)] transition-colors hover:bg-[var(--color-brake)]/10"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>

        {/* Add flag form */}
        {showFlagForm && (
          <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
            <h3 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
              Create Manual Flag
            </h3>
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap gap-2">
                {(['attention', 'safety', 'improvement', 'praise'] as const).map((ft) => (
                  <button
                    key={ft}
                    type="button"
                    onClick={() => setFlagType(ft)}
                    className={cn(
                      'rounded-lg border px-3 py-1.5 text-xs transition-colors',
                      flagType === ft
                        ? 'border-[var(--text-primary)]/30 bg-[var(--bg-elevated)]'
                        : 'border-transparent',
                    )}
                  >
                    <FlagBadge flagType={ft} />
                  </button>
                ))}
              </div>
              <textarea
                value={flagDesc}
                onChange={(e) => setFlagDesc(e.target.value)}
                placeholder="Describe the flag..."
                rows={2}
                className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--text-muted)] focus:outline-none"
              />
              <button
                type="button"
                onClick={handleCreateFlag}
                disabled={!flagDesc.trim() || flagMutation.isPending}
                className={cn(
                  'self-end rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                  'bg-[var(--color-throttle)] text-black hover:bg-[var(--color-throttle)]/80',
                  (!flagDesc.trim() || flagMutation.isPending) && 'opacity-50',
                )}
              >
                {flagMutation.isPending ? 'Creating...' : 'Create Flag'}
              </button>
            </div>
          </div>
        )}

        {/* Sessions */}
        <StudentSessionList
          studentId={selectedStudent.student_id}
          studentName={selectedStudent.name}
        />
      </div>
    );
  }

  // Student list view
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-4 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="h-5 w-5 text-[var(--text-muted)]" />
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">
            Instructor Dashboard
          </h1>
        </div>
        <span className="text-sm text-[var(--text-muted)]">
          {students.length} student{students.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Invite */}
      <InviteStudent />

      {/* Student list */}
      {students.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <Users className="h-8 w-8 text-[var(--text-muted)]" />
          <p className="text-sm text-[var(--text-secondary)]">
            No students linked yet. Generate an invite code above.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {students.map((student) => (
            <StudentCard
              key={student.student_id}
              student={student}
              isSelected={false}
              onClick={() => setSelectedStudent(student)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
