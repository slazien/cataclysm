'use client';

import { useRef } from 'react';
import { Bot, Plus, Settings, ChevronRight } from 'lucide-react';
import { useUiStore, useSessionStore, useCoachStore } from '@/stores';
import { useSession, useUploadSessions } from '@/hooks/useSession';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LapPillBar } from '@/components/navigation/LapPillBar';

type ActiveView = 'dashboard' | 'deep-dive' | 'progress';

const VIEW_TABS: { value: ActiveView; label: string }[] = [
  { value: 'dashboard', label: 'Dashboard' },
  { value: 'deep-dive', label: 'Deep Dive' },
  { value: 'progress', label: 'Progress' },
];

export function TopBar() {
  const activeView = useUiStore((s) => s.activeView);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const toggleSessionDrawer = useUiStore((s) => s.toggleSessionDrawer);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const panelOpen = useCoachStore((s) => s.panelOpen);
  const togglePanel = useCoachStore((s) => s.togglePanel);

  const { data: session } = useSession(activeSessionId);
  const uploadMutation = useUploadSessions();
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    uploadMutation.mutate(Array.from(files));
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
            title="Settings"
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <Settings className="h-4 w-4" />
          </Button>
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
    </div>
  );
}
