'use client';

import { useEffect, useRef, useState } from 'react';
import { useSessionStore } from '@/stores';
import { AlertTriangle, Check, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CircularProgress } from './CircularProgress';

const STEPS = [
  { key: 'uploading', label: 'Uploading CSV' },
  { key: 'processing', label: 'Detecting laps & corners' },
  { key: 'done', label: 'Ready to analyze' },
] as const;

function getStepStatus(
  stepKey: string,
  uploadState: string,
): 'pending' | 'active' | 'done' {
  const order = ['uploading', 'processing', 'done'];
  const currentIdx = order.indexOf(uploadState);
  const stepIdx = order.indexOf(stepKey);
  if (stepIdx < currentIdx) return 'done';
  if (stepIdx === currentIdx) return 'active';
  return 'pending';
}

/**
 * Animates from `start` toward 95% with an ease-out curve while
 * the server is processing (no real progress signal available).
 */
function useServerProcessingAnimation(active: boolean, start: number) {
  const [pct, setPct] = useState(start);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!active) return;

    let t0: number | null = null;
    const duration = 12000; // 12s to approach 95%

    function tick(ts: number) {
      if (t0 === null) t0 = ts;
      const elapsed = ts - t0;
      const t = Math.min(elapsed / duration, 1);
      // Ease-out cubic: fast start, slow approach to 95%
      const progress = start + (95 - start) * (1 - (1 - t) ** 3);
      setPct(progress);
      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [active, start]);

  return pct;
}

/** Scroll to the RaceChrono export instructions section on WelcomeScreen */
function scrollToExportInstructions() {
  const el = document.getElementById('racechrono-export-instructions');
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // Briefly highlight the section
    el.classList.add('ring-2', 'ring-[var(--cata-accent)]');
    setTimeout(() => el.classList.remove('ring-2', 'ring-[var(--cata-accent)]'), 2000);
  }
}

export function ProcessingOverlay() {
  const uploadState = useSessionStore((s) => s.uploadState);
  const uploadProgress = useSessionStore((s) => s.uploadProgress);
  const uploadErrorMessage = useSessionStore((s) => s.uploadErrorMessage);
  const resetUpload = useSessionStore((s) => s.resetUpload);

  // During 'processing' state, animate from wherever upload left off (60%) toward 95%
  const isProcessing = uploadState === 'processing';
  const serverPct = useServerProcessingAnimation(isProcessing, 60);

  // Compute the displayed progress
  let displayProgress: number;
  if (uploadState === 'done') {
    displayProgress = 100;
  } else if (uploadState === 'processing') {
    displayProgress = serverPct;
  } else {
    // 'uploading': real byte progress mapped to 0-60 range
    displayProgress = uploadProgress;
  }

  if (uploadState === 'idle') return null;
  if (uploadState === 'error') {
    const errorMsg = uploadErrorMessage || 'Upload failed. Please check your CSV format and try again.';
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div
          role="alertdialog"
          aria-modal="true"
          aria-label="Upload error"
          className="mx-4 w-full max-w-xs rounded-xl border border-red-500/30 bg-[var(--bg-surface)] p-6 text-center shadow-2xl"
        >
          <div className="mb-3 flex justify-center">
            <AlertTriangle className="h-8 w-8 text-red-400" />
          </div>
          <p className="text-sm font-medium text-red-400">Upload failed</p>
          <p className="mt-1.5 text-xs leading-relaxed text-[var(--text-secondary)]">
            {errorMsg}
          </p>
          <div className="mt-4 flex flex-col gap-2">
            <Button
              size="sm"
              onClick={resetUpload}
              className="min-h-[44px] w-full gap-2 bg-[var(--cata-accent)] text-white hover:bg-[var(--cata-accent)]/90"
            >
              <RotateCcw className="h-4 w-4" />
              Try Again
            </Button>
            <button
              type="button"
              onClick={() => {
                resetUpload();
                // Small delay so overlay unmounts before scroll
                requestAnimationFrame(() => scrollToExportInstructions());
              }}
              className="min-h-[44px] text-xs text-[var(--text-secondary)] underline underline-offset-2 transition-colors hover:text-[var(--text-primary)]"
            >
              Export instructions
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div role="dialog" aria-modal="true" aria-label="Processing session" className="w-full max-w-xs rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 shadow-2xl">
        <div className="mb-4 flex flex-col items-center gap-2">
          <CircularProgress size={48} strokeWidth={3.5} progress={displayProgress} />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Processing Session
          </h3>
        </div>
        <div className="space-y-3">
          {STEPS.map((step) => {
            const status = getStepStatus(step.key, uploadState);
            return (
              <div key={step.key} className="flex items-center gap-3">
                {status === 'done' ? (
                  <Check className="h-4 w-4 text-green-400" />
                ) : status === 'active' ? (
                  <CircularProgress size={16} strokeWidth={2} />
                ) : (
                  <div className="h-4 w-4 rounded-full border border-[var(--text-muted)]" />
                )}
                <span
                  className={`text-sm ${
                    status === 'done'
                      ? 'text-green-400'
                      : status === 'active'
                        ? 'text-[var(--text-primary)]'
                        : 'text-[var(--text-secondary)]'
                  }`}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
