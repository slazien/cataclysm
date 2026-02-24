"use client";

import { useUiStore } from "@/store";
import { useSessions } from "@/hooks/useSession";
import { useSessionStore } from "@/store";

type Tab = "overview" | "speed-trace" | "corners" | "coaching" | "trends";

interface TabDef {
  id: Tab;
  label: string;
  showAlways?: boolean;
}

const TABS: TabDef[] = [
  { id: "overview", label: "Overview", showAlways: true },
  { id: "speed-trace", label: "Speed Trace", showAlways: true },
  { id: "corners", label: "Corners", showAlways: true },
  { id: "coaching", label: "AI Coach", showAlways: true },
  { id: "trends", label: "Trends" },
];

export default function TabBar() {
  const { activeTab, setActiveTab } = useUiStore();
  const { data: sessionsData } = useSessions();
  const { activeSessionId } = useSessionStore();

  const sessions = sessionsData?.items ?? [];
  const activeSession = sessions.find(
    (s) => s.session_id === activeSessionId,
  );

  // Show trends tab only if 2+ sessions from the same track
  const sameTrackCount = activeSession
    ? sessions.filter((s) => s.track_name === activeSession.track_name).length
    : 0;
  const showTrends = sameTrackCount >= 2;

  const visibleTabs = TABS.filter((t) => t.showAlways || (t.id === "trends" && showTrends));

  return (
    <div className="flex gap-0 border-b border-[var(--border-color)] overflow-x-auto">
      {visibleTabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveTab(tab.id)}
          className={`
            whitespace-nowrap px-4 py-2.5 text-sm font-medium
            transition-colors duration-150 cursor-pointer
            border-b-2
            ${
              activeTab === tab.id
                ? "border-[var(--accent-blue)] text-[var(--accent-blue)]"
                : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-color)]"
            }
          `}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
