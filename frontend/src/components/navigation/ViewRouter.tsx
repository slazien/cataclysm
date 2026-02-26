'use client';

import { useSessionStore, useUiStore } from '@/stores';
import { ViewErrorBoundary } from '@/components/shared/ViewErrorBoundary';
import { WelcomeScreen } from '@/components/shared/WelcomeScreen';
import { SessionDashboard } from '@/components/dashboard/SessionDashboard';
import { DeepDive } from '@/components/deep-dive/DeepDive';
import { ProgressView } from '@/components/progress/ProgressView';

export function ViewRouter() {
  const activeView = useUiStore((s) => s.activeView);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);

  if (!activeSessionId) {
    return <WelcomeScreen />;
  }

  switch (activeView) {
    case 'dashboard':
      return (
        <ViewErrorBoundary>
          <SessionDashboard />
        </ViewErrorBoundary>
      );
    case 'deep-dive':
      return (
        <ViewErrorBoundary>
          <DeepDive />
        </ViewErrorBoundary>
      );
    case 'progress':
      return (
        <ViewErrorBoundary>
          <ProgressView />
        </ViewErrorBoundary>
      );
    default:
      return (
        <ViewErrorBoundary>
          <SessionDashboard />
        </ViewErrorBoundary>
      );
  }
}
