'use client';

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, X, CheckCircle2 } from 'lucide-react';
import { useSession } from 'next-auth/react';
import { cn } from '@/lib/utils';
import {
  useCreateProfile,
  useAssignEquipment,
  useAssignEquipmentInline,
  useVehicleSearch,
  useEquipmentProfiles,
  useTireSearch,
  useCommonTireSizes,
} from '@/hooks/useEquipment';
import { getVehicleSpec } from '@/lib/api';
import type { VehicleSpec, VehicleSearchResult, EquipmentProfile } from '@/lib/types';

interface EquipmentInterstitialProps {
  sessionId: string;
  onComplete: () => void;
}

const COMPOUND_OPTIONS = [
  { value: 'street', label: 'Street' },
  { value: 'super_200tw', label: '200TW' },
  { value: 'r_comp', label: 'R-Comp' },
  { value: 'slick', label: 'Slick' },
] as const;

// Estimated mu values per compound category (mirrors backend CATEGORY_MU_DEFAULTS)
const COMPOUND_MU: Record<string, number> = {
  street: 0.85,
  super_200tw: 1.10,
  r_comp: 1.35,
  slick: 1.50,
};

export function EquipmentInterstitial({ sessionId, onComplete }: EquipmentInterstitialProps) {
  const { status: authStatus } = useSession();
  const isAuthenticated = authStatus === 'authenticated';

  const { data: profilesData } = useEquipmentProfiles();
  const existingProfiles = profilesData?.items ?? [];

  const [vehicleQuery, setVehicleQuery] = useState('');
  const [selectedVehicle, setSelectedVehicle] = useState<VehicleSpec | null>(null);
  const { data: vehicleResults = [] } = useVehicleSearch(vehicleQuery);

  const [compound, setCompound] = useState<string>('');
  const [tireModel, setTireModel] = useState('');
  const [tireModelCompound, setTireModelCompound] = useState<string | null>(null);
  const [tireSize, setTireSize] = useState('');
  const [tireModelFocused, setTireModelFocused] = useState(false);
  const [tireSizeFocused, setTireSizeFocused] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const { data: tireResults = [] } = useTireSearch(tireModel.length >= 2 ? tireModel : '');
  const { data: commonTireSizes = [] } = useCommonTireSizes();

  const createProfile = useCreateProfile();
  const assignEquipment = useAssignEquipment();
  const assignEquipmentInline = useAssignEquipmentInline();

  const profileName = selectedVehicle
    ? `${selectedVehicle.make} ${selectedVehicle.model} – ${compound || 'Street'}`
    : compound
      ? `${compound} setup`
      : 'My Setup';

  // Validate tire size format: width/aspectRdiameter (e.g. 205/50R16)
  const validTireSize = /^\d{3}\/\d{2}R\d{2}$/i.test(tireSize.trim());
  const canSave = validTireSize && compound.length > 0;

  const clearVehicle = useCallback(() => {
    setSelectedVehicle(null);
    setVehicleQuery('');
    setTireSize('');
  }, []);

  const handleSelectVehicle = useCallback(
    async (result: VehicleSearchResult) => {
      setVehicleQuery(`${result.make} ${result.model}`);
      try {
        const spec = await getVehicleSpec(result.make, result.model, result.generation);
        setSelectedVehicle(spec);
        if (spec.stock_tire_size_front && !tireSize) {
          setTireSize(spec.stock_tire_size_front);
        }
      } catch {
        // Fall back to lightweight data if full spec fetch fails
        setSelectedVehicle({
          ...result,
          wheelbase_m: 0,
          track_width_front_m: 0,
          track_width_rear_m: 0,
          cg_height_m: 0,
          weight_dist_front_pct: 0,
          torque_nm: 0,
          has_aero: false,
          stock_tire_size_front: null,
          stock_tire_size_rear: null,
          notes: null,
        });
      }
    },
    [tireSize],
  );

  const handleSave = useCallback(async () => {
    if (!canSave || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      const mu = COMPOUND_MU[compound] ?? 0.93;
      const model = tireModel.trim() || 'OEM / Stock';
      if (isAuthenticated) {
        // Authenticated: create a named persistent profile and assign it
        const profile = await createProfile.mutateAsync({
          name: profileName,
          tires: {
            model,
            compound_category: compound,
            size: tireSize.trim(),
            estimated_mu: mu,
            mu_source: 'formula_estimate',
            mu_confidence: 'low',
            treadwear_rating: null,
            pressure_psi: null,
            brand: null,
            age_sessions: null,
          },
          vehicle: selectedVehicle ?? null,
          // Only auto-default when the profiles query has resolved to empty
          is_default: profilesData !== undefined && existingProfiles.length === 0,
        });
        await assignEquipment.mutateAsync({ sessionId, body: { profile_id: profile.id } });
      } else {
        // Anonymous: inline assignment — no persistent profile, migrated on sign-up
        await assignEquipmentInline.mutateAsync({
          sessionId,
          body: {
            compound_category: compound,
            tire_size: tireSize.trim(),
            tire_model: model !== 'OEM / Stock' ? model : undefined,
            estimated_mu: mu,
          },
        });
      }
      onComplete();
    } catch {
      setSaving(false);
      setSaveError('Failed to save. Please try again or skip for now.');
    }
  }, [
    canSave,
    saving,
    compound,
    tireModel,
    tireSize,
    profileName,
    selectedVehicle,
    isAuthenticated,
    createProfile,
    assignEquipment,
    assignEquipmentInline,
    sessionId,
    onComplete,
    profilesData,
    existingProfiles.length,
  ]);

  const handleQuickPick = useCallback(
    async (profile: EquipmentProfile) => {
      if (saving) return;
      setSaving(true);
      setSaveError(null);
      try {
        await assignEquipment.mutateAsync({ sessionId, body: { profile_id: profile.id } });
        onComplete();
      } catch {
        setSaving(false);
        setSaveError('Failed to apply setup. Please try again.');
      }
    },
    [assignEquipment, sessionId, onComplete, saving],
  );

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 px-4 py-8 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      role="dialog"
      aria-modal="true"
      aria-label="Car setup"
      onKeyDown={(e) => { if (e.key === 'Escape') onComplete(); }}
    >
      <motion.div
        className="w-full max-w-sm rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 shadow-2xl"
        initial={{ opacity: 0, y: 24, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.35, delay: 0.05, ease: 'easeOut' }}
      >
        {/* Header */}
        <h2 className="text-center font-[family-name:var(--font-display)] text-lg font-bold text-[var(--text-primary)]">
          What are you driving?
        </h2>
        <p className="mt-1.5 text-center text-sm text-[var(--text-secondary)]">
          Calibrates your optimal lap time. You can update this anytime.
        </p>

        {/* Quick-pick existing profiles */}
        {existingProfiles.length > 0 && (
          <div className="mt-5">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
              Use existing setup
            </p>
            <div className="flex flex-col gap-2">
              {existingProfiles.slice(0, 2).map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => handleQuickPick(p)}
                  disabled={saving}
                  className="flex items-center gap-3 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-3 py-2.5 text-left text-sm text-[var(--text-primary)] transition-colors hover:border-[var(--cata-accent)]/50 disabled:opacity-50"
                >
                  <CheckCircle2 className="size-4 shrink-0 text-[var(--cata-accent)]" />
                  <span className="min-w-0 truncate font-medium">{p.name}</span>
                </button>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-2">
              <div className="h-px flex-1 bg-[var(--cata-border)]" />
              <span className="text-xs text-[var(--text-muted)]">or new setup</span>
              <div className="h-px flex-1 bg-[var(--cata-border)]" />
            </div>
          </div>
        )}

        {/* Vehicle search */}
        <div className="mt-5">
          <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            Vehicle <span className="text-[var(--text-muted)]">(optional)</span>
          </label>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              value={vehicleQuery}
              onChange={(e) => {
                setVehicleQuery(e.target.value);
                if (!e.target.value) clearVehicle();
              }}
              placeholder="Search vehicle (e.g. Miata ND)"
              className="w-full rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] py-2 pl-8 pr-8 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--cata-accent)]/60 focus:outline-none"
            />
            {vehicleQuery && (
              <button
                type="button"
                onClick={clearVehicle}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                aria-label="Clear vehicle"
              >
                <X className="size-3.5" />
              </button>
            )}
          </div>

          {/* Dropdown results */}
          <AnimatePresence>
            {vehicleResults.length > 0 && !selectedVehicle && (
              <motion.ul
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="mt-1 max-h-40 overflow-y-auto rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] shadow-lg"
              >
                {vehicleResults.slice(0, 6).map((v: VehicleSearchResult) => (
                  <li key={v.slug}>
                    <button
                      type="button"
                      onClick={() => handleSelectVehicle(v)}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--bg-surface)]"
                    >
                      <span className="font-medium text-[var(--text-primary)]">
                        {v.make} {v.model}
                      </span>
                      <span className="ml-1.5 text-xs text-[var(--text-muted)]">
                        {v.generation} · {v.hp}hp · {v.drivetrain}
                      </span>
                    </button>
                  </li>
                ))}
              </motion.ul>
            )}
          </AnimatePresence>

          {/* Selected vehicle chip */}
          {selectedVehicle && (
            <div className="mt-1.5 flex items-center gap-2 rounded-md border border-[var(--cata-accent)]/30 bg-[var(--cata-accent)]/10 px-3 py-1.5 text-xs text-[var(--text-primary)]">
              <span className="flex-1">
                {selectedVehicle.make} {selectedVehicle.model} {selectedVehicle.generation}
                <span className="ml-1.5 text-[var(--text-muted)]">
                  {selectedVehicle.hp}hp · {selectedVehicle.weight_kg}kg
                </span>
              </span>
              <button
                type="button"
                onClick={clearVehicle}
                className="text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                aria-label="Clear vehicle"
              >
                <X className="size-3" />
              </button>
            </div>
          )}
        </div>

        {/* Compound picker */}
        <div className="mt-4">
          <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            Tire type <span className="text-red-400">*</span>
          </label>
          <div className="flex flex-wrap gap-1.5">
            {COMPOUND_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setCompound(opt.value)}
                className={cn(
                  'rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                  compound === opt.value
                    ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/15 text-[var(--cata-accent)]'
                    : 'border-[var(--cata-border)] text-[var(--text-secondary)] hover:border-[var(--cata-border-hover)]',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {tireModelCompound && compound && compound !== tireModelCompound && (
            <p className="mt-1.5 text-xs text-amber-400">
              Selected tire is typically{' '}
              {COMPOUND_OPTIONS.find((o) => o.value === tireModelCompound)?.label ?? tireModelCompound}
              . Override if you know your setup differs.
            </p>
          )}
        </div>

        {/* Tire model (optional) */}
        <div className="mt-4 relative">
          <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            Tire model <span className="text-[var(--text-muted)]">(optional)</span>
          </label>
          <input
            type="text"
            value={tireModel}
            onChange={(e) => { setTireModel(e.target.value); setTireModelFocused(true); setTireModelCompound(null); }}
            onFocus={() => setTireModelFocused(true)}
            onBlur={() => setTimeout(() => setTireModelFocused(false), 150)}
            placeholder="e.g. RE-71RS, RT660, RS4"
            className="w-full rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--cata-accent)]/60 focus:outline-none"
          />
          <AnimatePresence>
            {tireModelFocused && tireResults.length > 0 && tireModel.length >= 2 && (
              <motion.ul
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="absolute left-0 right-0 z-10 mt-1 max-h-32 overflow-y-auto rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] shadow-lg"
              >
                {tireResults.slice(0, 6).map((tire, i) => (
                  <li key={`${tire.model}-${i}`}>
                    <button
                      type="button"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => {
                        setTireModel(tire.model);
                        setTireModelFocused(false);
                        if (tire.compound_category) {
                          setCompound(tire.compound_category);
                          setTireModelCompound(tire.compound_category);
                        }
                        if (tire.size && tire.size !== 'varies' && !tireSize) setTireSize(tire.size);
                      }}
                      className="w-full px-3 py-1.5 text-left text-sm hover:bg-[var(--bg-surface)]"
                    >
                      <span className="font-medium text-[var(--text-primary)]">{tire.model}</span>
                      {tire.treadwear_rating ? (
                        <span className="ml-1.5 text-xs text-[var(--text-muted)]">TW {tire.treadwear_rating}</span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </div>

        {/* Tire size */}
        <div className="mt-4 relative">
          <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            Tire size <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={tireSize}
            onChange={(e) => setTireSize(e.target.value)}
            onFocus={() => setTireSizeFocused(true)}
            onBlur={() => setTimeout(() => setTireSizeFocused(false), 150)}
            placeholder="e.g. 205/50R16"
            className="w-full rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--cata-accent)]/60 focus:outline-none"
          />
          {tireSizeFocused && commonTireSizes.length > 0 && (
            <ul className="absolute left-0 right-0 z-10 mt-1 max-h-32 overflow-y-auto rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] shadow-lg">
              {commonTireSizes
                .filter((s) => !tireSize || s.toLowerCase().includes(tireSize.toLowerCase()))
                .slice(0, 8)
                .map((size) => (
                  <li key={size}>
                    <button
                      type="button"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => { setTireSize(size); setTireSizeFocused(false); }}
                      className="w-full px-3 py-1.5 text-left text-sm text-[var(--text-primary)] hover:bg-[var(--bg-surface)]"
                    >
                      {size}
                    </button>
                  </li>
                ))}
            </ul>
          )}
          {selectedVehicle?.stock_tire_size_rear &&
            selectedVehicle.stock_tire_size_rear !== selectedVehicle.stock_tire_size_front && (
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                Rear: {selectedVehicle.stock_tire_size_rear} (staggered)
              </p>
            )}
        </div>

        {/* Save error */}
        {saveError && (
          <p className="mt-3 text-xs text-red-400">{saveError}</p>
        )}

        {/* CTA buttons */}
        <div className="mt-6 flex flex-col gap-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={!canSave || saving}
            className="min-h-[48px] w-full rounded-lg bg-[var(--cata-accent)] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-[var(--cata-accent)]/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? 'Saving…' : 'Save & Continue'}
          </button>
          <button
            type="button"
            onClick={onComplete}
            disabled={saving}
            className="min-h-[44px] w-full rounded-lg border border-[var(--cata-border)] px-4 py-2.5 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:opacity-40"
          >
            Skip for now
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
