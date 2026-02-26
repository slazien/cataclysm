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
  const setUploadState = useSessionStore.getState().setUploadState;
  const addToast = useUiStore.getState().addToast;
  return useMutation({
    mutationFn: (files: File[]) => {
      setUploadState('uploading');
      return uploadSessions(files);
    },
    onSuccess: async (data) => {
      setUploadState('processing');
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      // Brief delay to show processing, then done, then auto-dismiss
      setTimeout(() => {
        setUploadState('done');
        setTimeout(() => setUploadState('idle'), 1500);
      }, 800);

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
      setUploadState('error');
      setTimeout(() => setUploadState('idle'), 3000);
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
