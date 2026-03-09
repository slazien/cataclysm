import { useMutation, useQuery } from "@tanstack/react-query";
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
  return useMutation({
    mutationFn: (body: StickyCreate) => createSticky(body),
  });
}

export function useUpdateSticky() {
  return useMutation({
    mutationFn: ({
      stickyId,
      body,
    }: {
      stickyId: string;
      body: StickyUpdate;
    }) => updateSticky(stickyId, body),
  });
}

export function useDeleteSticky() {
  return useMutation({
    mutationFn: (stickyId: string) => deleteSticky(stickyId),
  });
}
