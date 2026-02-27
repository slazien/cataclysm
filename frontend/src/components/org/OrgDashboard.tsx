'use client';

import { useState, useCallback } from 'react';
import {
  useOrg,
  useOrgMembers,
  useOrgEvents,
  useAddMember,
  useRemoveMember,
  useCreateEvent,
  useDeleteEvent,
} from '@/hooks/useOrganization';
import { RunGroupManager } from './RunGroupManager';
import {
  Loader2,
  Building2,
  Users,
  Calendar,
  Plus,
  Trash2,
  UserPlus,
  X,
  ChevronRight,
  Shield,
  GraduationCap,
  Crown,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface OrgDashboardProps {
  slug: string;
}

type Tab = 'members' | 'events';

const ROLE_ICONS: Record<string, typeof Crown> = {
  owner: Crown,
  instructor: Shield,
  student: GraduationCap,
};

const ROLE_COLORS: Record<string, string> = {
  owner: 'text-amber-400',
  instructor: 'text-blue-400',
  student: 'text-[var(--text-secondary)]',
};

export function OrgDashboard({ slug }: OrgDashboardProps) {
  const { data: org, isLoading, error } = useOrg(slug);
  const { data: membersData } = useOrgMembers(slug);
  const { data: eventsData } = useOrgEvents(slug);

  const addMemberMutation = useAddMember();
  const removeMemberMutation = useRemoveMember();
  const createEventMutation = useCreateEvent();
  const deleteEventMutation = useDeleteEvent();

  const [activeTab, setActiveTab] = useState<Tab>('members');
  const [showAddMember, setShowAddMember] = useState(false);
  const [showAddEvent, setShowAddEvent] = useState(false);

  // Add member form state
  const [memberUserId, setMemberUserId] = useState('');
  const [memberRole, setMemberRole] = useState('student');
  const [memberRunGroup, setMemberRunGroup] = useState('');

  // Add event form state
  const [eventName, setEventName] = useState('');
  const [eventTrack, setEventTrack] = useState('');
  const [eventDate, setEventDate] = useState('');
  const [eventRunGroups, setEventRunGroups] = useState<string[]>([]);

  const handleAddMember = useCallback(async () => {
    if (!memberUserId.trim()) return;
    await addMemberMutation.mutateAsync({
      slug,
      userId: memberUserId.trim(),
      role: memberRole,
      runGroup: memberRunGroup || undefined,
    });
    setMemberUserId('');
    setMemberRole('student');
    setMemberRunGroup('');
    setShowAddMember(false);
  }, [slug, memberUserId, memberRole, memberRunGroup, addMemberMutation]);

  const handleRemoveMember = useCallback(
    async (userId: string) => {
      if (!confirm('Remove this member from the organization?')) return;
      await removeMemberMutation.mutateAsync({ slug, userId });
    },
    [slug, removeMemberMutation],
  );

  const handleCreateEvent = useCallback(async () => {
    if (!eventName.trim() || !eventTrack.trim() || !eventDate) return;
    await createEventMutation.mutateAsync({
      slug,
      name: eventName.trim(),
      trackName: eventTrack.trim(),
      eventDate: new Date(eventDate).toISOString(),
      runGroups: eventRunGroups.length > 0 ? eventRunGroups : undefined,
    });
    setEventName('');
    setEventTrack('');
    setEventDate('');
    setEventRunGroups([]);
    setShowAddEvent(false);
  }, [slug, eventName, eventTrack, eventDate, eventRunGroups, createEventMutation]);

  const handleDeleteEvent = useCallback(
    async (eventId: string) => {
      if (!confirm('Delete this event?')) return;
      await deleteEventMutation.mutateAsync({ slug, eventId });
    },
    [slug, deleteEventMutation],
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--text-muted)]" />
      </div>
    );
  }

  if (error || !org) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <Building2 className="h-8 w-8 text-[var(--text-muted)]" />
        <p className="text-sm text-[var(--color-brake)]">
          Organization not found or you don&apos;t have access.
        </p>
      </div>
    );
  }

  const members = membersData?.members ?? [];
  const events = eventsData?.events ?? [];

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-4 lg:p-8">
      {/* Org header */}
      <div className="flex items-center gap-4">
        {org.logo_url ? (
          <img
            src={org.logo_url}
            alt={org.name}
            className="h-12 w-12 rounded-lg object-cover"
          />
        ) : (
          <div
            className="flex h-12 w-12 items-center justify-center rounded-lg text-lg font-bold text-white"
            style={{ backgroundColor: org.brand_color || '#6366f1' }}
          >
            {org.name.charAt(0).toUpperCase()}
          </div>
        )}
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">{org.name}</h1>
          <p className="text-sm text-[var(--text-muted)]">
            {org.member_count} member{org.member_count !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-[var(--cata-border)]">
        {([
          { key: 'members' as Tab, label: 'Members', icon: Users, count: members.length },
          { key: 'events' as Tab, label: 'Events', icon: Calendar, count: events.length },
        ]).map(({ key, label, icon: Icon, count }) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveTab(key)}
            className={cn(
              'flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
              activeTab === key
                ? 'border-[var(--color-throttle)] text-[var(--text-primary)]'
                : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
            <span className="rounded-full bg-[var(--bg-elevated)] px-2 py-0.5 text-xs">
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* Members tab */}
      {activeTab === 'members' && (
        <div className="flex flex-col gap-4">
          {/* Add member button */}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setShowAddMember(!showAddMember)}
              className={cn(
                'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                showAddMember
                  ? 'border-[var(--color-brake)]/30 text-[var(--color-brake)]'
                  : 'border-[var(--cata-border)] bg-[var(--bg-surface)] text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]',
              )}
            >
              {showAddMember ? (
                <X className="h-3.5 w-3.5" />
              ) : (
                <UserPlus className="h-3.5 w-3.5" />
              )}
              {showAddMember ? 'Cancel' : 'Add Member'}
            </button>
          </div>

          {/* Add member form */}
          {showAddMember && (
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
              <h3 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
                Add Member
              </h3>
              <div className="flex flex-col gap-3">
                <input
                  type="text"
                  value={memberUserId}
                  onChange={(e) => setMemberUserId(e.target.value)}
                  placeholder="User ID"
                  className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--text-muted)] focus:outline-none"
                />
                <div className="flex gap-2">
                  {(['student', 'instructor', 'owner'] as const).map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setMemberRole(r)}
                      className={cn(
                        'rounded-lg border px-3 py-1.5 text-xs capitalize transition-colors',
                        memberRole === r
                          ? 'border-[var(--color-throttle)]/40 bg-[var(--color-throttle)]/10 text-[var(--color-throttle)]'
                          : 'border-[var(--cata-border)] text-[var(--text-secondary)]',
                      )}
                    >
                      {r}
                    </button>
                  ))}
                </div>
                <input
                  type="text"
                  value={memberRunGroup}
                  onChange={(e) => setMemberRunGroup(e.target.value)}
                  placeholder="Run group (optional)"
                  className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--text-muted)] focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleAddMember}
                  disabled={!memberUserId.trim() || addMemberMutation.isPending}
                  className={cn(
                    'self-end rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                    'bg-[var(--color-throttle)] text-black hover:bg-[var(--color-throttle)]/80',
                    (!memberUserId.trim() || addMemberMutation.isPending) && 'opacity-50',
                  )}
                >
                  {addMemberMutation.isPending ? 'Adding...' : 'Add Member'}
                </button>
              </div>
            </div>
          )}

          {/* Members list */}
          {members.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <Users className="h-8 w-8 text-[var(--text-muted)]" />
              <p className="text-sm text-[var(--text-secondary)]">No members yet.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {members.map((member) => {
                const RoleIcon = ROLE_ICONS[member.role] ?? GraduationCap;
                return (
                  <div
                    key={member.user_id}
                    className="flex items-center gap-3 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-3 transition-colors hover:bg-[var(--bg-elevated)]"
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-sm font-semibold text-[var(--text-secondary)]">
                      {member.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-[var(--text-primary)]">
                          {member.name}
                        </span>
                        <RoleIcon className={cn('h-3.5 w-3.5', ROLE_COLORS[member.role])} />
                        <span className="text-xs capitalize text-[var(--text-muted)]">
                          {member.role}
                        </span>
                      </div>
                      <p className="text-xs text-[var(--text-muted)]">{member.email}</p>
                    </div>
                    {member.run_group && (
                      <span className="rounded-full bg-[var(--bg-elevated)] px-2.5 py-0.5 text-xs text-[var(--text-secondary)]">
                        {member.run_group}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemoveMember(member.user_id)}
                      disabled={removeMemberMutation.isPending}
                      className="rounded-lg p-1.5 text-[var(--text-muted)] transition-colors hover:bg-[var(--color-brake)]/10 hover:text-[var(--color-brake)]"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Events tab */}
      {activeTab === 'events' && (
        <div className="flex flex-col gap-4">
          {/* Add event button */}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setShowAddEvent(!showAddEvent)}
              className={cn(
                'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                showAddEvent
                  ? 'border-[var(--color-brake)]/30 text-[var(--color-brake)]'
                  : 'border-[var(--cata-border)] bg-[var(--bg-surface)] text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]',
              )}
            >
              {showAddEvent ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
              {showAddEvent ? 'Cancel' : 'Add Event'}
            </button>
          </div>

          {/* Add event form */}
          {showAddEvent && (
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
              <h3 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
                Create Event
              </h3>
              <div className="flex flex-col gap-3">
                <input
                  type="text"
                  value={eventName}
                  onChange={(e) => setEventName(e.target.value)}
                  placeholder="Event name (e.g. Track Day #1)"
                  className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--text-muted)] focus:outline-none"
                />
                <input
                  type="text"
                  value={eventTrack}
                  onChange={(e) => setEventTrack(e.target.value)}
                  placeholder="Track name (e.g. Barber Motorsports Park)"
                  className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--text-muted)] focus:outline-none"
                />
                <input
                  type="datetime-local"
                  value={eventDate}
                  onChange={(e) => setEventDate(e.target.value)}
                  className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--text-muted)] focus:outline-none"
                />
                <RunGroupManager groups={eventRunGroups} onChange={setEventRunGroups} />
                <button
                  type="button"
                  onClick={handleCreateEvent}
                  disabled={
                    !eventName.trim() ||
                    !eventTrack.trim() ||
                    !eventDate ||
                    createEventMutation.isPending
                  }
                  className={cn(
                    'self-end rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                    'bg-[var(--color-throttle)] text-black hover:bg-[var(--color-throttle)]/80',
                    (!eventName.trim() ||
                      !eventTrack.trim() ||
                      !eventDate ||
                      createEventMutation.isPending) &&
                      'opacity-50',
                  )}
                >
                  {createEventMutation.isPending ? 'Creating...' : 'Create Event'}
                </button>
              </div>
            </div>
          )}

          {/* Events list */}
          {events.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <Calendar className="h-8 w-8 text-[var(--text-muted)]" />
              <p className="text-sm text-[var(--text-secondary)]">
                No events scheduled. Create one above.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {events.map((ev) => (
                <div
                  key={ev.id}
                  className="flex items-center gap-3 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-3"
                >
                  <Calendar className="h-5 w-5 text-[var(--text-muted)]" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[var(--text-primary)]">
                        {ev.name}
                      </span>
                      <ChevronRight className="h-3 w-3 text-[var(--text-muted)]" />
                      <span className="text-sm text-[var(--text-secondary)]">{ev.track_name}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                      <span>
                        {new Date(ev.event_date).toLocaleDateString(undefined, {
                          weekday: 'short',
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                      {ev.run_groups && ev.run_groups.length > 0 && (
                        <span>{ev.run_groups.join(', ')}</span>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteEvent(ev.id)}
                    disabled={deleteEventMutation.isPending}
                    className="rounded-lg p-1.5 text-[var(--text-muted)] transition-colors hover:bg-[var(--color-brake)]/10 hover:text-[var(--color-brake)]"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
