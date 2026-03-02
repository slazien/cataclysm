'use client';

import { motion, AnimatePresence } from 'motion/react';
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

  return (
    <AnimatePresence>
      {!panelOpen && (
        <motion.button
          type="button"
          onClick={togglePanel}
          className={cn(
            'fixed bottom-20 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full shadow-lg',
            'bg-gradient-to-br from-[var(--cata-accent)] to-[var(--cata-accent)]/80 text-white',
            'lg:bottom-8 lg:right-8',
          )}
          title="Open AI Coach (press /)"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
        >
          <MessageCircle className="h-6 w-6" />
          {hasMessages && (
            <motion.span
              className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 500, damping: 15, delay: 0.2 }}
            >
              !
            </motion.span>
          )}
        </motion.button>
      )}
    </AnimatePresence>
  );
}
