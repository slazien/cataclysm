'use client';

import { useEffect, useRef } from 'react';
import { useSession as useAuthSession } from 'next-auth/react';
import { useSessionStore, useUiStore } from '@/stores';
import { useSessions } from '@/hooks/useSession';
import { claimSession } from '@/lib/api';
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
import { DisclaimerModal } from '@/components/shared/DisclaimerModal';
import { AppFooter } from '@/components/shared/AppFooter';

export default function Home() {
  const settingsPanelOpen = useUiStore((s) => s.settingsPanelOpen);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const { data: sessionsData } = useSessions();
  const { status: authStatus } = useAuthSession();
  const claimAttempted = useRef(false);
  useKeyboardShortcuts();

  // Claim anonymous session after OAuth sign-in
  useEffect(() => {
    if (authStatus !== 'authenticated' || claimAttempted.current) return;
    const anonSessionId = localStorage.getItem('cataclysm_anon_session_id');
    if (!anonSessionId) return;
    claimAttempted.current = true;
    claimSession(anonSessionId)
      .then(() => {
        localStorage.removeItem('cataclysm_anon_session_id');
        setActiveSession(anonSessionId);
      })
      .catch(() => {
        // Session expired or already claimed — clear stale key
        localStorage.removeItem('cataclysm_anon_session_id');
      });
  }, [authStatus, setActiveSession]);

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
        <main className={cn("flex flex-1 flex-col overflow-hidden", settingsPanelOpen && "pointer-events-none")}>
          <ViewRouter />
        </main>
      </div>
      <AppFooter />
      <MobileBottomTabs />
      <FloatingChatButton />
      <ChatDrawer />
      <ProcessingOverlay />
      <SettingsPanel />
      <ToastContainer />
      <KeyboardShortcutOverlay />
      <DisclaimerModal />
    </div>
  );
}
