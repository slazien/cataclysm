'use client';

import { useCallback, useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useCreateProfile, useTireSearch } from '@/hooks/useEquipment';
import type { TireSpec } from '@/lib/types';

interface EquipmentSetupModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (profileId: string) => void;
}

type Step = 'tire' | 'details' | 'confirm';

const COMPOUND_LABELS: Record<string, string> = {
  street: 'Street',
  '200tw': '200TW',
  'r-comp': 'R-Comp',
  slick: 'Slick',
};

export function EquipmentSetupModal({
  open,
  onOpenChange,
  onCreated,
}: EquipmentSetupModalProps) {
  const [step, setStep] = useState<Step>('tire');
  const [profileName, setProfileName] = useState('');
  const [tireQuery, setTireQuery] = useState('');
  const [selectedTire, setSelectedTire] = useState<TireSpec | null>(null);
  const [compoundCategory, setCompoundCategory] = useState('200tw');
  const [tireSize, setTireSize] = useState('');

  const { data: searchResults, isLoading: searching } = useTireSearch(tireQuery);
  const createMutation = useCreateProfile();

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setStep('tire');
      setProfileName('');
      setTireQuery('');
      setSelectedTire(null);
      setCompoundCategory('200tw');
      setTireSize('');
    }
  }, [open]);

  const handleSelectTire = useCallback((tire: TireSpec) => {
    setSelectedTire(tire);
    setCompoundCategory(tire.compound_category);
    setTireSize(tire.size);
    setTireQuery(tire.model);
  }, []);

  const handleCreate = useCallback(() => {
    if (!selectedTire && !tireQuery) return;

    const tireName = selectedTire?.model ?? tireQuery;
    const name = profileName || tireName;

    createMutation.mutate(
      {
        name,
        tires: {
          model: tireName,
          compound_category: compoundCategory,
          size: tireSize || '255/40R17',
          estimated_mu: selectedTire?.estimated_mu ?? 1.0,
          mu_source: selectedTire?.mu_source ?? 'estimated',
          mu_confidence: selectedTire?.mu_confidence ?? 'low',
          brand: selectedTire?.brand ?? null,
          treadwear_rating: selectedTire?.treadwear_rating ?? null,
          pressure_psi: null,
          age_sessions: null,
        },
      },
      {
        onSuccess: (data) => {
          onCreated?.(data.id);
          onOpenChange(false);
        },
      },
    );
  }, [
    selectedTire,
    tireQuery,
    profileName,
    compoundCategory,
    tireSize,
    createMutation,
    onCreated,
    onOpenChange,
  ]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[var(--bg-surface)] border-[var(--cata-border)] sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-[var(--text-primary)]">
            {step === 'tire' && 'Search for Tires'}
            {step === 'details' && 'Setup Details'}
            {step === 'confirm' && 'Confirm Profile'}
          </DialogTitle>
          <DialogDescription className="text-[var(--text-secondary)]">
            {step === 'tire' && 'Search our tire database or enter manually'}
            {step === 'details' && 'Set compound category and tire size'}
            {step === 'confirm' && 'Review and save your equipment profile'}
          </DialogDescription>
        </DialogHeader>

        {/* Step 1: Tire Search */}
        {step === 'tire' && (
          <div className="flex flex-col gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                type="text"
                value={tireQuery}
                onChange={(e) => {
                  setTireQuery(e.target.value);
                  setSelectedTire(null);
                }}
                placeholder="Search tires (e.g. RE-71RS, RT660)"
                className="w-full rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] py-2 pl-9 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--cata-accent)] focus:outline-none"
                autoFocus
              />
            </div>

            {/* Search results */}
            {searching && (
              <p className="text-xs text-[var(--text-muted)]">Searching...</p>
            )}
            {searchResults && searchResults.length > 0 && !selectedTire && (
              <div className="max-h-48 overflow-y-auto rounded-md border border-[var(--cata-border)]">
                {searchResults.map((tire, i) => (
                  <button
                    key={`${tire.model}-${i}`}
                    type="button"
                    onClick={() => handleSelectTire(tire)}
                    className="flex w-full items-center justify-between px-3 py-2 text-left transition-colors hover:bg-[var(--bg-elevated)]"
                  >
                    <div>
                      <p className="text-sm font-medium text-[var(--text-primary)]">
                        {tire.model}
                      </p>
                      <p className="text-xs text-[var(--text-muted)]">
                        {COMPOUND_LABELS[tire.compound_category] ?? tire.compound_category}
                        {tire.treadwear_rating ? ` | TW ${tire.treadwear_rating}` : ''}
                      </p>
                    </div>
                    <span className="text-xs text-[var(--text-muted)]">
                      {tire.brand}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {selectedTire && (
              <div className="rounded-md border border-[var(--cata-accent)]/30 bg-[var(--cata-accent)]/5 p-3">
                <p className="text-sm font-medium text-[var(--text-primary)]">
                  {selectedTire.model}
                </p>
                <p className="text-xs text-[var(--text-secondary)]">
                  {selectedTire.brand} | {COMPOUND_LABELS[selectedTire.compound_category] ?? selectedTire.compound_category}
                  {selectedTire.treadwear_rating ? ` | TW ${selectedTire.treadwear_rating}` : ''}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Step 2: Details */}
        {step === 'details' && (
          <div className="flex flex-col gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                Compound Category
              </label>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(COMPOUND_LABELS).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setCompoundCategory(key)}
                    className={`rounded-md border px-3 py-2 text-sm transition-colors ${
                      compoundCategory === key
                        ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/10 text-[var(--text-primary)]'
                        : 'border-[var(--cata-border)] text-[var(--text-secondary)] hover:border-[var(--text-muted)]'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                Tire Size
              </label>
              <input
                type="text"
                value={tireSize}
                onChange={(e) => setTireSize(e.target.value)}
                placeholder="e.g. 255/40R17"
                className="w-full rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--cata-accent)] focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                Profile Name (optional)
              </label>
              <input
                type="text"
                value={profileName}
                onChange={(e) => setProfileName(e.target.value)}
                placeholder={(selectedTire?.model ?? tireQuery) || 'My Setup'}
                className="w-full rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--cata-accent)] focus:outline-none"
              />
            </div>
          </div>
        )}

        {/* Step 3: Confirm */}
        {step === 'confirm' && (
          <div className="flex flex-col gap-3">
            <div className="rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] p-4">
              <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                {profileName || selectedTire?.model || tireQuery}
              </h4>
              <div className="mt-2 space-y-1 text-xs text-[var(--text-secondary)]">
                <p>Tire: {selectedTire?.model ?? tireQuery}</p>
                <p>Compound: {COMPOUND_LABELS[compoundCategory] ?? compoundCategory}</p>
                {tireSize && <p>Size: {tireSize}</p>}
                {selectedTire?.brand && <p>Brand: {selectedTire.brand}</p>}
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          {step === 'tire' && (
            <Button
              onClick={() => setStep('details')}
              disabled={!tireQuery && !selectedTire}
              className="bg-[var(--cata-accent)] text-white hover:opacity-90"
            >
              Next
            </Button>
          )}
          {step === 'details' && (
            <div className="flex w-full gap-2">
              <Button
                variant="outline"
                onClick={() => setStep('tire')}
                className="border-[var(--cata-border)] text-[var(--text-secondary)]"
              >
                Back
              </Button>
              <Button
                onClick={() => setStep('confirm')}
                className="flex-1 bg-[var(--cata-accent)] text-white hover:opacity-90"
              >
                Next
              </Button>
            </div>
          )}
          {step === 'confirm' && (
            <div className="flex w-full gap-2">
              <Button
                variant="outline"
                onClick={() => setStep('details')}
                className="border-[var(--cata-border)] text-[var(--text-secondary)]"
              >
                Back
              </Button>
              <Button
                onClick={handleCreate}
                disabled={createMutation.isPending}
                className="flex-1 bg-[var(--cata-accent)] text-white hover:opacity-90"
              >
                {createMutation.isPending ? 'Saving...' : 'Save Profile'}
              </Button>
            </div>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
