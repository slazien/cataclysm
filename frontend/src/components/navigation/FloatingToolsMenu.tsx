'use client';

import React, { useCallback, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { MessageCircle, Pin, Plus, StickyNote } from 'lucide-react';
import { useCoachStore, useNotesStore, useSessionStore } from '@/stores';
import { callTriggerAdd } from '@/stores/useStickyStore';
import { useIsMobile } from '@/hooks/useMediaQuery';
import { isDemoSession } from '@/hooks/useDemo';

interface ToolItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  accent: string;
  action: () => void;
}

/**
 * FAB that consolidates Notes, AI Coach, and Add Sticky
 * into a single trigger that fans open on click/tap.
 * Same design on mobile and desktop — only positioning differs.
 */
export function FloatingToolsMenu() {
  const isMobile = useIsMobile();
  const [open, setOpen] = useState(false);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);

  const toggleNotes = useNotesStore((s) => s.togglePanel);
  const notesPanelOpen = useNotesStore((s) => s.panelOpen);
  const toggleCoach = useCoachStore((s) => s.togglePanel);
  const coachPanelOpen = useCoachStore((s) => s.panelOpen);

  const handleAddSticky = useCallback(() => {
    callTriggerAdd();
    setOpen(false);
  }, []);

  const handleNotes = useCallback(() => {
    toggleNotes();
    setOpen(false);
  }, [toggleNotes]);

  const handleCoach = useCallback(() => {
    toggleCoach();
    setOpen(false);
  }, [toggleCoach]);

  // Hide when a panel is already open (they have their own close controls)
  if (notesPanelOpen || coachPanelOpen) return null;

  const isDemo = isDemoSession(activeSessionId);

  const allItems: ToolItem[] = [
    {
      id: 'coach',
      label: 'AI Coach',
      icon: <MessageCircle className="h-5 w-5" />,
      accent: 'bg-[var(--cata-accent)]/80',
      action: handleCoach,
    },
    {
      id: 'notes',
      label: 'Notes',
      icon: <StickyNote className="h-5 w-5" />,
      accent: 'bg-amber-400/80',
      action: handleNotes,
    },
    {
      id: 'sticky',
      label: 'Pin Sticky',
      icon: <Pin className="h-5 w-5" />,
      accent: 'bg-violet-400/80',
      action: handleAddSticky,
    },
  ];
  // During demo: only show AI Coach (notes/stickies are write-only)
  const items = isDemo ? allItems.filter((i) => i.id === 'coach') : allItems;

  return (
    <>
      {/* Scrim — click/tap outside to dismiss */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            onClick={() => setOpen(false)}
            aria-hidden
          >
            <div className="h-full w-full bg-black/20 backdrop-blur-[1px]" />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Menu + trigger */}
      <div
        className={
          isMobile
            ? 'fixed bottom-[calc(4.5rem+env(safe-area-inset-bottom))] right-4 z-40 flex flex-col items-end gap-2.5'
            : 'fixed bottom-8 right-8 z-40 flex flex-col items-end gap-2.5'
        }
      >
        {/* Fan-out items */}
        <AnimatePresence>
          {open &&
            items.map((item, i) => (
              <motion.button
                key={item.id}
                type="button"
                onClick={item.action}
                className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-[var(--bg-surface)]/85 py-1.5 pl-4 pr-1.5 shadow-lg backdrop-blur-xl transition-colors hover:bg-[var(--bg-surface)]"
                initial={{ opacity: 0, y: 16, scale: 0.85 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.85 }}
                transition={{
                  type: 'spring',
                  stiffness: 440,
                  damping: 26,
                  delay: i * 0.04,
                }}
              >
                <span className="text-xs font-semibold text-[var(--text-primary)]">
                  {item.label}
                </span>
                <span
                  className={`flex h-10 w-10 items-center justify-center rounded-full text-white ${item.accent}`}
                >
                  {item.icon}
                </span>
              </motion.button>
            ))}
        </AnimatePresence>

        {/* Trigger button */}
        <motion.button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? 'Close tools menu' : 'Open tools menu'}
          className={
            isMobile
              ? 'flex h-13 w-13 items-center justify-center rounded-full bg-[var(--cata-accent)] shadow-[0_8px_24px_-6px_rgba(0,0,0,0.5)]'
              : 'flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cata-accent)] shadow-[0_8px_24px_-6px_rgba(0,0,0,0.5)]'
          }
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.9 }}
        >
          <motion.div
            animate={{ rotate: open ? 45 : 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 22 }}
          >
            <Plus className="h-6 w-6 text-black" />
          </motion.div>
        </motion.button>
      </div>
    </>
  );
}
