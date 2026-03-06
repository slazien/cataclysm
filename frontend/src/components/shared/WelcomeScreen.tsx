'use client';

import { useRef, useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Upload, ChevronDown, Sparkles, Target, ClipboardCheck, Check } from 'lucide-react';
import { useSessionStore } from '@/stores';
import { useUploadSessions } from '@/hooks/useSession';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const STEPS = [
  {
    num: 1,
    icon: Upload,
    title: 'Upload your RaceChrono CSV',
  },
  {
    num: 2,
    icon: Sparkles,
    title: 'AI analyzes every corner',
  },
  {
    num: 3,
    icon: Target,
    title: 'Get a personalized coaching report',
  },
] as const;

const SAMPLE_GRADES = [
  { turn: 'T1', grade: 'A', color: 'text-[var(--grade-a)]' },
  { turn: 'T2', grade: 'B', color: 'text-[var(--grade-b)]' },
  { turn: 'T3', grade: 'C', color: 'text-[var(--grade-c)]' },
  { turn: 'T4', grade: 'B', color: 'text-[var(--grade-b)]' },
  { turn: 'T5', grade: 'D', color: 'text-[var(--grade-d)]' },
  { turn: 'T6', grade: 'A', color: 'text-[var(--grade-a)]' },
  { turn: 'T7', grade: 'B', color: 'text-[var(--grade-b)]' },
] as const;

export function WelcomeScreen() {
  const uploadMutation = useUploadSessions();
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);
  const [isDragging, setIsDragging] = useState(false);
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

  return (
    <div className="relative flex min-h-0 w-full flex-1 flex-col items-center overflow-y-auto">
      {/* Gradient mesh background */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(245,158,11,0.05)_0%,transparent_70%)]" />

      {/* Hero */}
      <div className="relative mt-12 px-6 text-center lg:mt-20">
        <h1 className="font-[family-name:var(--font-display)] text-4xl font-bold tracking-tight text-[var(--text-primary)] lg:text-5xl">
          Your fastest lap is next.
        </h1>
        <p className="mx-auto mt-3 max-w-md font-[family-name:var(--font-display)] text-lg text-[var(--text-secondary)] lg:text-xl">
          Upload your telemetry. Get AI coaching in seconds.
        </p>
      </div>

      {/* Upload zone — giant button + drop area */}
      <div className="mt-8 w-full max-w-lg px-6">
        <Button
          size="lg"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadMutation.isPending}
          className="w-full gap-2 bg-[var(--cata-accent)] text-base text-white hover:bg-[var(--cata-accent)]/90"
        >
          <Upload className="h-5 w-5" />
          Upload CSV
        </Button>
        <p className="mt-2 text-center text-xs text-[var(--text-secondary)]">
          No sign-up required. See your coaching report instantly.
        </p>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".csv"
          className="hidden"
          onChange={handleFileInput}
        />

        {/* Drop zone */}
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
            'mt-3 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-5 transition-colors',
            isDragging
              ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/5'
              : 'border-[var(--cata-border)] bg-[var(--bg-surface)] hover:border-[var(--text-secondary)]',
          )}
        >
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
                <Upload
                  className={cn(
                    'h-6 w-6',
                    isDragging ? 'text-[var(--cata-accent)]' : 'text-[var(--text-secondary)]',
                  )}
                />
                <p className="text-sm font-medium text-[var(--text-primary)]">Drop CSV files here</p>
                <p className="text-xs text-[var(--text-secondary)]">
                  or click to browse
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Error display */}
      {(error || uploadMutation.isError) && (
        <p className="mt-4 px-6 text-xs text-red-400">
          {error ?? 'Upload failed. Please check your CSV format.'}
        </p>
      )}

      {/* Sample Report Preview */}
      <div className="mt-12 w-full max-w-2xl px-6">
        <p className="mb-4 text-center text-sm text-[var(--text-secondary)]">
          Here&apos;s what Cataclysm does with your data
        </p>
        <motion.div
          className="overflow-hidden rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5 lg:p-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          {/* Mockup header row */}
          <div className="flex items-start gap-4 lg:gap-6">
            {/* Score circle */}
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 lg:h-16 lg:w-16">
              <span className="text-xl font-bold text-emerald-400 lg:text-2xl">78</span>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--cata-accent)]">
                #1 Focus
              </p>
              <p className="mt-1 text-sm font-medium leading-relaxed text-[var(--text-primary)]">
                Brake 15m later at Turn 5 &mdash; you&apos;re leaving 0.4s on the table
              </p>
            </div>
          </div>

          {/* Corner grades strip */}
          <div className="mt-4 flex items-center gap-3 border-t border-[var(--cata-border)] pt-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              Corner Grades
            </span>
            <div className="flex gap-2">
              {SAMPLE_GRADES.map((g) => (
                <div key={g.turn} className="flex flex-col items-center">
                  <span className="text-[10px] text-[var(--text-secondary)]">{g.turn}</span>
                  <span className={cn('text-xs font-bold', g.color)}>{g.grade}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>

      {/* How It Works — 3 steps */}
      <motion.div
        className="mt-12 w-full max-w-2xl px-6"
        initial="initial"
        animate="animate"
        variants={{ animate: { transition: { staggerChildren: 0.1 } } }}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {STEPS.map((step) => (
            <motion.div
              key={step.num}
              className="flex flex-col items-center gap-3 rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5 text-center"
              variants={{
                initial: { opacity: 0, y: 20 },
                animate: { opacity: 1, y: 0 },
              }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
            >
              <div className="rounded-full bg-[var(--bg-elevated)] p-3">
                <step.icon className="h-5 w-5 text-[var(--cata-accent)]" />
              </div>
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--cata-accent)]">
                  Step {step.num}
                </span>
                <p className="mt-1 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-primary)]">
                  {step.title}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Supported formats + collapsible instructions */}
      <div className="mt-8 w-full max-w-2xl px-6">
        <p className="mb-3 text-center text-xs text-[var(--text-secondary)]">
          Works with RaceChrono Pro
        </p>
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <button
            type="button"
            onClick={() => setInstructionsOpen((o) => !o)}
            className="flex w-full items-center justify-between"
          >
            <h3 className="font-[family-name:var(--font-display)] text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              How to export from RaceChrono
            </h3>
            <ChevronDown
              className={cn(
                'h-4 w-4 text-[var(--text-secondary)] transition-transform',
                (instructionsOpen || !isMobile) ? 'rotate-180' : '',
              )}
            />
          </button>
          {(instructionsOpen || !isMobile) && (
            <ol className="mt-3 space-y-2 text-sm text-[var(--text-secondary)]">
              <li className="flex items-start gap-2">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-bold text-[var(--text-secondary)]">
                  1
                </span>
                Open session in RaceChrono Pro
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-bold text-[var(--text-secondary)]">
                  2
                </span>
                Tap Export &rarr; CSV v3 format
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-bold text-[var(--text-secondary)]">
                  3
                </span>
                Include GPS, speed, and lap data channels
              </li>
            </ol>
          )}
        </div>
      </div>

      {/* Disclaimer footer */}
      <p className="mt-8 max-w-2xl px-6 text-center text-[10px] leading-relaxed text-[var(--text-muted)]/60">
        AI coaching is for educational purposes only and is not a substitute for professional instruction.
        Track driving carries inherent risks. GPS/telemetry data and AI analysis may contain inaccuracies.
      </p>

      {/* Bottom spacer */}
      <div className="h-8 shrink-0" />
    </div>
  );
}
