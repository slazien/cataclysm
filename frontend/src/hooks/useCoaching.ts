"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCoachingReport, generateCoachingReport } from "@/lib/api";
import { useUiStore } from "@/stores";
import type { CoachingReport } from "@/lib/types";

export function useCoachingReport(sessionId: string | null) {
  const skillLevel = useUiStore((s) => s.skillLevel);
  return useQuery<CoachingReport>({
    queryKey: ["coaching-report", sessionId, skillLevel],
    queryFn: () => getCoachingReport(sessionId!, skillLevel),
    enabled: !!sessionId,
    retry: 1,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60 * 1000, // 5 min — avoid repeated 404s when no report exists
    // Poll every 2s while the report is still generating
    refetchInterval: (query) => {
      const { data, status } = query.state;
      if (data?.status === "generating") return 2000;
      // Keep polling on errors — transient failures shouldn't kill the loop
      if (status === "error") return 3000;
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

