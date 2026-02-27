'use client';

import { useQuery } from '@tanstack/react-query';
import type { AchievementListData, NewAchievementsData } from '@/lib/types';
import { getAchievements, getRecentAchievements } from '@/lib/api';

export function useAchievements(enabled = true) {
  return useQuery<AchievementListData>({
    queryKey: ['achievements'],
    queryFn: getAchievements,
    enabled,
    staleTime: 30_000,
  });
}

export function useRecentAchievements(enabled = true) {
  return useQuery<NewAchievementsData>({
    queryKey: ['achievements', 'recent'],
    queryFn: getRecentAchievements,
    enabled,
    staleTime: 10_000,
  });
}
