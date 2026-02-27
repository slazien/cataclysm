'use client';

import { useQuery } from '@tanstack/react-query';
import type { WrappedData } from '@/lib/types';
import { getWrapped } from '@/lib/api';

export function useWrapped(year: number, enabled = true) {
  return useQuery<WrappedData>({
    queryKey: ['wrapped', year],
    queryFn: () => getWrapped(year),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}
