'use client';

import { useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useUiStore, type Toast } from '@/stores/uiStore';
import { X } from 'lucide-react';

const borderByType: Record<Toast['type'], string> = {
  pb: 'border-l-[var(--color-pb)]',
  milestone: 'border-l-[var(--color-throttle)]',
  info: 'border-l-[var(--cata-accent)]',
};

const prefixByType: Record<Toast['type'], string> = {
  pb: '\u{1F3C6} ',
  milestone: '\u{2B50} ',
  info: '',
};

function ToastCard({ toast }: { toast: Toast }) {
  const removeToast = useUiStore((s) => s.removeToast);
  const duration = toast.duration ?? 5000;

  useEffect(() => {
    const timer = setTimeout(() => removeToast(toast.id), duration);
    return () => clearTimeout(timer);
  }, [toast.id, duration, removeToast]);

  return (
    <div
      className={cn(
        'animate-in slide-in-from-right-5 fade-in duration-300',
        'flex items-center gap-3 rounded-lg border border-l-4 px-4 py-3 shadow-lg',
        'bg-[var(--bg-elevated)] border-[var(--cata-border)]',
        borderByType[toast.type],
      )}
    >
      <span className="flex-1 text-sm font-medium text-[var(--text-primary)]">
        {prefixByType[toast.type]}{toast.message}
      </span>
      <button
        onClick={() => removeToast(toast.id)}
        className="shrink-0 rounded p-0.5 text-[var(--text-muted)] transition-colors hover:text-[var(--text-primary)]"
        aria-label="Dismiss"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useUiStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
