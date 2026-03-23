"use client";

import { useCallback } from "react";
import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { setLapTags } from "@/lib/api";
import type { LapSummary } from "@/lib/types";

export const EXCLUDE_TAGS = new Set(["traffic", "off-line", "experimental", "cold-tires"]);

export function isUserExcluded(lap: LapSummary): boolean {
  return lap.tags.some((t) => EXCLUDE_TAGS.has(t));
}

// ---------------------------------------------------------------------------
// Debounced downstream invalidation
//
// Tag toggles are instant (optimistic UI), but coaching/physics recomputation
// is expensive (~30-60s). We batch invalidations so that a user tagging
// multiple laps over several minutes only triggers ONE backend recompute —
// either when the debounce timer fires (30s of inactivity) or when the
// tagging UI is explicitly closed (flush).
// ---------------------------------------------------------------------------

const DEBOUNCE_MS = 30_000;

/** Per-session pending flush timers (module-level singleton). */
const pendingFlush = new Map<string, ReturnType<typeof setTimeout>>();

function invalidateDownstream(qc: QueryClient, sessionId: string) {
  qc.invalidateQueries({ queryKey: ["coaching-report", sessionId] });
  qc.invalidateQueries({ queryKey: ["optimal-comparison", sessionId] });
  qc.invalidateQueries({ queryKey: ["ideal-lap", sessionId] });
  qc.invalidateQueries({ queryKey: ["sectors", sessionId] });
}

function scheduleInvalidation(qc: QueryClient, sessionId: string) {
  const existing = pendingFlush.get(sessionId);
  if (existing) clearTimeout(existing);

  const timer = setTimeout(() => {
    pendingFlush.delete(sessionId);
    invalidateDownstream(qc, sessionId);
  }, DEBOUNCE_MS);

  pendingFlush.set(sessionId, timer);
}

/** Immediately flush any pending invalidation for this session. */
function flushInvalidation(qc: QueryClient, sessionId: string) {
  const existing = pendingFlush.get(sessionId);
  if (existing) {
    clearTimeout(existing);
    pendingFlush.delete(sessionId);
    invalidateDownstream(qc, sessionId);
  }
}

/**
 * Call when the tagging UI closes (e.g. LapGridSelector popover dismissed).
 * If any tag changes are pending, this triggers the downstream recompute
 * immediately instead of waiting for the 30s debounce.
 */
export function useFlushTagInvalidation(sessionId: string | null) {
  const qc = useQueryClient();
  return useCallback(() => {
    if (sessionId) flushInvalidation(qc, sessionId);
  }, [qc, sessionId]);
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
      await qc.cancelQueries({ queryKey });

      const previous = qc.getQueryData<LapSummary[]>(queryKey);

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
      if (context?.previous) {
        qc.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      // Schedule (or reset) the debounced downstream invalidation.
      // Actual invalidation fires after 30s of no tag activity,
      // or immediately when the tagging UI closes (via useFlushTagInvalidation).
      if (sessionId) scheduleInvalidation(qc, sessionId);
    },
  });
}
