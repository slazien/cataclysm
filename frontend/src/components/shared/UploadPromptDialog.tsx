'use client';

import { useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Upload, X } from 'lucide-react';
import { useUiStore } from '@/stores/uiStore';
import { useSessionStore } from '@/stores';
import { useUploadSessions } from '@/hooks/useSession';
import { Button } from '@/components/ui/button';

export function UploadPromptDialog() {
  const open = useUiStore((s) => s.uploadPromptOpen);
  const setOpen = useUiStore((s) => s.setUploadPromptOpen);
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const uploadMutation = useUploadSessions();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: File[]) => {
      if (files.length === 0) return;
      uploadMutation.mutate(files, {
        onSuccess: (data) => {
          if (data.session_ids.length > 0) {
            localStorage.setItem('cataclysm_anon_session_id', data.session_ids[0]);
            setActiveSession(data.session_ids[0]);
            setOpen(false);
          }
        },
      });
    },
    [uploadMutation, setActiveSession, setOpen],
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files) handleFiles(Array.from(files));
      e.target.value = '';
    },
    [handleFiles],
  );

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onKeyDown={(e) => { if (e.key === 'Escape') setOpen(false); }}
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setOpen(false)}
          />

          {/* Dialog */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Upload a session"
            className="relative w-full max-w-sm rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 shadow-xl"
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
          >
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="absolute right-3 top-3 rounded p-1 text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="flex flex-col items-center text-center">
              <div className="rounded-full bg-[var(--cata-accent)]/10 p-3">
                <Upload className="h-6 w-6 text-[var(--cata-accent)]" />
              </div>
              <h3 className="mt-3 font-[family-name:var(--font-display)] text-lg font-semibold text-[var(--text-primary)]">
                Upload a session first
              </h3>
              <p className="mt-1.5 text-sm text-[var(--text-secondary)]">
                Upload your RaceChrono CSV to unlock all features — AI coaching, deep dive analysis, progress tracking, and more.
              </p>

              <Button
                size="lg"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadMutation.isPending}
                className="mt-5 w-full gap-2 bg-[var(--cata-accent)] text-white hover:bg-[var(--cata-accent)]/90"
              >
                {uploadMutation.isPending ? (
                  <>
                    <motion.div
                      className="h-4 w-4 rounded-full border-2 border-white border-t-transparent"
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    />
                    Processing...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" />
                    Upload CSV
                  </>
                )}
              </Button>

              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".csv"
                className="hidden"
                onChange={handleFileInput}
              />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
