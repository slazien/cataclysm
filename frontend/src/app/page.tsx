'use client';

import { useEffect } from 'react';
import { useSessionStore, useUiStore } from '@/stores';
import { useSessions } from '@/hooks/useSession';
import { cn } from '@/lib/utils';
import { TopBar } from '@/components/navigation/TopBar';
import { SessionDrawer } from '@/components/navigation/SessionDrawer';
import { ViewRouter } from '@/components/navigation/ViewRouter';
import { MobileBottomTabs } from '@/components/navigation/MobileBottomTabs';
import { FloatingChatButton } from '@/components/coach/FloatingChatButton';
import { ChatDrawer } from '@/components/coach/ChatDrawer';
import { ProcessingOverlay } from '@/components/shared/ProcessingOverlay';
import { SettingsPanel } from '@/components/shared/SettingsPanel';
import { ToastContainer } from '@/components/shared/ToastContainer';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { KeyboardShortcutOverlay } from '@/components/shared/KeyboardShortcutOverlay';

export default function Home() {
  const settingsPanelOpen = useUiStore((s) => s.settingsPanelOpen);
  const setActiveView = useUiStore((s) => s.setActiveView);
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

  // Navigate to session-report view when a new session becomes active
  useEffect(() => {
    if (activeSessionId) {
      setActiveView('session-report');
    }
  }, [activeSessionId, setActiveView]);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <SessionDrawer />
        <main className={cn("flex-1 overflow-y-auto", settingsPanelOpen && "pointer-events-none")}>
          <ViewRouter />
        </main>
      </div>
      <MobileBottomTabs />
      <FloatingChatButton />
      <ChatDrawer />
      <ProcessingOverlay />
      <SettingsPanel />
      <ToastContainer />
      <KeyboardShortcutOverlay />
    </div>
  );
}
