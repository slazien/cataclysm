'use client';

import { useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Upload, ChevronDown, Target, Check, BookOpen, TrendingDown, MessageSquare } from 'lucide-react';
import { useSessionStore, useUiStore } from '@/stores';
import { useUploadSessions } from '@/hooks/useSession';
import { useIsMobile } from '@/hooks/useMediaQuery';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { SkillLevelPicker, shouldShowSkillPicker } from './SkillLevelPicker';

const VALUE_PROPS = [
  {
    icon: Target,
    title: 'Physics-optimal lap target',
    description: 'Calibrated to your car, tires, and this specific track — not a best-sectors average.',
  },
  {
    icon: TrendingDown,
    title: 'Time gaps, corner by corner',
    description: 'See exactly where seconds are lost. Fix the biggest opportunity first.',
  },
  {
    icon: MessageSquare,
    title: 'AI coaching at your skill level',
    description: 'Specific, actionable advice — not generic driving tips.',
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
  const toggleHowItWorks = useUiStore((s) => s.toggleHowItWorks);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const isMobile = useIsMobile();
  const [showSuccess, setShowSuccess] = useState(false);
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null);
  const [showSkillPicker, setShowSkillPicker] = useState(false);

  const handleFiles = useCallback(
    (files: File[]) => {
      if (files.length === 0) return;
      setError(null);

      // Client-side CSV validation before triggering upload
      for (const file of files) {
        if (!file.name.toLowerCase().endsWith('.csv')) {
          setError(
            `"${file.name}" is not a CSV file. Please export from RaceChrono as CSV v3.`,
          );
          return;
        }
      }

      uploadMutation.mutate(files, {
        onSuccess: (data) => {
          if (data.session_ids.length > 0) {
            const sessionId = data.session_ids[0];
            localStorage.setItem('cataclysm_anon_session_id', sessionId);
            setShowSuccess(true);

            if (shouldShowSkillPicker()) {
              // Hold the session ID — show picker after brief success feedback
              setPendingSessionId(sessionId);
              setTimeout(() => {
                setShowSkillPicker(true);
              }, 800);
            } else {
              setTimeout(() => {
                setActiveSession(sessionId);
              }, 800);
            }
          }
        },
      });
    },
    [uploadMutation, setActiveSession],
  );

  const handleSkillPickerComplete = useCallback(() => {
    setShowSkillPicker(false);
    if (pendingSessionId) {
      setActiveSession(pendingSessionId);
    }
  }, [pendingSessionId, setActiveSession]);

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
      // Pass all files — handleFiles validates CSV extension and shows error for non-CSV
      const files = Array.from(e.dataTransfer.files);
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
      {/* Gradient background — visible atmospheric glow */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(245,158,11,0.10)_0%,transparent_60%)]" />

      {/* ── Hero ── */}
      <div className="relative mt-12 px-6 text-center lg:mt-20">
        <h1 className="font-[family-name:var(--font-display)] text-4xl font-bold tracking-tight text-[var(--text-primary)] lg:text-5xl">
          Your fastest lap is next.
        </h1>
        <p className="mx-auto mt-3 max-w-md text-lg text-[var(--text-secondary)] lg:text-xl">
          Upload telemetry. Get physics-based coaching. Drive faster.
        </p>
      </div>

      {/* ── Upload CTA ── */}
      <div className="mt-8 w-full max-w-md px-6">
        {/* Primary button — always visible */}
        <Button
          size="lg"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadMutation.isPending}
          className="min-h-[44px] w-full gap-2 bg-[var(--cata-accent)] text-base text-white hover:bg-[var(--cata-accent)]/90"
        >
          <Upload className="h-5 w-5" />
          Upload CSV
        </Button>

        {/* Trust badge */}
        <div className="mt-2.5 flex items-center justify-center gap-1.5 text-sm text-[var(--cata-accent)]">
          <Check className="h-3.5 w-3.5" />
          No sign-up required — see your report instantly
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

        {/* Drop zone — desktop only */}
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
            'mt-3 hidden cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 transition-colors lg:flex',
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
              <motion.div
                key="idle"
                className="flex flex-col items-center gap-1"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <Upload
                  className={cn('h-6 w-6', isDragging ? 'text-[var(--cata-accent)]' : 'text-[var(--text-secondary)]')}
                />
                <p className="text-sm font-medium text-[var(--text-primary)]">Drop CSV files here</p>
                <p className="text-xs text-[var(--text-secondary)]">or click to browse</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Success feedback on mobile (drop zone hidden, show inline) */}
        <AnimatePresence>
          {showSuccess && (
            <motion.div
              className="mt-3 flex items-center justify-center gap-1.5 lg:hidden"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <Check className="h-4 w-4 text-[var(--grade-a)]" />
              <p className="text-sm font-medium text-[var(--grade-a)]">Upload complete</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Error display */}
      {(error || uploadMutation.isError) && (
        <p className="mt-3 px-6 text-xs text-red-400">
          {error ?? uploadMutation.error?.message ?? 'Upload failed. Please check your CSV format.'}
        </p>
      )}

      {/* ── Sample Report Preview ── */}
      <div className="mt-12 w-full max-w-2xl px-6">
        <p className="mb-4 text-center text-sm font-medium text-[var(--text-secondary)]">
          Here&apos;s what you&apos;ll get after your first upload
        </p>
        <motion.div
          className="overflow-hidden rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)]"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          {/* Metrics strip */}
          <div className="grid grid-cols-3 divide-x divide-[var(--cata-border)] border-b border-[var(--cata-border)]">
            <div className="px-4 py-3 text-center">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Session Score</p>
              <p className="mt-0.5 text-xl font-bold text-emerald-400">78</p>
            </div>
            <div className="px-4 py-3 text-center">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Best Lap</p>
              <p className="mt-0.5 font-[family-name:var(--font-display)] text-xl font-bold text-[var(--text-primary)]">1:42.847</p>
            </div>
            <div className="px-4 py-3 text-center">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Optimal Gap</p>
              <p className="mt-0.5 font-[family-name:var(--font-display)] text-xl font-bold text-[var(--cata-accent)]">−1.3s</p>
            </div>
          </div>

          {/* AI coaching insight */}
          <div className="flex items-start gap-4 p-5 lg:gap-6">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[var(--cata-accent)]/15 lg:h-14 lg:w-14">
              <span className="font-[family-name:var(--font-display)] text-lg font-bold text-[var(--cata-accent)] lg:text-xl">T5</span>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--cata-accent)]">
                #1 Focus — 0.4s available
              </p>
              <p className="mt-1 text-sm leading-relaxed text-[var(--text-primary)]">
                Brake 15m later at Turn 5. Your brake trace shows early entry — move your reference
                point to the 50m board and carry more speed to the apex.
              </p>
            </div>
          </div>

          {/* Corner grades strip */}
          <div className="flex items-center gap-3 border-t border-[var(--cata-border)] px-5 py-3">
            <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              Corner Grades
            </span>
            <div className="flex gap-3">
              {SAMPLE_GRADES.map((g) => (
                <div key={g.turn} className="flex flex-col items-center gap-0.5">
                  <span className="text-[10px] text-[var(--text-secondary)]">{g.turn}</span>
                  <span className={cn('text-sm font-bold', g.color)}>{g.grade}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>

      {/* ── Value props ── */}
      <motion.div
        className="mt-10 w-full max-w-2xl px-6"
        initial="initial"
        animate="animate"
        variants={{ animate: { transition: { staggerChildren: 0.08 } } }}
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {VALUE_PROPS.map((prop) => (
            <motion.div
              key={prop.title}
              className="flex flex-col gap-3 rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4"
              variants={{ initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--cata-accent)]/10">
                <prop.icon className="h-4 w-4 text-[var(--cata-accent)]" />
              </div>
              <div>
                <p className="font-[family-name:var(--font-display)] text-sm font-semibold text-[var(--text-primary)]">
                  {prop.title}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
                  {prop.description}
                </p>
              </div>
            </motion.div>
          ))}
        </div>

        {/* How the analysis works — contextual link */}
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={toggleHowItWorks}
            className="inline-flex min-h-[44px] items-center gap-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            <BookOpen className="h-3.5 w-3.5" />
            How the analysis works
          </button>
        </div>
      </motion.div>

      {/* ── Setup instructions (demoted) ── */}
      <div id="racechrono-export-instructions" className="mt-8 w-full max-w-2xl px-6">
        <div className="rounded-lg bg-[var(--bg-surface)] px-4 py-3 transition-shadow">
          <button
            type="button"
            onClick={() => setInstructionsOpen((o) => !o)}
            className="flex min-h-[44px] w-full items-center justify-between text-left"
          >
            <span className="text-xs text-[var(--text-secondary)]">
              Works with <span className="font-medium text-[var(--text-primary)]">RaceChrono Pro</span>
              {' '}— how to export your data
            </span>
            <ChevronDown
              className={cn(
                'ml-2 h-3.5 w-3.5 shrink-0 text-[var(--text-secondary)] transition-transform',
                (instructionsOpen || !isMobile) ? 'rotate-180' : '',
              )}
            />
          </button>
          {(instructionsOpen || !isMobile) && (
            <ol className="mt-3 space-y-1.5 text-xs text-[var(--text-secondary)]">
              <li className="flex items-start gap-2">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-[10px] font-bold">1</span>
                Open session in RaceChrono Pro
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-[10px] font-bold">2</span>
                Tap Export &rarr; CSV v3 format
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-[10px] font-bold">3</span>
                Include GPS, speed, and lap data channels
              </li>
            </ol>
          )}
        </div>
      </div>

      {/* Disclaimer footer */}
      <p className="mt-6 max-w-2xl px-6 text-center text-[11px] leading-relaxed text-[var(--text-secondary)]">
        AI coaching is for educational purposes only and is not a substitute for professional instruction.
        Track driving carries inherent risks. GPS/telemetry data and AI analysis may contain inaccuracies.
      </p>

      <div className="h-8 shrink-0" />

      {/* Skill level picker overlay — shown once after first upload */}
      <AnimatePresence>
        {showSkillPicker && (
          <SkillLevelPicker onComplete={handleSkillPickerComplete} />
        )}
      </AnimatePresence>
    </div>
  );
}
