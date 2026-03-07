"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi, searchVehicles, getVehicleSpec } from "@/lib/api";
import type {
  BrakePadSearchResult,
  EquipmentProfile,
  EquipmentProfileCreate,
  SessionEquipmentResponse,
  SessionEquipmentSet,
  SessionWeather,
  TireSpec,
  VehicleSearchResult,
  VehicleSpec,
} from "@/lib/types";

/**
 * Query keys whose backend computation depends on vehicle/tire params.
 * Must be invalidated whenever equipment assignment or profile data changes.
 */
const PHYSICS_DEPENDENT_KEYS = [
  "optimal-comparison",
  "ideal-lap",
] as const;

function invalidatePhysicsQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  sessionId?: string,
) {
  for (const key of PHYSICS_DEPENDENT_KEYS) {
    const queryKey = sessionId ? [key, sessionId] : [key];
    // invalidateQueries marks stale and triggers a background refetch while
    // keeping the previous value visible.  This avoids a flash of stale
    // fallback data (the equipment-independent ideal lap) during the
    // transition.  invalidateQueries overrides staleTime: Infinity.
    queryClient.invalidateQueries({ queryKey });
  }
}

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
      // Default profile changes may affect session equipment auto-assignment
      queryClient.invalidateQueries({ queryKey: ["session"] });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
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
      // Deleted profile may have been assigned to sessions
      invalidatePhysicsQueries(queryClient);
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
    onSuccess: (data, variables) => {
      // Write the PUT response directly into the cache — instant UI update,
      // no extra GET round-trip.
      queryClient.setQueryData(
        ["session-equipment", variables.sessionId],
        data,
      );
      queryClient.invalidateQueries({
        queryKey: ["session", variables.sessionId],
      });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      invalidatePhysicsQueries(queryClient, variables.sessionId);
    },
  });
}

// --- Tire Search ---

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      profileId,
      body,
    }: {
      profileId: string;
      body: EquipmentProfileCreate;
    }) =>
      fetchApi<EquipmentProfile>(
        `/api/equipment/profiles/${profileId}`,
        {
          method: "PATCH",
          body: JSON.stringify(body),
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipment-profiles"] });
      // Profile edits (e.g. vehicle change) affect optimal lap time calculations
      // for any session using this profile — invalidate all session details
      queryClient.invalidateQueries({ queryKey: ["session"] });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      invalidatePhysicsQueries(queryClient);
    },
  });
}

// --- Vehicle Search ---

export function useVehicleSearch(query: string) {
  return useQuery({
    queryKey: ["vehicle-search", query],
    queryFn: () => searchVehicles(query),
    enabled: query.length >= 2,
    staleTime: 60_000,
  });
}

export function useVehicleSpec(make: string, model: string, generation?: string) {
  return useQuery({
    queryKey: ["vehicle-spec", make, model, generation],
    queryFn: () => getVehicleSpec(make, model, generation),
    enabled: !!make && !!model,
    staleTime: Infinity,
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
    enabled: true,
    staleTime: 60_000,
  });
}

// --- Brake Pad Search ---

export function useBrakePadSearch(query: string) {
  return useQuery({
    queryKey: ["brake-pad-search", query],
    queryFn: () =>
      fetchApi<BrakePadSearchResult[]>(
        `/api/equipment/brakes/search?q=${encodeURIComponent(query)}`,
      ),
    enabled: true,
    staleTime: 60_000,
  });
}

// --- Reference Data ---

export function useCommonTireSizes() {
  return useQuery({
    queryKey: ["common-tire-sizes"],
    queryFn: () =>
      fetchApi<string[]>("/api/equipment/reference/tire-sizes"),
    staleTime: Infinity,
  });
}

export function useCommonBrakeFluids() {
  return useQuery({
    queryKey: ["common-brake-fluids"],
    queryFn: () =>
      fetchApi<string[]>("/api/equipment/reference/brake-fluids"),
    staleTime: Infinity,
  });
}

// --- Session Weather ---

export function useSessionWeather(sessionId: string | null) {
  return useQuery({
    queryKey: ["session-weather", sessionId],
    queryFn: () =>
      fetchApi<{ session_id: string; weather: SessionWeather | null }>(
        `/api/sessions/${sessionId}/weather`,
      ),
    enabled: !!sessionId,
    staleTime: Infinity, // Weather is immutable per session
  });
}
