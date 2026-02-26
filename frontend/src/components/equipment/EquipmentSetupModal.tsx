'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  useBrakePadSearch,
  useCommonBrakeFluids,
  useCommonTireSizes,
  useCreateProfile,
  useTireSearch,
  useUpdateProfile,
} from '@/hooks/useEquipment';
import type { BrakePadSearchResult, EquipmentProfile, TireSpec } from '@/lib/types';

interface EquipmentSetupModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: (profileId: string) => void;
  editProfile?: EquipmentProfile | null;
}

const COMPOUND_LABELS: Record<string, string> = {
  street: 'Street',
  endurance_200tw: 'Endurance 200TW',
  super_200tw: '200TW',
  '100tw': '100TW',
  r_comp: 'R-Comp',
  slick: 'Slick',
};

const COMPOUND_BUTTONS: Record<string, string> = {
  street: 'Street',
  super_200tw: '200TW',
  r_comp: 'R-Comp',
  slick: 'Slick',
};

export function EquipmentSetupModal({
  open,
  onOpenChange,
  onSaved,
  editProfile,
}: EquipmentSetupModalProps) {
  const isEdit = !!editProfile;

  // --- Form state ---
  const [profileName, setProfileName] = useState('');
  const [tireQuery, setTireQuery] = useState('');
  const [selectedTire, setSelectedTire] = useState<TireSpec | null>(null);
  const [compoundCategory, setCompoundCategory] = useState('super_200tw');
  const [tireSize, setTireSize] = useState('');
  const [tireSizeOpen, setTireSizeOpen] = useState(false);
  const [tirePressure, setTirePressure] = useState('');
  const [padQuery, setPadQuery] = useState('');
  const [selectedPad, setSelectedPad] = useState<BrakePadSearchResult | null>(null);
  const [brakeFluid, setBrakeFluid] = useState('');
  const [notes, setNotes] = useState('');

  // --- Queries ---
  const { data: tireResults, isLoading: searchingTires } = useTireSearch(tireQuery);
  const { data: padResults, isLoading: searchingPads } = useBrakePadSearch(padQuery);
  const { data: commonSizes } = useCommonTireSizes();
  const { data: commonFluids } = useCommonBrakeFluids();
  const createMutation = useCreateProfile();
  const updateMutation = useUpdateProfile();

  const tireSizeRef = useRef<HTMLDivElement>(null);

  // Pre-fill when editing
  useEffect(() => {
    if (!open) return;
    if (editProfile) {
      setProfileName(editProfile.name);
      setTireQuery(editProfile.tires.model);
      setSelectedTire(editProfile.tires);
      setCompoundCategory(editProfile.tires.compound_category);
      setTireSize(editProfile.tires.size === 'varies' ? '' : editProfile.tires.size);
      setTirePressure(editProfile.tires.pressure_psi?.toString() ?? '');
      if (editProfile.brakes?.compound) {
        setPadQuery(editProfile.brakes.compound);
        setSelectedPad({
          model: editProfile.brakes.compound,
          brand: '',
          category: '',
          temp_range: editProfile.brakes.pad_temp_range ?? '',
          initial_bite: '',
          notes: '',
        });
      } else {
        setPadQuery('');
        setSelectedPad(null);
      }
      setBrakeFluid(editProfile.brakes?.fluid_type ?? '');
      setNotes(editProfile.notes ?? '');
    } else {
      // Reset for create mode
      setProfileName('');
      setTireQuery('');
      setSelectedTire(null);
      setCompoundCategory('super_200tw');
      setTireSize('');
      setTireSizeOpen(false);
      setTirePressure('');
      setPadQuery('');
      setSelectedPad(null);
      setBrakeFluid('');
      setNotes('');
    }
  }, [open, editProfile]);

  // Close tire size dropdown on outside click
  useEffect(() => {
    if (!tireSizeOpen) return;
    function handleClick(e: MouseEvent) {
      if (tireSizeRef.current && !tireSizeRef.current.contains(e.target as Node)) {
        setTireSizeOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [tireSizeOpen]);

  const handleSelectTire = useCallback((tire: TireSpec) => {
    setSelectedTire(tire);
    setCompoundCategory(tire.compound_category);
    if (tire.size !== 'varies') setTireSize(tire.size);
    setTireQuery(tire.model);
  }, []);

  const handleSelectPad = useCallback((pad: BrakePadSearchResult) => {
    setSelectedPad(pad);
    setPadQuery(pad.model);
  }, []);

  const handleSave = useCallback(() => {
    if (!selectedTire && !tireQuery) return;

    const tireName = selectedTire?.model ?? tireQuery;
    const name = profileName || tireName;

    const payload = {
      name,
      tires: {
        model: tireName,
        compound_category: compoundCategory,
        size: tireSize || '255/40R17',
        estimated_mu: selectedTire?.estimated_mu ?? 1.0,
        mu_source: selectedTire?.mu_source ?? 'formula_estimate',
        mu_confidence: selectedTire?.mu_confidence ?? 'low',
        brand: selectedTire?.brand ?? null,
        treadwear_rating: selectedTire?.treadwear_rating ?? null,
        pressure_psi: tirePressure ? parseFloat(tirePressure) : null,
        age_sessions: null,
      },
      brakes: selectedPad
        ? {
            compound: selectedPad.model,
            rotor_type: null,
            pad_temp_range: selectedPad.temp_range,
            fluid_type: brakeFluid || null,
          }
        : brakeFluid
          ? { compound: null, rotor_type: null, pad_temp_range: null, fluid_type: brakeFluid }
          : null,
      notes: notes || null,
    };

    if (isEdit && editProfile) {
      updateMutation.mutate(
        { profileId: editProfile.id, body: payload },
        {
          onSuccess: (data) => {
            onSaved?.(data.id);
            onOpenChange(false);
          },
        },
      );
    } else {
      createMutation.mutate(payload, {
        onSuccess: (data) => {
          onSaved?.(data.id);
          onOpenChange(false);
        },
      });
    }
  }, [
    selectedTire, tireQuery, profileName, compoundCategory, tireSize,
    tirePressure, selectedPad, brakeFluid, notes, isEdit, editProfile,
    createMutation, updateMutation, onSaved, onOpenChange,
  ]);

  const isSaving = createMutation.isPending || updateMutation.isPending;
  const inputClass =
    'w-full rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--cata-accent)] focus:outline-none';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[var(--bg-surface)] border-[var(--cata-border)] sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-[var(--text-primary)]">
            {isEdit ? 'Edit Equipment Profile' : 'Create Equipment Profile'}
          </DialogTitle>
          <DialogDescription className="text-[var(--text-secondary)]">
            Configure tires and brakes for your track setup
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5">
          {/* Profile Name */}
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              Profile Name
            </label>
            <input
              type="text"
              value={profileName}
              onChange={(e) => setProfileName(e.target.value)}
              placeholder="e.g. Track Day Setup"
              className={inputClass}
            />
          </div>

          {/* --- TIRES --- */}
          <fieldset>
            <legend className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Tires
            </legend>
            <div className="flex flex-col gap-3">
              {/* Tire search */}
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
                  className={`${inputClass} pl-9`}
                />
              </div>

              {/* Tire search results */}
              {searchingTires && (
                <p className="text-xs text-[var(--text-muted)]">Searching...</p>
              )}
              {tireResults && tireResults.length > 0 && !selectedTire && (
                <div className="max-h-36 overflow-y-auto rounded-md border border-[var(--cata-border)]">
                  {tireResults.map((tire, i) => (
                    <button
                      key={`${tire.model}-${i}`}
                      type="button"
                      onClick={() => handleSelectTire(tire)}
                      className="flex w-full items-center justify-between px-3 py-2 text-left transition-colors hover:bg-[var(--bg-elevated)]"
                    >
                      <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">{tire.model}</p>
                        <p className="text-xs text-[var(--text-muted)]">
                          {COMPOUND_LABELS[tire.compound_category] ?? tire.compound_category}
                          {tire.treadwear_rating ? ` | TW ${tire.treadwear_rating}` : ''}
                        </p>
                      </div>
                      <span className="text-xs text-[var(--text-muted)]">{tire.brand}</span>
                    </button>
                  ))}
                </div>
              )}

              {selectedTire && (
                <div className="rounded-md border border-[var(--cata-accent)]/30 bg-[var(--cata-accent)]/5 p-2">
                  <p className="text-sm font-medium text-[var(--text-primary)]">{selectedTire.model}</p>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {selectedTire.brand} | {COMPOUND_LABELS[selectedTire.compound_category] ?? selectedTire.compound_category}
                  </p>
                </div>
              )}

              {/* Compound buttons */}
              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                  Compound
                </label>
                <div className="grid grid-cols-4 gap-1.5">
                  {Object.entries(COMPOUND_BUTTONS).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setCompoundCategory(key)}
                      className={`rounded-md border px-2 py-1.5 text-xs transition-colors ${
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

              {/* Tire size combobox */}
              <div className="grid grid-cols-2 gap-3">
                <div ref={tireSizeRef} className="relative">
                  <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                    Size
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={tireSize}
                      onChange={(e) => setTireSize(e.target.value)}
                      onFocus={() => setTireSizeOpen(true)}
                      placeholder="e.g. 255/40R17"
                      className={inputClass}
                    />
                    <button
                      type="button"
                      onClick={() => setTireSizeOpen((v) => !v)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                    >
                      <ChevronDown className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  {tireSizeOpen && commonSizes && (
                    <div className="absolute z-10 mt-1 max-h-40 w-full overflow-y-auto rounded-md border border-[var(--cata-border)] bg-[var(--bg-surface)] shadow-lg">
                      {commonSizes
                        .filter((s) => !tireSize || s.toLowerCase().includes(tireSize.toLowerCase()))
                        .map((size) => (
                          <button
                            key={size}
                            type="button"
                            onClick={() => {
                              setTireSize(size);
                              setTireSizeOpen(false);
                            }}
                            className="w-full px-3 py-1.5 text-left text-sm text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]"
                          >
                            {size}
                          </button>
                        ))}
                    </div>
                  )}
                </div>

                {/* Pressure */}
                <div>
                  <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                    Pressure (psi)
                  </label>
                  <input
                    type="number"
                    value={tirePressure}
                    onChange={(e) => setTirePressure(e.target.value)}
                    placeholder="e.g. 32"
                    className={inputClass}
                  />
                </div>
              </div>
            </div>
          </fieldset>

          {/* --- BRAKES --- */}
          <fieldset>
            <legend className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Brakes
            </legend>
            <div className="flex flex-col gap-3">
              {/* Pad search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  value={padQuery}
                  onChange={(e) => {
                    setPadQuery(e.target.value);
                    setSelectedPad(null);
                  }}
                  placeholder="Search brake pads (e.g. Hawk, DTC-60)"
                  className={`${inputClass} pl-9`}
                />
              </div>

              {/* Pad search results */}
              {searchingPads && (
                <p className="text-xs text-[var(--text-muted)]">Searching...</p>
              )}
              {padResults && padResults.length > 0 && !selectedPad && (
                <div className="max-h-36 overflow-y-auto rounded-md border border-[var(--cata-border)]">
                  {padResults.map((pad, i) => (
                    <button
                      key={`${pad.model}-${i}`}
                      type="button"
                      onClick={() => handleSelectPad(pad)}
                      className="flex w-full items-center justify-between px-3 py-2 text-left transition-colors hover:bg-[var(--bg-elevated)]"
                    >
                      <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">{pad.model}</p>
                        <p className="text-xs text-[var(--text-muted)]">
                          {pad.category} | {pad.temp_range}
                        </p>
                      </div>
                      <span className="text-xs text-[var(--text-muted)]">{pad.brand}</span>
                    </button>
                  ))}
                </div>
              )}

              {selectedPad && (
                <div className="rounded-md border border-[var(--cata-accent)]/30 bg-[var(--cata-accent)]/5 p-2">
                  <p className="text-sm font-medium text-[var(--text-primary)]">{selectedPad.model}</p>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {selectedPad.brand && `${selectedPad.brand} | `}{selectedPad.temp_range}
                  </p>
                </div>
              )}

              {/* Brake fluid dropdown */}
              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                  Brake Fluid
                </label>
                <select
                  value={brakeFluid}
                  onChange={(e) => setBrakeFluid(e.target.value)}
                  className={`${inputClass} appearance-none`}
                >
                  <option value="">Select brake fluid...</option>
                  {commonFluids?.map((fluid) => (
                    <option key={fluid} value={fluid}>{fluid}</option>
                  ))}
                </select>
              </div>
            </div>
          </fieldset>

          {/* Notes */}
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              Notes
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Barber Motorsports Park setup"
              className={inputClass}
            />
          </div>
        </div>

        <DialogFooter className="mt-2">
          <div className="flex w-full gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="border-[var(--cata-border)] text-[var(--text-secondary)]"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isSaving || (!tireQuery && !selectedTire)}
              className="flex-1 bg-[var(--cata-accent)] text-white hover:opacity-90"
            >
              {isSaving ? 'Saving...' : isEdit ? 'Update Profile' : 'Save Profile'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
