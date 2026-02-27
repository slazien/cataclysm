'use client';

import { MessageCircle } from 'lucide-react';
import { useCoachStore } from '@/stores';
import { cn } from '@/lib/utils';

export function FloatingChatButton() {
  const panelOpen = useCoachStore((s) => s.panelOpen);
  const togglePanel = useCoachStore((s) => s.togglePanel);
  const chatHistory = useCoachStore((s) => s.chatHistory);

  // Count assistant messages since last user message as "unread" (simplified)
  // In practice this would use a proper unread counter from the store
  const hasMessages = chatHistory.length > 0;

  if (panelOpen) return null; // Hide FAB when drawer is open

  return (
    <button
      type="button"
      onClick={togglePanel}
      className={cn(
        'fixed bottom-20 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition-all hover:scale-105 active:scale-95',
        'bg-gradient-to-br from-[var(--cata-accent)] to-[var(--cata-accent)]/80 text-white',
        'lg:bottom-8 lg:right-8',
      )}
      title="Open AI Coach (press /)"
    >
      <MessageCircle className="h-6 w-6" />
      {hasMessages && (
        <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
          !
        </span>
      )}
    </button>
  );
}
