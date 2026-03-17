'use client';

import { useState } from 'react';
import { Settings2, ChevronDown, Check, Pencil, Star, Loader2 } from 'lucide-react';
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
  const addToast = useUiStore((s) => s.addToast);

  const { data: profilesData } = useEquipmentProfiles();
  const { data: currentEquipment } = useSessionEquipment(sessionId);
  const assignMutation = useAssignEquipment();

  const profiles = profilesData?.items ?? [];

  // Track which profile is being switched to (for loading indicator)
  const pendingProfileId = assignMutation.isPending
    ? (assignMutation.variables?.body as { profile_id?: string })?.profile_id ?? null
    : null;

  function handleAssign(profileId: string) {
    if (assignMutation.isPending) return;
    assignMutation.mutate(
      { sessionId, body: { profile_id: profileId } },
      {
        onSuccess: () => setDropdownOpen(false),
        onError: () => {
          setDropdownOpen(false);
          addToast({ message: 'Equipment switch failed — please try again', type: 'info' });
        },
      },
    );
  }

  function handleManageProfiles() {
    if (assignMutation.isPending) return;
    setDropdownOpen(false);
    toggleSettingsPanel();
  }

  function handleEditProfile(profile: EquipmentProfile) {
    if (assignMutation.isPending) return;
    setDropdownOpen(false);
    setEditingProfile(profile);
    setEditModalOpen(true);
  }

  function handleDropdownClose() {
    // Don't allow closing while mutation is in-flight — user needs to see the result
    if (assignMutation.isPending) return;
    setDropdownOpen(false);
  }

  // If equipment is assigned, show a compact badge
  if (currentEquipment) {
    return (
      <div className="relative">
        <button
          type="button"
          onClick={() => setDropdownOpen((v) => !v)}
          className="flex min-h-[44px] items-center gap-1.5 rounded-md border border-[var(--cata-border)] bg-[var(--bg-surface)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--text-muted)]/40 hover:bg-[var(--bg-elevated)] sm:min-h-0"
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
            pendingProfileId={pendingProfileId}
            onSelect={handleAssign}
            onClose={handleDropdownClose}
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
        className="flex min-h-[44px] items-center gap-1.5 rounded-md border border-dashed border-[var(--cata-border)] bg-[var(--bg-surface)] px-2.5 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:border-[var(--text-secondary)] hover:text-[var(--text-secondary)] sm:min-h-0"
      >
        <Settings2 className="h-3 w-3" />
        Add car <span className="hidden sm:inline">(optional)</span>
      </button>

      {dropdownOpen && (
        <EquipmentDropdown
          profiles={profiles}
          currentProfileId={null}
          pendingProfileId={pendingProfileId}
          onSelect={handleAssign}
          onClose={handleDropdownClose}
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
  pendingProfileId: string | null;
  onSelect: (profileId: string) => void;
  onClose: () => void;
  onManageProfiles: () => void;
  onEditProfile: (profile: EquipmentProfile) => void;
}

function EquipmentDropdown({
  profiles,
  currentProfileId,
  pendingProfileId,
  onSelect,
  onClose,
  onManageProfiles,
  onEditProfile,
}: EquipmentDropdownProps) {
  const isSwitching = pendingProfileId != null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
      />
      <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] py-1 shadow-xl">
        <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          Equipment Profiles
        </p>
        {profiles.map((profile) => {
          const isCurrent = profile.id === currentProfileId;
          const isPending = profile.id === pendingProfileId;

          return (
            <div
              key={profile.id}
              className={cn(
                'flex items-center justify-between px-3 py-2 transition-colors hover:bg-[var(--bg-elevated)]',
                isPending && 'bg-[var(--bg-elevated)]',
              )}
            >
              <button
                type="button"
                onClick={() => onSelect(profile.id)}
                disabled={isCurrent || isSwitching}
                className="flex flex-1 items-center justify-between text-left disabled:opacity-50"
              >
                <div>
                  <p className="flex items-center gap-1 text-sm text-[var(--text-primary)]">
                    {profile.name}
                    {profile.is_default && (
                      <Star className="h-2.5 w-2.5 shrink-0 fill-amber-400 text-amber-400" />
                    )}
                  </p>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {profile.tires.model}
                  </p>
                </div>
                {isCurrent && !isPending && (
                  <Check className="h-3.5 w-3.5 text-[var(--cata-accent)]" />
                )}
                {isPending && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--cata-accent)]" />
                )}
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onEditProfile(profile);
                }}
                disabled={isSwitching}
                className="ml-2 rounded p-1 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-surface)] hover:text-[var(--text-secondary)] disabled:opacity-30"
                title="Edit profile"
              >
                <Pencil className="h-3 w-3" />
              </button>
            </div>
          );
        })}
        <div className="mx-2 my-1 border-t border-[var(--cata-border)]" />
        <button
          type="button"
          onClick={onManageProfiles}
          disabled={isSwitching}
          className="flex w-full items-center gap-2 px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] disabled:opacity-50"
        >
          <Settings2 className="h-3.5 w-3.5" />
          Manage Profiles
        </button>
      </div>
    </>
  );
}
