'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getCoachingFeedback, submitCoachingFeedback } from '@/lib/api';
import type { CoachingFeedback } from '@/lib/types';

export function useCoachingFeedback(sessionId: string | null) {
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: ['coaching-feedback', sessionId],
    queryFn: () => getCoachingFeedback(sessionId!),
    enabled: !!sessionId,
  });

  const mutation = useMutation({
    mutationFn: async ({
      section,
      rating,
      comment,
    }: {
      section: string;
      rating: number;
      comment?: string;
    }) => {
      if (!sessionId) throw new Error('No session');
      return submitCoachingFeedback(sessionId, section, rating, comment);
    },
    onMutate: async ({ section, rating, comment }) => {
      await qc.cancelQueries({ queryKey: ['coaching-feedback', sessionId] });
      const prev = qc.getQueryData<{ feedback: CoachingFeedback[] }>([
        'coaching-feedback',
        sessionId,
      ]);

      qc.setQueryData<{ feedback: CoachingFeedback[] }>(
        ['coaching-feedback', sessionId],
        (old) => {
          const existing = old?.feedback ?? [];
          const filtered = existing.filter((f) => f.section !== section);
          if (rating !== 0) {
            filtered.push({
              session_id: sessionId!,
              section,
              rating,
              comment: comment ?? null,
            });
          }
          return { feedback: filtered };
        },
      );

      return { prev };
    },
    onError: (_err, _vars, context) => {
      if (context?.prev) {
        qc.setQueryData(['coaching-feedback', sessionId], context.prev);
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['coaching-feedback', sessionId] });
    },
  });

  function getRating(section: string): number {
    const fb = query.data?.feedback?.find((f) => f.section === section);
    return fb?.rating ?? 0;
  }

  return { ...query, getRating, submitFeedback: mutation };
}
