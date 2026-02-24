"use client";

import Sidebar from "@/components/layout/Sidebar";
import TabBar from "@/components/layout/TabBar";
import OverviewTab from "@/components/tabs/OverviewTab";
import SpeedTraceTab from "@/components/tabs/SpeedTraceTab";
import CornersTab from "@/components/tabs/CornersTab";
import CoachingTab from "@/components/tabs/CoachingTab";
import TrendsTab from "@/components/tabs/TrendsTab";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useUiStore } from "@/store";

function TabContent() {
  const { activeTab } = useUiStore();

  switch (activeTab) {
    case "overview":
      return <OverviewTab />;
    case "speed-trace":
      return <SpeedTraceTab />;
    case "corners":
      return <CornersTab />;
    case "coaching":
      return <CoachingTab />;
    case "trends":
      return <TrendsTab />;
    default:
      return null;
  }
}

export default function Home() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex items-center gap-3 border-b border-[var(--border-color)] bg-[var(--bg-secondary)] px-6 py-3 lg:hidden">
          {/* Spacer for mobile hamburger */}
          <div className="w-8" />
          <h1 className="text-lg font-bold text-[var(--text-primary)]">
            Cataclysm
          </h1>
        </header>

        <TabBar />

        <div className="flex-1 overflow-y-auto p-4 lg:p-6">
          <ErrorBoundary>
            <TabContent />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}
