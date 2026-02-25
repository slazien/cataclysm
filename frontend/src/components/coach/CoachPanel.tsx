'use client';

export function CoachPanel() {
  return (
    <div className="flex h-full w-[400px] shrink-0 flex-col border-l border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <div className="flex h-12 items-center border-b border-[var(--cata-border)] px-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">AI Coach</h2>
      </div>
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">Coach Panel</p>
      </div>
    </div>
  );
}
