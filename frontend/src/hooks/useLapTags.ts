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
  const queryKey = ["session-laps", sessionId];

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
      const laps = qc.getQueryData<LapSummary[]>(queryKey);
      const lap = laps?.find((l) => l.lap_number === lapNumber);
      const currentTags = lap?.tags ?? [];

      const newTags = enable
        ? [...new Set([...currentTags, tag])]
        : currentTags.filter((t) => t !== tag);

      return setLapTags(sessionId, lapNumber, newTags);
    },
    onMutate: async ({ lapNumber, tag, enable }) => {
      // Cancel any in-flight refetch so it doesn't overwrite our optimistic update
      await qc.cancelQueries({ queryKey });

      const previous = qc.getQueryData<LapSummary[]>(queryKey);

      // Optimistic update: immediately reflect the tag change in the cache
      qc.setQueryData<LapSummary[]>(queryKey, (old) => {
        if (!old) return old;
        return old.map((lap) => {
          if (lap.lap_number !== lapNumber) return lap;
          const newTags = enable
            ? [...new Set([...lap.tags, tag])]
            : lap.tags.filter((t) => t !== tag);
          const excluded = newTags.some((t) => EXCLUDE_TAGS.has(t));
          return { ...lap, tags: newTags, is_clean: excluded ? false : lap.is_clean };
        });
      });

      return { previous };
    },
    onError: (_err, _vars, context) => {
      // Rollback on failure
      if (context?.previous) {
        qc.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      // Invalidate downstream queries that depend on which laps are clean
      qc.invalidateQueries({ queryKey: ["coaching", sessionId] });
      qc.invalidateQueries({ queryKey: ["optimal-comparison", sessionId] });
      qc.invalidateQueries({ queryKey: ["ideal-lap", sessionId] });
      qc.invalidateQueries({ queryKey: ["sectors", sessionId] });
    },
  });
}
