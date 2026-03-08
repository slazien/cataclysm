'use client';

import { motion, AnimatePresence } from 'motion/react';
import { StickyNote } from 'lucide-react';
import { useNotesStore } from '@/stores';
import { cn } from '@/lib/utils';

export function FloatingNotesButton() {
  const panelOpen = useNotesStore((s) => s.panelOpen);
  const togglePanel = useNotesStore((s) => s.togglePanel);

  return (
    <AnimatePresence>
      {!panelOpen && (
        <motion.button
          type="button"
          onClick={togglePanel}
          className={cn(
            'fixed bottom-24 left-4 z-40 flex h-14 w-14 items-center justify-center rounded-full shadow-lg',
            'bg-gradient-to-br from-amber-500 to-amber-500/80 text-white',
            'lg:bottom-8 lg:left-8',
          )}
          title="Open Notes (press n)"
          aria-label="Open Notes"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
        >
          <StickyNote className="h-6 w-6" />
        </motion.button>
      )}
    </AnimatePresence>
  );
}
