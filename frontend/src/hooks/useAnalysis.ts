import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "@/lib/api";

export function useCorners(sessionId: string | null) {
  return useQuery({
    queryKey: ["corners", sessionId],
    queryFn: () => fetchApi(`/api/sessions/${sessionId}/corners`),
    enabled: !!sessionId,
  });
}

export function useConsistency(sessionId: string | null) {
  return useQuery({
    queryKey: ["consistency", sessionId],
    queryFn: () => fetchApi(`/api/sessions/${sessionId}/consistency`),
    enabled: !!sessionId,
  });
}

export function useGains(sessionId: string | null) {
  return useQuery({
    queryKey: ["gains", sessionId],
    queryFn: () => fetchApi(`/api/sessions/${sessionId}/gains`),
    enabled: !!sessionId,
  });
}
