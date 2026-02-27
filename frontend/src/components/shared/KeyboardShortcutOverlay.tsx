'use client';

import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { useSkillLevel } from '@/hooks/useSkillLevel';

const SHORTCUTS = [
  { key: '1', description: 'Session Report' },
  { key: '2', description: 'Deep Dive' },
  { key: '3', description: 'Progress' },
  { key: '/', description: 'Open AI Coach' },
  { key: 'Esc', description: 'Close panel/drawer' },
  { key: '\u2190/\u2192', description: 'Prev/next corner (Corner tab)' },
  { key: '?', description: 'Toggle this overlay' },
];

export function KeyboardShortcutOverlay() {
  const { showFeature } = useSkillLevel();
  const [visible, setVisible] = useState(false);
  const isEnabled = showFeature('keyboard_overlay');

  useEffect(() => {
    if (!isEnabled) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === '?' && !(e.target as HTMLElement).matches('input, textarea, [contenteditable]')) {
        e.preventDefault();
        setVisible((v) => !v);
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isEnabled]);

  if (!isEnabled || !visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-sm rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">Keyboard Shortcuts</h2>
          <button type="button" onClick={() => setVisible(false)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="space-y-2">
          {SHORTCUTS.map((s) => (
            <div key={s.key} className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">{s.description}</span>
              <kbd className="rounded border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-2 py-0.5 text-xs font-mono text-[var(--text-primary)]">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
