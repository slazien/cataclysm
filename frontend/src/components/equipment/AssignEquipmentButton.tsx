'use client';

import { useState } from 'react';
import { Settings2, ChevronDown, Check, Pencil } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUiStore } from '@/stores';
import {
  useEquipmentProfiles,
  useSessionEquipment,
  useAssignEquipment,
} from '@/hooks/useEquipment';
import { EquipmentSetupModal } from './EquipmentSetupModal';
import type { EquipmentProfile } from '@/lib/types';

interface AssignEquipmentButtonProps {
  sessionId: string;
}

export function AssignEquipmentButton({ sessionId }: AssignEquipmentButtonProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<EquipmentProfile | null>(null);
  const toggleSettingsPanel = useUiStore((s) => s.toggleSettingsPanel);

  const { data: profilesData } = useEquipmentProfiles();
  const { data: currentEquipment } = useSessionEquipment(sessionId);
  const assignMutation = useAssignEquipment();

  const profiles = profilesData?.items ?? [];

  function handleAssign(profileId: string) {
    assignMutation.mutate(
      { sessionId, body: { profile_id: profileId } },
      { onSuccess: () => setDropdownOpen(false) },
    );
  }

  function handleManageProfiles() {
    setDropdownOpen(false);
    toggleSettingsPanel();
  }

  function handleEditProfile(profile: EquipmentProfile) {
    setDropdownOpen(false);
    setEditingProfile(profile);
    setEditModalOpen(true);
  }

  // If equipment is assigned, show a compact badge
  if (currentEquipment) {
    return (
      <div className="relative">
        <button
          type="button"
          onClick={() => setDropdownOpen((v) => !v)}
          className="flex items-center gap-1.5 rounded-md border border-[var(--cata-border)] bg-[var(--bg-surface)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--text-muted)]/40 hover:bg-[var(--bg-elevated)]"
        >
          <Settings2 className="h-3 w-3" />
          <span className="max-w-[120px] truncate">
            {currentEquipment.tires.model}
          </span>
          <ChevronDown className="h-3 w-3" />
        </button>

        {dropdownOpen && (
          <EquipmentDropdown
            profiles={profiles}
            currentProfileId={currentEquipment.profile_id}
            onSelect={handleAssign}
            onClose={() => setDropdownOpen(false)}
            onManageProfiles={handleManageProfiles}
            onEditProfile={handleEditProfile}
          />
        )}
        <EquipmentSetupModal
          open={editModalOpen}
          onOpenChange={setEditModalOpen}
          editProfile={editingProfile}
        />
      </div>
    );
  }

  // No equipment assigned — show "Add Equipment" button
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          if (profiles.length > 0) {
            setDropdownOpen((v) => !v);
          } else {
            toggleSettingsPanel();
          }
        }}
        className="flex items-center gap-1.5 rounded-md border border-dashed border-[var(--cata-border)] bg-[var(--bg-surface)] px-2.5 py-1 text-xs text-[var(--text-muted)] transition-colors hover:border-[var(--text-secondary)] hover:text-[var(--text-secondary)]"
      >
        <Settings2 className="h-3 w-3" />
        Equipment
      </button>

      {dropdownOpen && (
        <EquipmentDropdown
          profiles={profiles}
          currentProfileId={null}
          onSelect={handleAssign}
          onClose={() => setDropdownOpen(false)}
          onManageProfiles={handleManageProfiles}
          onEditProfile={handleEditProfile}
        />
      )}
      <EquipmentSetupModal
        open={editModalOpen}
        onOpenChange={setEditModalOpen}
        editProfile={editingProfile}
      />
    </div>
  );
}

// --- Dropdown ---

interface EquipmentDropdownProps {
  profiles: EquipmentProfile[];
  currentProfileId: string | null;
  onSelect: (profileId: string) => void;
  onClose: () => void;
  onManageProfiles: () => void;
  onEditProfile: (profile: EquipmentProfile) => void;
}

function EquipmentDropdown({
  profiles,
  currentProfileId,
  onSelect,
  onClose,
  onManageProfiles,
  onEditProfile,
}: EquipmentDropdownProps) {
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
      />
      <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] py-1 shadow-xl">
        <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Equipment Profiles
        </p>
        {profiles.map((profile) => (
          <div
            key={profile.id}
            className="flex items-center justify-between px-3 py-2 transition-colors hover:bg-[var(--bg-elevated)]"
          >
            <button
              type="button"
              onClick={() => onSelect(profile.id)}
              className="flex flex-1 items-center justify-between text-left"
            >
              <div>
                <p className="text-sm text-[var(--text-primary)]">{profile.name}</p>
                <p className="text-xs text-[var(--text-muted)]">
                  {profile.tires.model}
                </p>
              </div>
              {profile.id === currentProfileId && (
                <Check className="h-3.5 w-3.5 text-[var(--cata-accent)]" />
              )}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onEditProfile(profile);
              }}
              className="ml-2 rounded p-1 text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-surface)] hover:text-[var(--text-secondary)]"
              title="Edit profile"
            >
              <Pencil className="h-3 w-3" />
            </button>
          </div>
        ))}
        <div className="mx-2 my-1 border-t border-[var(--cata-border)]" />
        <button
          type="button"
          onClick={onManageProfiles}
          className="flex w-full items-center gap-2 px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)]"
        >
          <Settings2 className="h-3.5 w-3.5" />
          Manage Profiles
        </button>
      </div>
    </>
  );
}
