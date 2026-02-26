"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "@/lib/api";
import type {
  EquipmentProfile,
  EquipmentProfileCreate,
  SessionEquipmentResponse,
  SessionEquipmentSet,
  TireSpec,
} from "@/lib/types";

// --- Equipment Profiles ---

export function useEquipmentProfiles() {
  return useQuery({
    queryKey: ["equipment-profiles"],
    queryFn: () =>
      fetchApi<{ items: EquipmentProfile[]; total: number }>(
        "/api/equipment/profiles",
      ),
  });
}

export function useCreateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: EquipmentProfileCreate) =>
      fetchApi<EquipmentProfile>("/api/equipment/profiles", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipment-profiles"] });
    },
  });
}

export function useDeleteProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profileId: string) =>
      fetchApi<{ message: string }>(`/api/equipment/profiles/${profileId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipment-profiles"] });
    },
  });
}

// --- Session Equipment Assignment ---

export function useSessionEquipment(sessionId: string | null) {
  return useQuery({
    queryKey: ["session-equipment", sessionId],
    queryFn: async (): Promise<SessionEquipmentResponse | null> => {
      try {
        return await fetchApi<SessionEquipmentResponse>(
          `/api/equipment/${sessionId}/equipment`,
        );
      } catch {
        // 404 is expected when no equipment is assigned to the session
        return null;
      }
    },
    enabled: !!sessionId,
    retry: false,
  });
}

export function useAssignEquipment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sessionId,
      body,
    }: {
      sessionId: string;
      body: SessionEquipmentSet;
    }) =>
      fetchApi<SessionEquipmentResponse>(
        `/api/equipment/${sessionId}/equipment`,
        {
          method: "PUT",
          body: JSON.stringify(body),
        },
      ),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["session-equipment", variables.sessionId],
      });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

// --- Tire Search ---

export function useTireSearch(query: string) {
  return useQuery({
    queryKey: ["tire-search", query],
    queryFn: () =>
      fetchApi<TireSpec[]>(
        `/api/equipment/tires/search?q=${encodeURIComponent(query)}`,
      ),
    enabled: query.length >= 2,
    staleTime: 60_000,
  });
}
