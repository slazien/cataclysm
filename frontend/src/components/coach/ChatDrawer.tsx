'use client';

import { useCoachStore } from '@/stores';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { ContextChips } from '@/components/coach/ContextChips';
import { SuggestedQuestions } from '@/components/coach/SuggestedQuestions';
import { ChatMessages, ChatInput } from '@/components/coach/ChatInterface';
import { Bot } from 'lucide-react';

export function ChatDrawer() {
  const panelOpen = useCoachStore((s) => s.panelOpen);
  const togglePanel = useCoachStore((s) => s.togglePanel);
  const setPendingQuestion = useCoachStore((s) => s.setPendingQuestion);

  return (
    <Sheet open={panelOpen} onOpenChange={togglePanel}>
      <SheetContent
        side="right"
        className="flex w-full flex-col border-l border-[var(--cata-border)] bg-[var(--bg-surface)] p-0 sm:max-w-[480px]"
      >
        <SheetHeader className="border-b border-[var(--cata-border)] px-4 py-3">
          <SheetTitle className="flex items-center gap-2 text-base font-semibold text-[var(--text-primary)]">
            <Bot className="h-4 w-4 text-[var(--cata-accent)]" />
            AI Coach
          </SheetTitle>
        </SheetHeader>

        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="border-b border-[var(--cata-border)]">
            <ContextChips />
          </div>

          <div className="flex-1 overflow-y-auto">
            <ChatMessages />
          </div>

          <div className="border-t border-[var(--cata-border)]">
            <SuggestedQuestions onAsk={setPendingQuestion} />
          </div>

          <ChatInput />
        </div>
      </SheetContent>
    </Sheet>
  );
}
