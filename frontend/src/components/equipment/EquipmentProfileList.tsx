'use client';

import { useState } from 'react';
import { Pencil, Trash2, Plus, Star } from 'lucide-react';
import { useEquipmentProfiles, useDeleteProfile, useUpdateProfile } from '@/hooks/useEquipment';
import { EquipmentSetupModal } from './EquipmentSetupModal';
import type { EquipmentProfile } from '@/lib/types';

const COMPOUND_LABELS: Record<string, string> = {
  street: 'Street',
  '200tw': '200TW',
  'r-comp': 'R-Comp',
  slick: 'Slick',
};

export function EquipmentProfileList() {
  const { data: profilesData, isPending } = useEquipmentProfiles();
  const deleteMutation = useDeleteProfile();
  const updateMutation = useUpdateProfile();
  const [modalOpen, setModalOpen] = useState(false);
  const [editProfile, setEditProfile] = useState<EquipmentProfile | null>(null);

  const profiles = profilesData?.items ?? [];

  function handleEdit(profile: EquipmentProfile) {
    setEditProfile(profile);
    setModalOpen(true);
  }

  function handleDelete(profileId: string, name: string) {
    if (window.confirm(`Delete profile "${name}"?`)) {
      deleteMutation.mutate(profileId);
    }
  }

  function handleCreateNew() {
    setEditProfile(null);
    setModalOpen(true);
  }

  function handleToggleDefault(profile: EquipmentProfile) {
    updateMutation.mutate({
      profileId: profile.id,
      body: {
        name: profile.name,
        tires: profile.tires,
        vehicle: profile.vehicle ?? null,
        brakes: profile.brakes ?? null,
        suspension: profile.suspension ?? null,
        vehicle_overrides: profile.vehicle_overrides ?? {},
        notes: profile.notes,
        is_default: !profile.is_default,
      },
    });
  }

  function formatSummary(profile: EquipmentProfile): string {
    const parts: string[] = [];

    if (profile.tires?.model) {
      const compound = profile.tires.compound_category
        ? COMPOUND_LABELS[profile.tires.compound_category] ?? profile.tires.compound_category
        : null;
      parts.push(compound ? `${profile.tires.model} (${compound})` : profile.tires.model);
    }

    if (profile.brakes?.compound) {
      parts.push(profile.brakes.compound);
    }

    return parts.join(' · ') || 'No equipment configured';
  }

  return (
    <fieldset className="mb-6 min-w-0">
      <legend className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
        Equipment Profiles
      </legend>

      {isPending ? (
        <div className="space-y-2 animate-pulse">
          {[1, 2].map((i) => (
            <div key={i} className="h-14 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-elevated)]" />
          ))}
        </div>
      ) : profiles.length === 0 ? (
        <p className="py-4 text-center text-sm text-[var(--text-secondary)]">
          No equipment profiles yet
        </p>
      ) : (
        <div className="space-y-2">
          {profiles.map((profile) => (
            <div
              key={profile.id}
              className="flex items-center justify-between rounded-lg border border-[var(--cata-border)] px-3 py-2 transition-colors hover:border-[var(--text-muted)]/40"
            >
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1 truncate text-sm font-medium text-[var(--text-primary)]">
                  {profile.is_default && (
                    <Star className="h-3 w-3 shrink-0 fill-amber-400 text-amber-400" />
                  )}
                  {profile.name}
                </p>
                <p className="truncate text-xs text-[var(--text-secondary)]">
                  {formatSummary(profile)}
                </p>
              </div>
              <div className="ml-2 flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={() => handleToggleDefault(profile)}
                  className={`flex h-7 w-7 items-center justify-center rounded-md transition-colors ${
                    profile.is_default
                      ? 'text-amber-400 hover:bg-[var(--bg-elevated)] hover:text-amber-300'
                      : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-amber-400'
                  }`}
                  title={profile.is_default ? 'Remove default' : 'Set as default'}
                >
                  <Star className={`h-3.5 w-3.5 ${profile.is_default ? 'fill-current' : ''}`} />
                </button>
                <button
                  type="button"
                  onClick={() => handleEdit(profile)}
                  className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                  title="Edit profile"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(profile.id, profile.name)}
                  disabled={deleteMutation.isPending}
                  className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-red-500/10 hover:text-red-400"
                  title="Delete profile"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={handleCreateNew}
        className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-[var(--cata-border)] px-3 py-2 text-xs text-[var(--text-secondary)] transition-colors hover:border-[var(--text-secondary)] hover:text-[var(--text-secondary)]"
      >
        <Plus className="h-3.5 w-3.5" />
        New Profile
      </button>

      <EquipmentSetupModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        editProfile={editProfile}
      />
    </fieldset>
  );
}
