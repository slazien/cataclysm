'use client';

import { useRef, useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Upload, FileSpreadsheet, ChevronDown, Clock, Sparkles, Target, TrendingUp, Check } from 'lucide-react';
import { useSessionStore } from '@/stores';
import { useUploadSessions, useSessions } from '@/hooks/useSession';
import { useTracks, useLoadTrackFolder } from '@/hooks/useTracks';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const VALUE_CARDS = [
  {
    icon: Sparkles,
    title: 'AI Coaching Report',
    description: 'Personalized insights after every session',
  },
  {
    icon: Target,
    title: 'Corner-by-Corner Grades',
    description: 'Know exactly where you\'re losing time',
  },
  {
    icon: TrendingUp,
    title: 'Progress Tracking',
    description: 'Track improvement session over session',
  },
] as const;

export function WelcomeScreen() {
  const uploadMutation = useUploadSessions();
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);
  const [isDragging, setIsDragging] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 1023px)');
    setIsMobile(mql.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);

  const handleFiles = useCallback(
    (files: File[]) => {
      if (files.length === 0) return;
      setError(null);
      uploadMutation.mutate(files, {
        onSuccess: (data) => {
          if (data.session_ids.length > 0) {
            setShowSuccess(true);
            setTimeout(() => {
              setActiveSession(data.session_ids[0]);
            }, 800);
          }
        },
      });
    },
    [uploadMutation, setActiveSession],
  );

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current++;
    setIsDragging(true);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      dragCounterRef.current = 0;
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files).filter((f) =>
        f.name.endsWith('.csv'),
      );
      handleFiles(files);
    },
    [handleFiles],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files) handleFiles(Array.from(files));
      e.target.value = '';
    },
    [handleFiles],
  );

  const { data: sessionsData } = useSessions();
  const { data: tracks } = useTracks();
  const loadTrackMutation = useLoadTrackFolder();

  const hasSampleData = (tracks?.length ?? 0) > 0;

  const handleSampleData = useCallback(() => {
    if (!tracks || tracks.length === 0) {
      setError('No local track data found. Upload a CSV to get started.');
      return;
    }
    setLoadingSample(true);
    setError(null);
    loadTrackMutation.mutate({ folder: tracks[0].folder, limit: 3 }, {
      onSuccess: (data) => {
        if (data.session_ids.length > 0) {
          setActiveSession(data.session_ids[0]);
        }
      },
      onError: () => {
        setError('Failed to load sample data');
      },
      onSettled: () => {
        setLoadingSample(false);
      },
    });
  }, [tracks, loadTrackMutation, setActiveSession]);

  return (
    <div className="relative flex min-h-0 w-full flex-1 flex-col items-center gap-8 overflow-y-auto p-6 lg:p-10">
      {/* Gradient mesh background */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(245,158,11,0.05)_0%,transparent_70%)]" />

      {/* Hero */}
      <div className="relative mt-8 text-center lg:mt-16">
        <h1 className="font-[family-name:var(--font-display)] text-4xl font-bold tracking-tight text-[var(--text-primary)] lg:text-5xl">
          Your AI racing coach
        </h1>
        <p className="mt-3 font-[family-name:var(--font-display)] text-lg text-[var(--text-secondary)] lg:text-xl">
          Upload a session. Get faster.
        </p>
      </div>

      {/* Action buttons */}
      <div className="flex flex-col items-center gap-3 sm:flex-row">
        <Button
          size="lg"
          onClick={() => fileInputRef.current?.click()}
          className="gap-2 bg-[var(--cata-accent)] text-white hover:bg-[var(--cata-accent)]/90"
        >
          <Upload className="h-4 w-4" />
          Upload CSV
        </Button>
        {hasSampleData && (
          <Button
            variant="outline"
            size="lg"
            onClick={handleSampleData}
            disabled={loadingSample}
            className="gap-2"
          >
            <FileSpreadsheet className="h-4 w-4" />
            {loadingSample ? 'Loading...' : 'Try Sample Data'}
          </Button>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".csv"
        className="hidden"
        onChange={handleFileInput}
      />

      {/* Error display */}
      {(error || uploadMutation.isError) && (
        <p className="text-xs text-red-400">
          {error ?? 'Upload failed. Please check your CSV format.'}
        </p>
      )}

      {/* Value cards */}
      <motion.div
        className="grid w-full max-w-2xl grid-cols-1 gap-4 sm:grid-cols-3"
        initial="initial"
        animate="animate"
        variants={{ animate: { transition: { staggerChildren: 0.1 } } }}
      >
        {VALUE_CARDS.map((card) => (
          <motion.div
            key={card.title}
            className="flex flex-col items-center gap-3 rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5 text-center"
            variants={{
              initial: { opacity: 0, y: 20 },
              animate: { opacity: 1, y: 0 },
            }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
          >
            <div className="rounded-full bg-[var(--bg-elevated)] p-3">
              <card.icon className="h-5 w-5 text-[var(--cata-accent)]" />
            </div>
            <h3 className="font-[family-name:var(--font-display)] text-sm font-semibold text-[var(--text-primary)]">
              {card.title}
            </h3>
            <p className="text-xs leading-relaxed text-[var(--text-muted)]">
              {card.description}
            </p>
          </motion.div>
        ))}
      </motion.div>

      {/* Upload drop zone */}
      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          'flex w-full max-w-2xl cursor-pointer flex-col items-center gap-4 rounded-xl border-2 border-dashed p-6 lg:p-10 min-h-[6rem] lg:min-h-[10rem] transition-colors',
          isDragging
            ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/5'
            : 'border-[var(--cata-border)] bg-[var(--bg-surface)] hover:border-[var(--text-muted)]',
        )}
      >
        <div className="rounded-full bg-[var(--bg-elevated)] p-4">
          <Upload
            className={cn(
              'h-8 w-8',
              isDragging ? 'text-[var(--cata-accent)]' : 'text-[var(--text-muted)]',
            )}
          />
        </div>
        <div className="text-center">
          <AnimatePresence mode="wait">
            {showSuccess ? (
              <motion.div
                key="success"
                className="flex flex-col items-center gap-1"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Check className="h-6 w-6 text-[var(--grade-a)]" />
                <p className="text-sm font-medium text-[var(--grade-a)]">Upload complete</p>
              </motion.div>
            ) : uploadMutation.isPending ? (
              <motion.div
                key="uploading"
                className="flex flex-col items-center gap-2"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <motion.div
                  className="h-5 w-5 rounded-full border-2 border-[var(--cata-accent)] border-t-transparent"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                />
                <p className="text-sm font-medium text-[var(--cata-accent)]">Processing telemetry...</p>
              </motion.div>
            ) : (
              <motion.div key="idle" className="flex flex-col items-center gap-1" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <p className="text-sm font-medium text-[var(--text-primary)]">Drop CSV files here</p>
                <p className="text-xs text-[var(--text-muted)]">
                  or click to browse — RaceChrono v3 CSV format
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Recent Sessions */}
      {(sessionsData?.items?.length ?? 0) > 0 && (
        <div className="w-full max-w-2xl rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Recent Sessions
          </h3>
          <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto">
            {sessionsData!.items.slice(0, 8).map((s) => (
              <button
                key={s.session_id}
                type="button"
                onClick={() => setActiveSession(s.session_id)}
                className="flex items-center gap-3 rounded-md px-3 py-2 text-left transition-colors hover:bg-[var(--bg-elevated)]"
              >
                <Clock className="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-primary)]">
                    {s.track_name}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">
                    {s.session_date} &middot; {s.n_laps} laps &middot; Best {s.best_lap_time_s ? `${Math.floor(s.best_lap_time_s / 60)}:${(s.best_lap_time_s % 60).toFixed(1).padStart(4, '0')}` : 'N/A'}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* How to export from RaceChrono (collapsible) */}
      <div className="w-full max-w-2xl rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
        <button
          type="button"
          onClick={() => setInstructionsOpen((o) => !o)}
          className="flex w-full items-center justify-between"
        >
          <h3 className="font-[family-name:var(--font-display)] text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            How to export from RaceChrono
          </h3>
          <ChevronDown
            className={cn(
              'h-4 w-4 text-[var(--text-muted)] transition-transform',
              (instructionsOpen || !isMobile) ? 'rotate-180' : '',
            )}
          />
        </button>
        {(instructionsOpen || !isMobile) && (
          <ol className="mt-3 space-y-2 text-sm text-[var(--text-secondary)]">
            <li className="flex items-start gap-2">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-bold text-[var(--text-muted)]">
                1
              </span>
              Open session in RaceChrono Pro
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-bold text-[var(--text-muted)]">
                2
              </span>
              Tap Export → CSV v3 format
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-bold text-[var(--text-muted)]">
                3
              </span>
              Include GPS, speed, and lap data channels
            </li>
          </ol>
        )}
      </div>

      {/* Disclaimer footer */}
      <p className="max-w-2xl text-center text-[10px] leading-relaxed text-[var(--text-muted)]/60">
        AI coaching is for educational purposes only and is not a substitute for professional instruction.
        Track driving carries inherent risks. GPS/telemetry data and AI analysis may contain inaccuracies.
      </p>

      {/* Bottom spacer */}
      <div className="h-4 shrink-0" />
    </div>
  );
}
