'use client';

import { useEffect } from 'react';
import { X } from 'lucide-react';
import { useUiStore } from '@/stores';
import { cn } from '@/lib/utils';
import { EquipmentProfileList } from '@/components/equipment/EquipmentProfileList';
import { updateUserProfile } from '@/lib/api';

const SKILL_LEVELS = [
  { value: 'novice' as const, label: 'Novice', description: 'New to track days' },
  { value: 'intermediate' as const, label: 'Intermediate', description: 'Regular track driver' },
  { value: 'advanced' as const, label: 'Advanced', description: 'Competitive / racing' },
];

const UNIT_OPTIONS = [
  { value: 'imperial' as const, label: 'Imperial', description: 'mph, ft' },
  { value: 'metric' as const, label: 'Metric', description: 'km/h, m' },
];

export function SettingsPanel() {
  const open = useUiStore((s) => s.settingsPanelOpen);
  const toggle = useUiStore((s) => s.toggleSettingsPanel);
  const skillLevel = useUiStore((s) => s.skillLevel);
  const setSkillLevel = useUiStore((s) => s.setSkillLevel);
  const unitPreference = useUiStore((s) => s.unitPreference);
  const setUnitPreference = useUiStore((s) => s.setUnitPreference);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') toggle();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, toggle]);

  return (
    <>
      {/* Overlay */}
      <div
        className={cn(
          'fixed inset-0 z-40 bg-black/50 transition-opacity duration-200',
          open ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
        onClick={toggle}
      />

      {/* Panel */}
      <div
        className={cn(
          'fixed right-0 top-0 z-50 flex h-full w-80 flex-col bg-[var(--bg-surface)] shadow-xl transition-transform duration-200 ease-out',
          open ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--cata-border)] px-4 py-3">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Settings</h2>
          <button
            type="button"
            onClick={toggle}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Equipment Profiles — most important customization */}
          <EquipmentProfileList />

          {/* Skill Level */}
          <fieldset className="mb-6">
            <legend className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
              Skill Level
            </legend>
            <div className="space-y-2">
              {SKILL_LEVELS.map((level) => (
                <label
                  key={level.value}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 transition-colors',
                    skillLevel === level.value
                      ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/10'
                      : 'border-[var(--cata-border)] hover:border-[var(--text-muted)]',
                  )}
                >
                  <input
                    type="radio"
                    name="skillLevel"
                    value={level.value}
                    checked={skillLevel === level.value}
                    onChange={() => {
                      setSkillLevel(level.value);
                      updateUserProfile({ skill_level: level.value }).catch(() => {});
                    }}
                    className="sr-only"
                  />
                  <div
                    className={cn(
                      'flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2',
                      skillLevel === level.value
                        ? 'border-[var(--cata-accent)]'
                        : 'border-[var(--text-muted)]',
                    )}
                  >
                    {skillLevel === level.value && (
                      <div className="h-2 w-2 rounded-full bg-[var(--cata-accent)]" />
                    )}
                  </div>
                  <div>
                    <span className="text-sm font-medium text-[var(--text-primary)]">
                      {level.label}
                    </span>
                    <p className="text-xs text-[var(--text-muted)]">{level.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </fieldset>

          {/* Units */}
          <fieldset>
            <legend className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
              Units
            </legend>
            <div className="space-y-2">
              {UNIT_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 transition-colors',
                    unitPreference === option.value
                      ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/10'
                      : 'border-[var(--cata-border)] hover:border-[var(--text-muted)]',
                  )}
                >
                  <input
                    type="radio"
                    name="unitPreference"
                    value={option.value}
                    checked={unitPreference === option.value}
                    onChange={() => setUnitPreference(option.value)}
                    className="sr-only"
                  />
                  <div
                    className={cn(
                      'flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2',
                      unitPreference === option.value
                        ? 'border-[var(--cata-accent)]'
                        : 'border-[var(--text-muted)]',
                    )}
                  >
                    {unitPreference === option.value && (
                      <div className="h-2 w-2 rounded-full bg-[var(--cata-accent)]" />
                    )}
                  </div>
                  <div>
                    <span className="text-sm font-medium text-[var(--text-primary)]">
                      {option.label}
                    </span>
                    <p className="text-xs text-[var(--text-muted)]">{option.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </fieldset>
        </div>
      </div>
    </>
  );
}
