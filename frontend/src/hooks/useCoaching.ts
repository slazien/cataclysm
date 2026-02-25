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
    onSuccess: (data, variables) => {
      queryClient.setQueryData(
        ["coaching-report", variables.sessionId],
        data,
      );
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
