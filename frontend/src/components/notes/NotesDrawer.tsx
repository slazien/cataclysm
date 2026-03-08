'use client';

import { motion, AnimatePresence } from 'motion/react';
import { StickyNote, Globe, FileText } from 'lucide-react';
import { useNotesStore, useSessionStore } from '@/stores';
import { useSessionNotes, useGlobalNotes } from '@/hooks/useNotes';
import { useCorners } from '@/hooks/useAnalysis';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { NoteCard } from '@/components/notes/NoteCard';
import { NoteEditor } from '@/components/notes/NoteEditor';
import { cn } from '@/lib/utils';

export function NotesDrawer() {
  const panelOpen = useNotesStore((s) => s.panelOpen);
  const togglePanel = useNotesStore((s) => s.togglePanel);
  const activeTab = useNotesStore((s) => s.activeTab);
  const setActiveTab = useNotesStore((s) => s.setActiveTab);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);

  const { data: sessionNotes, isPending: sessionPending } =
    useSessionNotes(activeSessionId);
  const { data: globalNotes, isPending: globalPending } = useGlobalNotes();
  const { data: corners } = useCorners(activeSessionId);

  const cornerNames = corners?.map(
    (c) => `T${c.number}`,
  ) ?? [];

  const notes = activeTab === 'session' ? sessionNotes : globalNotes;
  const isPending = activeTab === 'session' ? sessionPending : globalPending;

  return (
    <Sheet open={panelOpen} onOpenChange={togglePanel}>
      <SheetContent
        side="right"
        className="flex w-full flex-col border-l border-[var(--cata-border)] bg-[var(--bg-surface)] p-0 sm:max-w-[400px]"
      >
        <AnimatePresence>
          {panelOpen && (
            <motion.div
              className="flex flex-1 flex-col overflow-hidden"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              transition={{ duration: 0.3, delay: 0.15 }}
            >
              <SheetHeader className="border-b border-[var(--cata-border)] px-4 py-3">
                <SheetTitle className="flex items-center gap-2 text-base font-semibold text-[var(--text-primary)]">
                  <StickyNote className="h-4 w-4 text-[var(--cata-accent)]" />
                  Notes
                </SheetTitle>
              </SheetHeader>

              {/* Tab switcher */}
              <div className="flex border-b border-[var(--cata-border)]">
                <button
                  type="button"
                  onClick={() => setActiveTab('session')}
                  className={cn(
                    'flex flex-1 items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors',
                    activeTab === 'session'
                      ? 'border-b-2 border-[var(--cata-accent)] text-[var(--cata-accent)]'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
                  )}
                >
                  <FileText className="h-3.5 w-3.5" />
                  This Session
                  {sessionNotes && sessionNotes.total > 0 && (
                    <span className="rounded-full bg-[var(--cata-accent)]/20 px-1.5 py-0.5 text-[10px]">
                      {sessionNotes.total}
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('global')}
                  className={cn(
                    'flex flex-1 items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors',
                    activeTab === 'global'
                      ? 'border-b-2 border-[var(--cata-accent)] text-[var(--cata-accent)]'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
                  )}
                >
                  <Globe className="h-3.5 w-3.5" />
                  Global Notepad
                  {globalNotes && globalNotes.total > 0 && (
                    <span className="rounded-full bg-[var(--cata-accent)]/20 px-1.5 py-0.5 text-[10px]">
                      {globalNotes.total}
                    </span>
                  )}
                </button>
              </div>

              {/* Note editor */}
              <div className="border-b border-[var(--cata-border)] p-3">
                <NoteEditor
                  sessionId={activeTab === 'session' ? activeSessionId : null}
                  corners={cornerNames}
                  laps={[]} // Will be populated from session laps
                />
              </div>

              {/* Notes list */}
              <div className="flex-1 overflow-y-auto p-3">
                {isPending ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--cata-accent)] border-t-transparent" />
                  </div>
                ) : notes && notes.items.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    {notes.items.map((note) => (
                      <NoteCard key={note.id} note={note} />
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
                    <StickyNote className="h-8 w-8 text-[var(--text-muted)]" />
                    <p className="text-sm text-[var(--text-muted)]">
                      {activeTab === 'session'
                        ? 'No notes for this session yet'
                        : 'No global notes yet'}
                    </p>
                    <p className="text-xs text-[var(--text-muted)]">
                      Use @ to reference corners (@T5), laps (@L7), or metrics
                    </p>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </SheetContent>
    </Sheet>
  );
}
