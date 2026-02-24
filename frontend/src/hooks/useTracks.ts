"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listTracks, loadTrackFolder } from "@/lib/api";

export function useTracks() {
  return useQuery({
    queryKey: ["tracks"],
    queryFn: listTracks,
  });
}

export function useLoadTrackFolder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (folder: string) => loadTrackFolder(folder),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
}
