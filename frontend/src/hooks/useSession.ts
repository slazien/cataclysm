"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession as useAuthSession } from "next-auth/react";
import {
  listSessions,
  getSession,
  getSessionLaps,
  getLapData,
  uploadSessions,
  deleteSession,
  deleteAllSessions,
  getMilestones,
} from "@/lib/api";
import { useSessionStore } from "@/stores";
import { useUiStore } from "@/stores/uiStore";
import { fetchApi } from "@/lib/api";
import type { SessionSummary } from "@/lib/types";

// Telemetry & session data is immutable once uploaded — never refetch.
const IMMUTABLE = { staleTime: Infinity } as const;

export function useSessions() {
  const { status } = useAuthSession();
  return useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
    // Only fetch when auth session is established — prevents 401 race
    enabled: status === "authenticated",
  });
}

export function useSession(sessionId: string | null) {
  return useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId!),
    enabled: !!sessionId,
    staleTime: Infinity,
    // Poll every 30s while weather is missing — backend lazy-retries the
    // Open-Meteo fetch with a 5-min cooldown, stops once weather arrives.
    refetchInterval: (query) =>
      query.state.data?.weather_condition ? false : 30_000,
  });
}

export function useSessionLaps(sessionId: string | null) {
  return useQuery({
    queryKey: ["session-laps", sessionId],
    queryFn: () => getSessionLaps(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}

export function useLapData(sessionId: string | null, lapNumber: number | null) {
  return useQuery({
    queryKey: ["lap-data", sessionId, lapNumber],
    queryFn: () => getLapData(sessionId!, lapNumber!),
    enabled: !!sessionId && lapNumber !== null,
    ...IMMUTABLE,
  });
}

export function useUploadSessions() {
  const queryClient = useQueryClient();
  const store = useSessionStore.getState;
  const addToast = useUiStore.getState().addToast;
  return useMutation({
    mutationFn: (files: File[]) => {
      store().setUploadState('uploading');
      store().setUploadProgress(0);
      store().setUploadErrorMessage(null);
      return uploadSessions(files, (fraction) => {
        // Upload bytes account for 0-60% of the progress bar.
        // XHR fires progress during upload; server processing happens after
        // upload completes, so once fraction=1 the server is working.
        const pct = Math.round(fraction * 60);
        store().setUploadProgress(pct);
        if (fraction >= 1) {
          store().setUploadState('processing');
        }
      });
    },
    onSuccess: async (data) => {
      // No sessions produced — file was parseable but had no valid laps
      if (data.session_ids.length === 0) {
        store().setUploadState('error');
        store().setUploadProgress(0);
        store().setUploadErrorMessage(
          'No laps detected — was the session shorter than 1 lap? Make sure RaceChrono was recording.',
        );
        return;
      }

      store().setUploadProgress(100);
      store().setUploadState('done');
      // Session activation is handled by each call-site's onSuccess callback
      // (WelcomeScreen delays for skill picker, TopBar/SessionDrawer activate immediately).
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      // Brief pause to show 100% check, then auto-dismiss
      setTimeout(() => {
        store().setUploadState('idle');
        store().setUploadProgress(0);
      }, 1500);

      // Show achievement toasts if any were unlocked
      if (data.newly_unlocked && data.newly_unlocked.length > 0) {
        // Invalidate achievement queries so BadgeGrid picks up new unlocks
        queryClient.invalidateQueries({ queryKey: ['achievements'] });
        // Fetch full achievement details for toast messages
        try {
          const achResp = await fetchApi<{ newly_unlocked: Array<{ name: string }> }>(
            '/api/achievements/recent',
          );
          for (const ach of achResp.newly_unlocked) {
            addToast({ type: 'achievement', message: ach.name, duration: 8000 });
          }
        } catch {
          // Fallback: show generic achievement toast
          const count = data.newly_unlocked.length;
          addToast({
            type: 'achievement',
            message: `${count} achievement${count > 1 ? 's' : ''} unlocked!`,
            duration: 8000,
          });
        }
      }

      // Check for PB milestones after upload
      try {
        if (data.session_ids.length > 0) {
          // Fetch the first uploaded session to get track name
          const session = await fetchApi<SessionSummary>(
            `/api/sessions/${data.session_ids[0]}`,
          );
          if (session.track_name) {
            const milestoneResp = await getMilestones(session.track_name);
            const uploadedIds = new Set(data.session_ids);
            const hasPb = milestoneResp.milestones.some(
              (m) => m.category === 'pb' && uploadedIds.has(m.session_id),
            );
            if (hasPb) {
              addToast({ type: 'pb', message: 'New Personal Best!' });
            } else {
              addToast({ type: 'info', message: 'Session uploaded successfully' });
            }
          } else {
            addToast({ type: 'info', message: 'Session uploaded successfully' });
          }
        }
      } catch {
        // Milestone check is non-critical; still show success toast
        addToast({ type: 'info', message: 'Session uploaded successfully' });
      }
    },
    onError: (error: Error) => {
      store().setUploadState('error');
      store().setUploadProgress(0);
      store().setUploadErrorMessage(
        error.message || 'Upload failed. Please check your CSV format and try again.',
      );
      // No auto-dismiss — user clicks "Try Again" in ProcessingOverlay
    },
  });
}

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSession(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

export function useDeleteAllSessions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => deleteAllSessions(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
}
