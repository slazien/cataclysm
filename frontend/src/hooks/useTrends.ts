import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "@/lib/api";

export function useTrends(trackName: string | null) {
  return useQuery({
    queryKey: ["trends", trackName],
    queryFn: () => fetchApi(`/api/trends/${trackName}`),
    enabled: !!trackName,
  });
}

export function useMilestones(trackName: string | null) {
  return useQuery({
    queryKey: ["milestones", trackName],
    queryFn: () => fetchApi(`/api/trends/${trackName}/milestones`),
    enabled: !!trackName,
  });
}
