'use client';

import { useRef, useState } from 'react';
import { useSession as useAuthSession, signOut } from 'next-auth/react';
import { Bot, Plus, Settings, ChevronRight, LogOut, Sparkles } from 'lucide-react';
import { useUiStore, useSessionStore, useCoachStore } from '@/stores';
import { useSession, useUploadSessions } from '@/hooks/useSession';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LapPillBar } from '@/components/navigation/LapPillBar';
import { SeasonWrapped } from '@/components/wrapped/SeasonWrapped';

type ActiveView = 'dashboard' | 'deep-dive' | 'progress' | 'debrief';

const VIEW_TABS: { value: ActiveView; label: string }[] = [
  { value: 'dashboard', label: 'Dashboard' },
  { value: 'deep-dive', label: 'Deep Dive' },
  { value: 'progress', label: 'Progress' },
  { value: 'debrief', label: 'Debrief' },
];

export function TopBar() {
  const activeView = useUiStore((s) => s.activeView);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const toggleSessionDrawer = useUiStore((s) => s.toggleSessionDrawer);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const panelOpen = useCoachStore((s) => s.panelOpen);
  const togglePanel = useCoachStore((s) => s.togglePanel);
  const toggleSettingsPanel = useUiStore((s) => s.toggleSettingsPanel);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [wrappedOpen, setWrappedOpen] = useState(false);

  const { data: authSession } = useAuthSession();
  const { data: session } = useSession(activeSessionId);
  const uploadMutation = useUploadSessions();
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    uploadMutation.mutate(Array.from(files), {
      onSuccess: (data) => {
        if (data.session_ids.length > 0 && !activeSessionId) {
          setActiveSession(data.session_ids[0]);
        }
      },
    });
    // Reset input so the same file can be re-selected
    e.target.value = '';
  }

  return (
    <div className="shrink-0">
      {/* Row 1: Main navigation */}
      <div className="flex h-12 items-center bg-[var(--bg-surface)] px-4">
        {/* Left: Logo */}
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-[var(--text-primary)]">Cataclysm</span>
          <Badge variant="secondary" className="text-[10px]">v2</Badge>
        </div>

        {/* Center: View tabs */}
        <div className="ml-auto mr-auto hidden items-center gap-1 lg:flex">
          {VIEW_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveView(tab.value)}
              className={cn(
                'relative px-3 py-1.5 text-sm font-medium transition-colors',
                activeView === tab.value
                  ? 'text-[var(--text-primary)]'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
              )}
            >
              {tab.label}
              {activeView === tab.value && (
                <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-[var(--cata-accent)]" />
              )}
            </button>
          ))}
        </div>

        {/* Right: Action buttons */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={handleUploadClick}
            title="Upload CSV"
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <Plus className="h-4 w-4" />
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".csv"
            className="hidden"
            onChange={handleFileChange}
          />
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={togglePanel}
            title="Toggle AI Coach"
            className={cn(
              'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
              panelOpen && 'bg-[var(--cata-accent)]/15 text-[var(--cata-accent)]',
            )}
          >
            <Bot className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setWrappedOpen(true)}
            title="Year in Review"
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <Sparkles className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={toggleSettingsPanel}
            title="Settings"
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <Settings className="h-4 w-4" />
          </Button>
          {/* User avatar + sign-out */}
          {authSession?.user && (
            <div className="relative ml-1">
              <button
                type="button"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex h-7 w-7 items-center justify-center overflow-hidden rounded-full ring-2 ring-transparent transition-all hover:ring-[var(--cata-accent)]"
              >
                {authSession.user.image ? (
                  <img
                    src={authSession.user.image}
                    alt={authSession.user.name ?? 'User'}
                    className="h-full w-full rounded-full object-cover"
                  />
                ) : (
                  <span className="flex h-full w-full items-center justify-center rounded-full bg-[var(--cata-accent)] text-xs font-bold text-white">
                    {(authSession.user.name ?? 'U')[0].toUpperCase()}
                  </span>
                )}
              </button>
              {userMenuOpen && (
                <div className="absolute right-0 top-9 z-50 w-48 rounded-md border border-[var(--cata-border)] bg-[var(--bg-surface)] py-1 shadow-lg">
                  <div className="border-b border-[var(--cata-border)] px-3 py-2">
                    <p className="text-sm font-medium text-[var(--text-primary)]">{authSession.user.name}</p>
                    <p className="text-xs text-[var(--text-muted)]">{authSession.user.email}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => signOut()}
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Row 2: Contextual bar — only when session active */}
      {activeSessionId && (
        <div className="flex h-10 items-center border-b border-[var(--cata-border)] bg-[var(--bg-base)] px-4">
          {/* Left: Session selector */}
          <button
            type="button"
            onClick={toggleSessionDrawer}
            className="flex items-center gap-1 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            <span className="font-medium">{session?.track_name ?? 'Loading...'}</span>
            <ChevronRight className="h-3 w-3 text-[var(--text-muted)]" />
            <span className="text-[var(--text-muted)]">{session?.session_date ?? ''}</span>
          </button>

          {/* Right: Lap pills (deep-dive only) */}
          {activeView === 'deep-dive' && (
            <div className="ml-auto">
              <LapPillBar />
            </div>
          )}
        </div>
      )}
      <SeasonWrapped open={wrappedOpen} onClose={() => setWrappedOpen(false)} />
    </div>
  );
}
