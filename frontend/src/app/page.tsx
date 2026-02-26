'use client';

import { useCoachStore } from '@/stores';
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
  useKeyboardShortcuts();

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <SessionDrawer />
        <main className="flex-1 overflow-y-auto">
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
