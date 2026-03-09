'use client';

import { useState } from 'react';
import { X } from 'lucide-react';

interface SignUpCTAProps {
  /** Headline override for contextual CTAs (e.g. share page). */
  headline?: string;
  /** Sub-headline override. */
  subline?: string;
}

export function SignUpCTA({ headline, subline }: SignUpCTAProps = {}) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-[var(--cata-border)] bg-[var(--bg-surface)]/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-4 px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-[var(--text-primary)]">{headline ?? 'Analyze your own track days'}</p>
          <p className="text-xs text-[var(--text-secondary)]">{subline ?? 'AI coaching, corner analysis, and progress tracking'}</p>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="/api/auth/signin"
            className="whitespace-nowrap rounded-md bg-[#6366f1] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#5558e6]"
          >
            Sign up free
          </a>
          <button
            onClick={() => setDismissed(true)}
            className="rounded p-1 text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
