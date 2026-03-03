'use client';

import { useQuery } from '@tanstack/react-query';
import { getComparison, getShareComparison } from '@/lib/api';
import type { ComparisonResult, ShareComparisonResult } from '@/lib/types';

export function useComparison(sessionId: string | null, otherId: string | null) {
  return useQuery<ComparisonResult>({
    queryKey: ['comparison', sessionId, otherId],
    queryFn: () => getComparison(sessionId!, otherId!),
    enabled: !!sessionId && !!otherId,
  });
}

export function useShareComparison(token: string | null) {
  return useQuery<ShareComparisonResult>({
    queryKey: ['share-comparison', token],
    queryFn: () => getShareComparison(token!),
    enabled: !!token,
  });
}
