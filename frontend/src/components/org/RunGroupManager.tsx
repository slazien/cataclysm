'use client';

import { useState, useCallback } from 'react';
import { Plus, X, Tag } from 'lucide-react';
import { cn } from '@/lib/utils';

interface RunGroupManagerProps {
  groups: string[];
  onChange: (groups: string[]) => void;
  disabled?: boolean;
}

const PRESET_GROUPS = ['Novice', 'Intermediate', 'Advanced', 'Instructor'];

export function RunGroupManager({ groups, onChange, disabled }: RunGroupManagerProps) {
  const [customInput, setCustomInput] = useState('');

  const addGroup = useCallback(
    (name: string) => {
      const trimmed = name.trim();
      if (!trimmed || groups.includes(trimmed)) return;
      onChange([...groups, trimmed]);
    },
    [groups, onChange],
  );

  const removeGroup = useCallback(
    (name: string) => {
      onChange(groups.filter((g) => g !== name));
    },
    [groups, onChange],
  );

  const handleCustomAdd = useCallback(() => {
    if (customInput.trim()) {
      addGroup(customInput.trim());
      setCustomInput('');
    }
  }, [customInput, addGroup]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Tag className="h-4 w-4 text-[var(--text-muted)]" />
        <span className="text-sm font-medium text-[var(--text-primary)]">Run Groups</span>
      </div>

      {/* Presets */}
      <div className="flex flex-wrap gap-2">
        {PRESET_GROUPS.map((preset) => {
          const isActive = groups.includes(preset);
          return (
            <button
              key={preset}
              type="button"
              disabled={disabled}
              onClick={() => (isActive ? removeGroup(preset) : addGroup(preset))}
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                isActive
                  ? 'border-[var(--color-throttle)]/40 bg-[var(--color-throttle)]/10 text-[var(--color-throttle)]'
                  : 'border-[var(--cata-border)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]',
                disabled && 'opacity-50',
              )}
            >
              {isActive && '✓ '}
              {preset}
            </button>
          );
        })}
      </div>

      {/* Custom group input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCustomAdd()}
          placeholder="Custom group name..."
          disabled={disabled}
          className={cn(
            'flex-1 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-primary)] px-3 py-1.5 text-sm text-[var(--text-primary)]',
            'placeholder:text-[var(--text-muted)] focus:border-[var(--text-muted)] focus:outline-none',
            disabled && 'opacity-50',
          )}
        />
        <button
          type="button"
          onClick={handleCustomAdd}
          disabled={disabled || !customInput.trim()}
          className={cn(
            'rounded-lg bg-[var(--bg-surface)] p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)]',
            (disabled || !customInput.trim()) && 'opacity-50',
          )}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Active groups list */}
      {groups.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {groups.map((g) => (
            <span
              key={g}
              className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-elevated)] px-2.5 py-0.5 text-xs text-[var(--text-secondary)]"
            >
              {g}
              {!disabled && (
                <button
                  type="button"
                  onClick={() => removeGroup(g)}
                  className="ml-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
