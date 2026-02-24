import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "@/lib/api";
import type { SessionSummary, LapSummary, LapData } from "@/lib/types";

export function useSessions() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: () => fetchApi<{ items: SessionSummary[]; total: number }>("/api/sessions"),
  });
}

export function useSessionLaps(sessionId: string | null) {
  return useQuery({
    queryKey: ["session-laps", sessionId],
    queryFn: () => fetchApi<LapSummary[]>(`/api/sessions/${sessionId}/laps`),
    enabled: !!sessionId,
  });
}

export function useLapData(sessionId: string | null, lapNumber: number | null) {
  return useQuery({
    queryKey: ["lap-data", sessionId, lapNumber],
    queryFn: () =>
      fetchApi<LapData>(`/api/sessions/${sessionId}/laps/${lapNumber}/data`),
    enabled: !!sessionId && lapNumber !== null,
  });
}
