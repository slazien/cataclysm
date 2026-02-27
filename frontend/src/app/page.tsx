'use client';

import { useEffect } from 'react';
import { useCoachStore, useSessionStore, useUiStore } from '@/stores';
import { useSessions } from '@/hooks/useSession';
import { cn } from '@/lib/utils';
import { TopBar } from '@/components/navigation/TopBar';
import { SessionDrawer } from '@/components/navigation/SessionDrawer';
import { ViewRouter } from '@/components/navigation/ViewRouter';
import { MobileBottomTabs } from '@/components/navigation/MobileBottomTabs';
import { CoachPanel } from '@/components/coach/CoachPanel';
import { ProcessingOverlay } from '@/components/shared/ProcessingOverlay';
import { SettingsPanel } from '@/components/shared/SettingsPanel';
import { ToastContainer } from '@/components/shared/ToastContainer';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';

export default function Home() {
  const panelOpen = useCoachStore((s) => s.panelOpen);
  const settingsPanelOpen = useUiStore((s) => s.settingsPanelOpen);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const { data: sessionsData } = useSessions();
  useKeyboardShortcuts();

  // Auto-select the most recent session when sessions load and none is active.
  // This ensures sessions restored from DB after a redeploy appear immediately.
  useEffect(() => {
    if (!activeSessionId && sessionsData?.items?.length) {
      setActiveSession(sessionsData.items[0].session_id);
    }
  }, [activeSessionId, sessionsData, setActiveSession]);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <SessionDrawer />
        <main className={cn("flex-1 overflow-y-auto", settingsPanelOpen && "pointer-events-none")}>
          <ViewRouter />
        </main>
        {panelOpen && <CoachPanel />}
      </div>
      <MobileBottomTabs />
      <ProcessingOverlay />
      <SettingsPanel />
      <ToastContainer />
    </div>
  );
}
