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
} from "@/lib/api";
import { useSessionStore } from "@/stores";

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
  return useMutation({
    mutationFn: (files: File[]) => {
      setUploadState('uploading');
      return uploadSessions(files);
    },
    onSuccess: () => {
      setUploadState('processing');
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      // Brief delay to show processing, then done, then auto-dismiss
      setTimeout(() => {
        setUploadState('done');
        setTimeout(() => setUploadState('idle'), 1500);
      }, 800);
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
