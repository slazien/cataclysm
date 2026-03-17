'use client';

import { useEffect } from 'react';
import { X } from 'lucide-react';
import { useUiStore } from '@/stores';
import { cn } from '@/lib/utils';
import { HOW_IT_WORKS_SECTIONS } from './howItWorksSections';

const HOW_IT_WORKS_SEEN_KEY = 'cataclysm-how-it-works-seen';

export function HowItWorksModal() {
  const open = useUiStore((s) => s.howItWorksOpen);
  const toggle = useUiStore((s) => s.toggleHowItWorks);

  // Auto-open once for first-time visitors, but only after disclaimer is accepted
  useEffect(() => {
    if (localStorage.getItem(HOW_IT_WORKS_SEEN_KEY)) return;

    const DISCLAIMER_KEY = 'cataclysm-disclaimer-accepted';

    const openIfClosed = () => {
      if (!useUiStore.getState().howItWorksOpen) toggle();
    };

    // Returning user: disclaimer already accepted, show after short delay
    if (localStorage.getItem(DISCLAIMER_KEY)) {
      const timer = setTimeout(openIfClosed, 400);
      return () => clearTimeout(timer);
    }

    // New user: poll until disclaimer is accepted, then show
    let pendingTimeout: ReturnType<typeof setTimeout>;
    const interval = setInterval(() => {
      if (localStorage.getItem(DISCLAIMER_KEY)) {
        clearInterval(interval);
        pendingTimeout = setTimeout(openIfClosed, 400);
      }
    }, 300);
    return () => { clearInterval(interval); clearTimeout(pendingTimeout); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleClose = () => {
    localStorage.setItem(HOW_IT_WORKS_SEEN_KEY, '1');
    toggle();
  };

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') handleClose();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[55] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div
        className={cn(
          'flex max-h-[90vh] w-full max-w-xl flex-col rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] shadow-2xl',
        )}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-[var(--cata-border)] px-6 py-4">
          <h2 className="font-[family-name:var(--font-display)] text-base font-bold text-[var(--text-primary)]">
            How Cataclysm Works
          </h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close"
            className="flex h-11 w-11 items-center justify-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <p className="mb-5 text-sm leading-relaxed text-[var(--text-secondary)]">
            Cataclysm turns raw telemetry into coaching you can act on. Here&apos;s what the
            numbers actually mean.
          </p>

          <div className="space-y-6">
            {HOW_IT_WORKS_SECTIONS.map((section) => (
              <section key={section.title}>
                <div className="mb-2 flex items-center gap-2">
                  <section.icon className="h-4 w-4 shrink-0 text-[var(--cata-accent)]" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--cata-accent)]">
                    {section.title}
                  </h3>
                </div>
                <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
                  {section.body}
                </p>
              </section>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-[var(--cata-border)] px-6 py-3">
          <p className="text-center text-[11px] text-[var(--text-secondary)]/60">
            Analysis accuracy depends on GPS quality and session length. Results are estimates, not guarantees.
          </p>
        </div>
      </div>
    </div>
  );
}
