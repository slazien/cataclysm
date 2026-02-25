'use client';

import { useCoachStore } from '@/stores';
import { TopBar } from '@/components/navigation/TopBar';
import { SessionDrawer } from '@/components/navigation/SessionDrawer';
import { ViewRouter } from '@/components/navigation/ViewRouter';
import { MobileBottomTabs } from '@/components/navigation/MobileBottomTabs';
import { CoachPanel } from '@/components/coach/CoachPanel';

export default function Home() {
  const panelOpen = useCoachStore((s) => s.panelOpen);

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
    </div>
  );
}
