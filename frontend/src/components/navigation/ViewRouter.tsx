'use client';

import { useSessionStore, useUiStore } from '@/stores';
import { EmptyState } from '@/components/shared/EmptyState';
import { SessionDashboard } from '@/components/dashboard/SessionDashboard';
import { DeepDive } from '@/components/deep-dive/DeepDive';
import { ProgressView } from '@/components/progress/ProgressView';

export function ViewRouter() {
  const activeView = useUiStore((s) => s.activeView);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);

  if (!activeSessionId) {
    return (
      <EmptyState
        title="No session loaded"
        message="Upload a RaceChrono CSV or select a session from the drawer to get started."
        className="h-full"
      />
    );
  }

  switch (activeView) {
    case 'dashboard':
      return <SessionDashboard />;
    case 'deep-dive':
      return <DeepDive />;
    case 'progress':
      return <ProgressView />;
    default:
      return <SessionDashboard />;
  }
}
