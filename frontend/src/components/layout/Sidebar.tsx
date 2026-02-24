"use client";

import { useSessionStore, useUiStore } from "@/store";
import {
  useSessions,
  useDeleteSession,
  useDeleteAllSessions,
  useSessionLaps,
} from "@/hooks/useSession";
import { useTracks, useLoadTrackFolder } from "@/hooks/useTracks";
import FileUpload from "@/components/ui/FileUpload";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import { formatLapTime } from "@/lib/formatters";
import { MPS_TO_MPH } from "@/lib/constants";

export default function Sidebar() {
  const { sidebarOpen, toggleSidebar, skillLevel, setSkillLevel } =
    useUiStore();
  const { activeSessionId, setActiveSession } = useSessionStore();
  const { data: sessionsData, isLoading: sessionsLoading } = useSessions();
  const { data: tracks } = useTracks();
  const loadTrack = useLoadTrackFolder();
  const deleteMutation = useDeleteSession();
  const deleteAllMutation = useDeleteAllSessions();
  const { data: laps } = useSessionLaps(activeSessionId);

  const sessions = sessionsData?.items ?? [];

  const activeSession = sessions.find(
    (s) => s.session_id === activeSessionId,
  );

  // Auto-select first session if none selected
  if (!activeSessionId && sessions.length > 0) {
    setActiveSession(sessions[0].session_id);
  }

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={toggleSidebar}
        className="fixed left-4 top-4 z-50 rounded-md bg-[var(--bg-card)] p-2 text-[var(--text-primary)] lg:hidden"
        aria-label="Toggle sidebar"
      >
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed left-0 top-0 z-40 flex h-full w-[280px] flex-col
          border-r border-[var(--border-color)] bg-[var(--bg-secondary)]
          transition-transform duration-200
          lg:static lg:translate-x-0
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        {/* Header */}
        <div className="flex items-center gap-2 border-b border-[var(--border-color)] px-4 py-3">
          <h1 className="text-lg font-bold text-[var(--text-primary)]">
            Cataclysm
          </h1>
          <span className="rounded bg-[var(--accent-blue)]/20 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent-blue)]">
            v2
          </span>
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
          {/* Track Folder */}
          {tracks && tracks.length > 0 && (
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                Track Folder
              </label>
              <div className="flex gap-1">
                <select
                  className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-2 py-1.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
                  onChange={(e) => {
                    if (e.target.value) loadTrack.mutate(e.target.value);
                  }}
                  defaultValue=""
                >
                  <option value="" disabled>
                    Select track...
                  </option>
                  {tracks.map((t) => (
                    <option key={t.path} value={t.path}>
                      {t.name} ({t.csv_count} files)
                    </option>
                  ))}
                </select>
              </div>
              {loadTrack.isPending && (
                <div className="mt-1 flex items-center gap-1">
                  <Spinner size="sm" />
                  <span className="text-xs text-[var(--text-muted)]">
                    Loading...
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Upload */}
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              Upload Sessions
            </label>
            <FileUpload />
          </div>

          {/* Session List */}
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="text-xs font-medium text-[var(--text-secondary)]">
                Sessions ({sessions.length})
              </label>
              {sessions.length > 0 && (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => {
                    deleteAllMutation.mutate();
                    setActiveSession(null);
                  }}
                  disabled={deleteAllMutation.isPending}
                >
                  Remove All
                </Button>
              )}
            </div>

            {sessionsLoading ? (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            ) : sessions.length === 0 ? (
              <p className="py-4 text-center text-xs text-[var(--text-muted)]">
                No sessions loaded
              </p>
            ) : (
              <div className="flex max-h-48 flex-col gap-1 overflow-y-auto">
                {sessions.map((s) => (
                  <div
                    key={s.session_id}
                    className={`flex items-center justify-between rounded-md px-2 py-1.5 text-xs transition-colors cursor-pointer ${
                      s.session_id === activeSessionId
                        ? "bg-[var(--accent-blue)]/20 text-[var(--accent-blue)]"
                        : "text-[var(--text-primary)] hover:bg-[var(--bg-card)]"
                    }`}
                    onClick={() => setActiveSession(s.session_id)}
                  >
                    <span className="truncate">
                      {s.track_name} - {s.session_date}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteMutation.mutate(s.session_id);
                        if (activeSessionId === s.session_id) {
                          setActiveSession(null);
                        }
                      }}
                      className="ml-1 shrink-0 rounded p-0.5 text-[var(--text-muted)] hover:bg-[var(--accent-red)]/20 hover:text-[var(--accent-red)]"
                      aria-label={`Remove session ${s.track_name}`}
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Active Session Metadata */}
          {activeSession && (
            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
              <h3 className="mb-2 text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                Session Info
              </h3>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Track</span>
                  <span className="text-[var(--text-primary)]">
                    {activeSession.track_name}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Date</span>
                  <span className="text-[var(--text-primary)]">
                    {activeSession.session_date}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Laps</span>
                  <span className="text-[var(--text-primary)]">
                    {activeSession.n_clean_laps} clean / {activeSession.n_laps} total
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Best</span>
                  <span className="font-mono text-[var(--accent-green)]">
                    {formatLapTime(activeSession.best_lap_time_s)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Average</span>
                  <span className="font-mono text-[var(--text-primary)]">
                    {formatLapTime(activeSession.avg_lap_time_s)}
                  </span>
                </div>
                {laps && laps.length > 0 && (
                  <div className="flex justify-between">
                    <span className="text-[var(--text-muted)]">Top Speed</span>
                    <span className="font-mono text-[var(--text-primary)]">
                      {(
                        Math.max(...laps.map((l) => l.max_speed_mps)) *
                        MPS_TO_MPH
                      ).toFixed(1)}{" "}
                      mph
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Skill Level */}
          <Select
            label="Skill Level"
            value={skillLevel}
            onChange={(e) => setSkillLevel(e.target.value)}
            options={[
              { value: "novice", label: "Novice" },
              { value: "intermediate", label: "Intermediate" },
              { value: "advanced", label: "Advanced" },
              { value: "expert", label: "Expert" },
            ]}
          />
        </div>
      </aside>
    </>
  );
}
