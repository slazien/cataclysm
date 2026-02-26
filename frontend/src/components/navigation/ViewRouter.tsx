'use client';

import { useEffect, useRef } from 'react';
import { useSessionStore, useUiStore, useAnalysisStore } from '@/stores';
import { ViewErrorBoundary } from '@/components/shared/ViewErrorBoundary';
import { WelcomeScreen } from '@/components/shared/WelcomeScreen';
import { SessionDashboard } from '@/components/dashboard/SessionDashboard';
import { DeepDive } from '@/components/deep-dive/DeepDive';
import { ProgressView } from '@/components/progress/ProgressView';

export function ViewRouter() {
  const activeView = useUiStore((s) => s.activeView);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const resetAnalysis = useAnalysisStore((s) => s.reset);
  const prevSessionId = useRef(activeSessionId);

  // Reset analysis state when switching sessions to prevent stale data crashes
  useEffect(() => {
    if (prevSessionId.current !== null && activeSessionId !== prevSessionId.current) {
      resetAnalysis();
    }
    prevSessionId.current = activeSessionId;
  }, [activeSessionId, resetAnalysis]);

  if (!activeSessionId) {
    return <WelcomeScreen />;
  }

  // key={activeSessionId} forces remount of ErrorBoundary + children on session switch,
  // clearing any caught error state and giving components fresh renders
  switch (activeView) {
    case 'dashboard':
      return (
        <ViewErrorBoundary key={activeSessionId}>
          <SessionDashboard />
        </ViewErrorBoundary>
      );
    case 'deep-dive':
      return (
        <ViewErrorBoundary key={activeSessionId}>
          <DeepDive />
        </ViewErrorBoundary>
      );
    case 'progress':
      return (
        <ViewErrorBoundary key={activeSessionId}>
          <ProgressView />
        </ViewErrorBoundary>
      );
    default:
      return (
        <ViewErrorBoundary key={activeSessionId}>
          <SessionDashboard />
        </ViewErrorBoundary>
      );
  }
}
