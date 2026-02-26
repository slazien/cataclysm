"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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

export function useSessions() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
  });
}

export function useSession(sessionId: string | null) {
  return useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId!),
    enabled: !!sessionId,
  });
}

export function useSessionLaps(sessionId: string | null) {
  return useQuery({
    queryKey: ["session-laps", sessionId],
    queryFn: () => getSessionLaps(sessionId!),
    enabled: !!sessionId,
  });
}

export function useLapData(sessionId: string | null, lapNumber: number | null) {
  return useQuery({
    queryKey: ["lap-data", sessionId, lapNumber],
    queryFn: () => getLapData(sessionId!, lapNumber!),
    enabled: !!sessionId && lapNumber !== null,
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
      store().setUploadProgress(100);
      store().setUploadState('done');
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      // Brief pause to show 100% check, then auto-dismiss
      setTimeout(() => {
        store().setUploadState('idle');
        store().setUploadProgress(0);
      }, 1500);

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
    onError: () => {
      store().setUploadState('error');
      store().setUploadProgress(0);
      setTimeout(() => store().setUploadState('idle'), 3000);
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
