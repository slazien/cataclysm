'use client';

import { useEffect, useState } from 'react';
import { useSessionStore } from '@/stores';
import { Check } from 'lucide-react';
import { CircularProgress } from './CircularProgress';

const STEPS = [
  { key: 'uploading', label: 'Uploading CSV', target: 33 },
  { key: 'processing', label: 'Detecting laps & corners', target: 66 },
  { key: 'done', label: 'Ready to analyze', target: 100 },
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

export function ProcessingOverlay() {
  const uploadState = useSessionStore((s) => s.uploadState);
  const [progress, setProgress] = useState(0);

  // Smoothly advance progress within each step's range
  useEffect(() => {
    if (uploadState === 'idle') {
      setProgress(0);
      return;
    }

    const step = STEPS.find((s) => s.key === uploadState);
    if (!step) return;

    const prevTarget = STEPS[STEPS.indexOf(step) - 1]?.target ?? 0;
    const target = step.target;

    // Jump to start of current range, then smoothly fill
    setProgress(prevTarget);
    const timer = setTimeout(() => setProgress(target), 100);
    return () => clearTimeout(timer);
  }, [uploadState]);

  if (uploadState === 'idle') return null;
  if (uploadState === 'error') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div className="w-full max-w-xs rounded-xl border border-red-500/30 bg-[var(--bg-surface)] p-6 text-center shadow-2xl">
          <p className="text-sm font-medium text-red-400">Upload failed</p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Please check your CSV format and try again
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-xs rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 shadow-2xl">
        <div className="mb-4 flex flex-col items-center gap-2">
          <CircularProgress size={48} strokeWidth={3.5} progress={progress} />
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
                        : 'text-[var(--text-muted)]'
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
