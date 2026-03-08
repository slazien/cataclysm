import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listStickies,
  createSticky,
  updateSticky,
  deleteSticky,
} from "@/lib/api";
import type { StickyCreate, StickyUpdate } from "@/lib/types";

const STICKIES_KEY = ["stickies"] as const;

export function useStickies() {
  return useQuery({
    queryKey: STICKIES_KEY,
    queryFn: () => listStickies(),
    staleTime: 30_000,
  });
}

export function useCreateSticky() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: StickyCreate) => createSticky(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: STICKIES_KEY });
    },
  });
}

export function useUpdateSticky() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      stickyId,
      body,
    }: {
      stickyId: string;
      body: StickyUpdate;
    }) => updateSticky(stickyId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: STICKIES_KEY });
    },
  });
}

export function useDeleteSticky() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (stickyId: string) => deleteSticky(stickyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: STICKIES_KEY });
    },
  });
}
