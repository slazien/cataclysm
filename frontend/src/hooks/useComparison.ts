'use client';

import { useQuery } from '@tanstack/react-query';
import { getComparison } from '@/lib/api';
import type { ComparisonResult } from '@/lib/types';

export function useComparison(sessionId: string | null, otherId: string | null) {
  return useQuery<ComparisonResult>({
    queryKey: ['comparison', sessionId, otherId],
    queryFn: () => getComparison(sessionId!, otherId!),
    enabled: !!sessionId && !!otherId,
  });
}
