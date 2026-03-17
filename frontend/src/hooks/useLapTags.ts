"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { setLapTags } from "@/lib/api";
import type { LapSummary } from "@/lib/types";

export const EXCLUDE_TAGS = new Set(["traffic", "off-line", "experimental", "cold-tires"]);

export function isUserExcluded(lap: LapSummary): boolean {
  return lap.tags.some((t) => EXCLUDE_TAGS.has(t));
}

export function useToggleLapTag(sessionId: string | null) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async ({
      lapNumber,
      tag,
      enable,
    }: {
      lapNumber: number;
      tag: string;
      enable: boolean;
    }) => {
      if (!sessionId) throw new Error("No session");
      const laps = qc.getQueryData<LapSummary[]>(["session-laps", sessionId]);
      const lap = laps?.find((l) => l.lap_number === lapNumber);
      const currentTags = lap?.tags ?? [];

      const newTags = enable
        ? [...new Set([...currentTags, tag])]
        : currentTags.filter((t) => t !== tag);

      return setLapTags(sessionId, lapNumber, newTags);
    },
    onSuccess: () => {
      // Invalidate everything downstream
      qc.invalidateQueries({ queryKey: ["session-laps", sessionId] });
      qc.invalidateQueries({ queryKey: ["coaching", sessionId] });
      qc.invalidateQueries({ queryKey: ["optimal-comparison", sessionId] });
      qc.invalidateQueries({ queryKey: ["ideal-lap", sessionId] });
      qc.invalidateQueries({ queryKey: ["sectors", sessionId] });
    },
  });
}
