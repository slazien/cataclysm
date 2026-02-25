'use client';

import { useCallback, useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useCoachStore } from '@/stores';
import { ContextChips } from './ContextChips';
import { ReportSummary } from './ReportSummary';
import { SuggestedQuestions } from './SuggestedQuestions';
import { ChatInterface } from './ChatInterface';

function CoachPanelContent({ onClose }: { onClose: () => void }) {
  const setPendingQuestion = useCoachStore((s) => s.setPendingQuestion);

  const handleAsk = useCallback(
    (question: string) => {
      setPendingQuestion(question);
    },
    [setPendingQuestion],
  );

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-[var(--cata-border)] px-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">AI Coach</h2>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-7 w-7 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Context Chips */}
      <ContextChips />

      {/* Report Summary */}
      <ReportSummary />

      {/* Suggested Questions */}
      <SuggestedQuestions onAsk={handleAsk} />

      {/* Chat Interface -- fills remaining space */}
      <ChatInterface />
    </div>
  );
}

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    setIsMobile(mql.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, [breakpoint]);

  return isMobile;
}

export function CoachPanel() {
  const panelOpen = useCoachStore((s) => s.panelOpen);
  const togglePanel = useCoachStore((s) => s.togglePanel);
  const isMobile = useIsMobile();

  if (isMobile) {
    return (
      <Sheet open={panelOpen} onOpenChange={togglePanel}>
        <SheetContent
          side="right"
          showCloseButton={false}
          className="w-full max-w-[400px] p-0 bg-[var(--bg-surface)]"
        >
          <SheetHeader className="sr-only">
            <SheetTitle>AI Coach</SheetTitle>
          </SheetHeader>
          <CoachPanelContent onClose={togglePanel} />
        </SheetContent>
      </Sheet>
    );
  }

  // Desktop: inline panel
  return (
    <div className="flex h-full w-[400px] shrink-0 flex-col border-l border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <CoachPanelContent onClose={togglePanel} />
    </div>
  );
}
