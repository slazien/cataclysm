import { useQuery } from "@tanstack/react-query";
import { getTrends, getMilestones } from "@/lib/api";

export function useTrends(trackName: string | null) {
  return useQuery({
    queryKey: ["trends", trackName],
    queryFn: () => getTrends(trackName!),
    enabled: !!trackName,
  });
}

export function useMilestones(trackName: string | null) {
  return useQuery({
    queryKey: ["milestones", trackName],
    queryFn: () => getMilestones(trackName!),
    enabled: !!trackName,
  });
}
