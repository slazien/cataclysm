'use client';

import { Mail, MessageSquare } from 'lucide-react';

const EMAIL = 'cataclysm.hpde@gmail.com';

export function AppFooter() {
  return (
    <footer className="shrink-0 border-t border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-2">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[10px] text-[var(--text-secondary)]">
        <span>
          Built by <span className="text-[var(--text-secondary)]">Przemek Zientala</span>
        </span>
        <div className="flex items-center gap-3">
          <a
            href={`mailto:${EMAIL}`}
            className="flex items-center gap-1 transition-colors hover:text-[var(--text-secondary)]"
          >
            <Mail className="h-3 w-3" />
            <span className="hidden sm:inline">{EMAIL}</span>
            <span className="sm:hidden">Contact</span>
          </a>
          <a
            href={`mailto:${EMAIL}?subject=Cataclysm%20Feedback`}
            className="flex items-center gap-1 rounded-md bg-[var(--cata-accent)]/10 px-2 py-0.5 text-[var(--cata-accent)] transition-colors hover:bg-[var(--cata-accent)]/20"
          >
            <MessageSquare className="h-3 w-3" />
            Submit Feedback
          </a>
        </div>
      </div>
    </footer>
  );
}
