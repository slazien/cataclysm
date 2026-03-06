"use client";

import { useQuery, useQueries, keepPreviousData } from "@tanstack/react-query";
import { getCorners, getAllLapCorners, getConsistency, getGains, getGrip, getDelta, getLapData, getGPSQuality, getMiniSectors, getDegradation, getOptimalComparison, getGGDiagram, getLineAnalysis } from "@/lib/api";
import type { Corner, SessionConsistency, DeltaData, LapData, GPSQualityReport, MiniSectorData, DegradationData, OptimalComparisonData, GGDiagramData, LineAnalysisData } from "@/lib/types";

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

  const isLoading = results.some((r) => r.isLoading);
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

export function useOptimalComparison(sessionId: string | null, equipmentProfileId?: string | null) {
  return useQuery<OptimalComparisonData>({
    queryKey: ["optimal-comparison", sessionId, equipmentProfileId ?? "default"],
    queryFn: () => getOptimalComparison(sessionId!),
    enabled: !!sessionId,
    ...IMMUTABLE,
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
    enabled: !!sessionId,
    ...IMMUTABLE,
  });
}
