import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "@/lib/api";

export function useCoachingReport(sessionId: string | null) {
  return useQuery({
    queryKey: ["coaching-report", sessionId],
    queryFn: () => fetchApi(`/api/coaching/${sessionId}/report`),
    enabled: !!sessionId,
  });
}

export function useGenerateReport(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      fetchApi(`/api/coaching/${sessionId}/report`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["coaching-report", sessionId] });
    },
  });
}
