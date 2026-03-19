'use client';

import { Sparkles, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useSessionStore } from '@/stores';
import { useIsMobile } from '@/hooks/useMediaQuery';

/**
 * Slim banner shown at the top of session content when viewing the demo session.
 * Includes a CTA to upload the user's own data.
 */
export function DemoBanner() {
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const isMobile = useIsMobile();

  return (
    <div className="flex items-center justify-between border-b border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-2">
      <div className="flex items-center gap-2 text-sm text-[var(--cata-accent)]">
        <Sparkles className="h-4 w-4 shrink-0" />
        <span>{isMobile ? 'Demo session' : "You're exploring a demo session"}</span>
      </div>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => setActiveSession(null)}
        className="gap-1.5 text-xs text-[var(--text-secondary)]"
      >
        <Upload className="h-3.5 w-3.5" />
        {isMobile ? 'Upload' : 'Upload your data'}
      </Button>
    </div>
  );
}
