'use client';

import { useSessionStore, useUiStore } from '@/stores';
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
      return <SessionDashboard />;
    case 'deep-dive':
      return <DeepDive />;
    case 'progress':
      return <ProgressView />;
    default:
      return <SessionDashboard />;
  }
}
