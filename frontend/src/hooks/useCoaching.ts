"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCoachingReport, generateCoachingReport, getIdealLap } from "@/lib/api";
import type { CoachingReport, IdealLapData } from "@/lib/types";

export function useCoachingReport(sessionId: string | null) {
  return useQuery<CoachingReport>({
    queryKey: ["coaching-report", sessionId],
    queryFn: () => getCoachingReport(sessionId!),
    enabled: !!sessionId,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60 * 1000, // 5 min — avoid repeated 404s when no report exists
    // Poll every 2s while the report is still generating
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && data.status === "generating") return 2000;
      return false;
    },
  });
}

export function useGenerateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sessionId,
      skillLevel,
    }: {
      sessionId: string;
      skillLevel: string;
    }) => generateCoachingReport(sessionId, skillLevel),
    onSuccess: (_data, variables) => {
      // Invalidate the query so it refetches from GET (which now returns
      // status="generating" instead of 404). This also clears the error state.
      void queryClient.invalidateQueries({
        queryKey: ["coaching-report", variables.sessionId],
      });
    },
  });
}

export function useIdealLap(sessionId: string | null) {
  return useQuery<IdealLapData>({
    queryKey: ["ideal-lap", sessionId],
    queryFn: () => getIdealLap(sessionId!),
    enabled: !!sessionId,
    retry: false,
  });
}
