"use client";

import Sidebar from "@/components/layout/Sidebar";
import TabBar from "@/components/layout/TabBar";
import OverviewTab from "@/components/tabs/OverviewTab";
import { useUiStore } from "@/store";

function TabContent() {
  const { activeTab } = useUiStore();

  switch (activeTab) {
    case "overview":
      return <OverviewTab />;
    case "speed-trace":
      return (
        <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
          Speed Trace tab coming soon
        </div>
      );
    case "corners":
      return (
        <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
          Corners tab coming soon
        </div>
      );
    case "coaching":
      return (
        <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
          AI Coach tab coming soon
        </div>
      );
    case "trends":
      return (
        <div className="flex items-center justify-center py-20 text-[var(--text-muted)]">
          Trends tab coming soon
        </div>
      );
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
          <TabContent />
        </div>
      </main>
    </div>
  );
}
