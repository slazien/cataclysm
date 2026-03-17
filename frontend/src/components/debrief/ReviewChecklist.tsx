'use client';

import { useCallback, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight } from 'lucide-react';

interface ChecklistItem {
  id: string;
  label: string;
}

const ITEMS: ChecklistItem[] = [
  { id: 'top3', label: 'Reviewed top 3 opportunities and coaching tips' },
  { id: 'optimal', label: 'Checked optimal gap per corner' },
  { id: 'comparison', label: 'Compared with previous session — noted changes' },
  { id: 'consistency', label: 'Checked consistency trends for weak corners' },
  { id: 'drills', label: 'Identified 1–2 drills to practice next session' },
  { id: 'goal', label: 'Set a specific goal for next session' },
];

function storageKey(sessionId: string) {
  return `cataclysm-review-checklist-${sessionId}`;
}

function loadChecked(sessionId: string): Set<string> {
  try {
    const raw = localStorage.getItem(storageKey(sessionId));
    if (!raw) return new Set();
    return new Set(JSON.parse(raw) as string[]);
  } catch {
    return new Set();
  }
}

function saveChecked(sessionId: string, checked: Set<string>) {
  localStorage.setItem(storageKey(sessionId), JSON.stringify([...checked]));
}

interface ReviewChecklistProps {
  sessionId: string;
}

export function ReviewChecklist({ sessionId }: ReviewChecklistProps) {
  const router = useRouter();
  const [checked, setChecked] = useState<Set<string>>(() => loadChecked(sessionId));

  const toggle = useCallback(
    (id: string) => {
      setChecked((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        saveChecked(sessionId, next);
        return next;
      });
    },
    [sessionId],
  );

  const progress = useMemo(
    () => Math.round((checked.size / ITEMS.length) * 100),
    [checked.size],
  );

  const allDone = checked.size === ITEMS.length;

  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="border-l-[3px] border-[var(--text-secondary)] pl-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
          Review Checklist
        </h3>
        <span
          className={`text-xs font-semibold ${
            allDone ? 'text-[var(--color-throttle)]' : 'text-[var(--text-secondary)]'
          }`}
        >
          {progress}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
        <div
          className="h-full rounded-full bg-[var(--color-throttle)] transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      <ul className="space-y-2">
        {ITEMS.map((item) => {
          const isChecked = checked.has(item.id);
          return (
            <li key={item.id}>
              <label className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-[var(--bg-elevated)]">
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => toggle(item.id)}
                  className="h-4 w-4 shrink-0 accent-[var(--color-throttle)]"
                />
                <span
                  className={`text-sm ${
                    isChecked
                      ? 'text-[var(--text-secondary)] line-through'
                      : 'text-[var(--text-primary)]'
                  }`}
                >
                  {item.label}
                </span>
                {item.id === 'comparison' && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      router.push(`/compare/${sessionId}`);
                    }}
                    className="ml-auto flex shrink-0 items-center gap-1 text-xs text-[var(--cata-accent)] hover:underline"
                  >
                    Compare
                    <ArrowRight className="h-3 w-3" />
                  </button>
                )}
              </label>
            </li>
          );
        })}
      </ul>

      {allDone && (
        <p className="mt-3 text-center text-xs font-medium text-[var(--color-throttle)]">
          Review complete — you&apos;re ready for your next session!
        </p>
      )}
    </div>
  );
}
