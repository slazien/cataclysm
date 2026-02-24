"use client";

import { useQuery, useQueries } from "@tanstack/react-query";
import { getCorners, getAllLapCorners, getConsistency, getGains, getGrip, getDelta, getLapData } from "@/lib/api";
import type { Corner, SessionConsistency, DeltaData, LapData } from "@/lib/types";

export function useCorners(sessionId: string | null) {
  return useQuery<Corner[]>({
    queryKey: ["corners", sessionId],
    queryFn: () => getCorners(sessionId!),
    enabled: !!sessionId,
  });
}

export function useAllLapCorners(sessionId: string | null) {
  return useQuery<Record<string, Corner[]>>({
    queryKey: ["all-lap-corners", sessionId],
    queryFn: () => getAllLapCorners(sessionId!),
    enabled: !!sessionId,
  });
}

export function useConsistency(sessionId: string | null) {
  return useQuery<SessionConsistency>({
    queryKey: ["consistency", sessionId],
    queryFn: () => getConsistency(sessionId!),
    enabled: !!sessionId,
  });
}

export function useGains(sessionId: string | null) {
  return useQuery<Record<string, unknown>>({
    queryKey: ["gains", sessionId],
    queryFn: () => getGains(sessionId!),
    enabled: !!sessionId,
  });
}

export function useGrip(sessionId: string | null) {
  return useQuery<Record<string, unknown>>({
    queryKey: ["grip", sessionId],
    queryFn: () => getGrip(sessionId!),
    enabled: !!sessionId,
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
    })),
  });

  const isLoading = results.some((r) => r.isLoading);
  const data = results
    .map((r) => r.data)
    .filter((d): d is LapData => d !== undefined);

  return { data, isLoading };
}
