"use client";

import { useQuery, useQueries, keepPreviousData } from "@tanstack/react-query";
import { getCorners, getAllLapCorners, getConsistency, getGains, getGrip, getDelta, getLapData, getGPSQuality, getMiniSectors, getDegradation, getOptimalComparison, getGGDiagram, getLineAnalysis, getIdealLap } from "@/lib/api";
import type { Corner, SessionConsistency, DeltaData, LapData, GPSQualityReport, MiniSectorData, DegradationData, OptimalComparisonData, GGDiagramData, LineAnalysisData, IdealLapData } from "@/lib/types";
import { useSessionEquipment } from "./useEquipment";

// Telemetry data is immutable per session — never refetch once cached.
const IMMUTABLE = { staleTime: Infinity } as const;

export function useCorners(sessionId: string | null) {
  return useQuery<Corner[]>({
    queryKey: ["corners", sessionId],
    queryFn: () => getCorners(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}

export function useAllLapCorners(sessionId: string | null) {
  return useQuery<Record<string, Corner[]>>({
    queryKey: ["all-lap-corners", sessionId],
    queryFn: () => getAllLapCorners(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}

export function useConsistency(sessionId: string | null) {
  return useQuery<SessionConsistency>({
    queryKey: ["consistency", sessionId],
    queryFn: () => getConsistency(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}

export function useGains(sessionId: string | null) {
  return useQuery<Record<string, unknown>>({
    queryKey: ["gains", sessionId],
    queryFn: () => getGains(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}

export function useGrip(sessionId: string | null) {
  return useQuery<Record<string, unknown>>({
    queryKey: ["grip", sessionId],
    queryFn: () => getGrip(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}

export function useDelta(
  sessionId: string | null,
  ref: number | null,
  comp: number | null,
) {
  return useQuery<DeltaData>({
    queryKey: ["delta", sessionId, ref, comp],
    queryFn: () => getDelta(sessionId!, ref!, comp!),
    enabled: !!sessionId && ref !== null && comp !== null,
    ...IMMUTABLE,
  });
}

export function useGPSQuality(sessionId: string | null) {
  return useQuery<GPSQualityReport>({
    queryKey: ["gps-quality", sessionId],
    queryFn: () => getGPSQuality(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}

export function useMultiLapData(
  sessionId: string | null,
  lapNumbers: number[],
) {
  const results = useQueries({
    queries: lapNumbers.map((lap) => ({
      queryKey: ["lap-data", sessionId, lap],
      queryFn: () => getLapData(sessionId!, lap),
      enabled: !!sessionId,
      staleTime: Infinity,
    })),
  });

  // Use isPending (not isLoading) so paused queries (mobile background, network
  // blip) also show a spinner.  React Query v5: isLoading = isPending && isFetching;
  // a paused query has isFetching=false so isLoading=false even with no data yet.
  const isLoading = results.some((r) => r.isPending);
  const data = results
    .map((r) => r.data)
    .filter((d): d is LapData => d !== undefined);

  return { data, isLoading };
}

export function useMiniSectors(
  sessionId: string | null,
  nSectors: number = 20,
  lap?: number,
) {
  return useQuery<MiniSectorData>({
    queryKey: ["mini-sectors", sessionId, nSectors, lap],
    queryFn: () => getMiniSectors(sessionId!, nSectors, lap),
    enabled: !!sessionId,
    retry: 1,
    ...IMMUTABLE,
  });
}

export function useDegradation(sessionId: string | null) {
  return useQuery<DegradationData>({
    queryKey: ["degradation", sessionId],
    queryFn: () => getDegradation(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}

export function useOptimalComparison(sessionId: string | null) {
  // Include the equipment profile_id in the query key so that switching
  // equipment automatically creates a separate cache entry — no manual
  // invalidation needed and no TOCTOU race with stale data.
  //
  // Wait for the equipment query to settle before fetching.  Without this,
  // profileId is null while equipment is loading, which fires a redundant
  // computation with default vehicle params that gets thrown away once the
  // real profileId arrives.
  const { data: equipment, isFetched: equipmentSettled } = useSessionEquipment(sessionId);
  const profileId = equipment?.profile_id ?? null;

  return useQuery<OptimalComparisonData>({
    queryKey: ["optimal-comparison", sessionId, profileId],
    queryFn: () => getOptimalComparison(sessionId!, profileId),
    enabled: !!sessionId && equipmentSettled,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  });
}

export function useGGDiagram(sessionId: string | null, corner?: number) {
  return useQuery<GGDiagramData>({
    queryKey: ["gg-diagram", sessionId, corner],
    queryFn: () => getGGDiagram(sessionId!, corner),
    enabled: !!sessionId,
    placeholderData: keepPreviousData,
    ...IMMUTABLE,
  });
}

export function useLineAnalysis(
  sessionId: string | null,
  laps?: number[],
) {
  return useQuery<LineAnalysisData>({
    queryKey: ["line-analysis", sessionId, laps],
    queryFn: () => getLineAnalysis(sessionId!, laps),
    // Don't fire with empty lap array — backend returns available:false anyway, and
    // isPending=true on a disabled query would show a ghost spinner when 0 laps selected.
    enabled: !!sessionId && (laps === undefined || laps.length > 0),
    ...IMMUTABLE,
  });
}

export function useIdealLap(sessionId: string | null) {
  return useQuery<IdealLapData>({
    queryKey: ["ideal-lap", sessionId],
    queryFn: () => getIdealLap(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}
