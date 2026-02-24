"use client";

import { useQuery } from "@tanstack/react-query";
import { getCorners, getConsistency, getGains, getGrip } from "@/lib/api";
import type { Corner, SessionConsistency } from "@/lib/types";

export function useCorners(sessionId: string | null) {
  return useQuery<Corner[]>({
    queryKey: ["corners", sessionId],
    queryFn: () => getCorners(sessionId!),
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
