'use client';

import { useParams, useSearchParams } from 'next/navigation';
import { useComparison } from '@/hooks/useComparison';
import { ComparisonOverview } from '@/components/comparison/ComparisonOverview';
import { SessionSelector } from '@/components/comparison/SessionSelector';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { EmptyState } from '@/components/shared/EmptyState';

export default function ComparePage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();

  const sessionAId = params.id;
  const sessionBId = searchParams.get('with');

  const { data, isLoading, error } = useComparison(sessionAId, sessionBId);

  // No comparison target selected -- show session picker
  if (!sessionBId) {
    return <SessionSelector currentSessionId={sessionAId} />;
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <CircularProgress size={32} />
        <p className="text-sm text-[var(--text-secondary)]">Loading comparison data...</p>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <EmptyState
        title="Comparison failed"
        message={
          error instanceof Error
            ? error.message
            : 'An error occurred while loading comparison data.'
        }
      />
    );
  }

  // No data
  if (!data) {
    return (
      <EmptyState
        title="No comparison data"
        message="The comparison could not be loaded. Please check that both sessions exist."
      />
    );
  }

  return <ComparisonOverview data={data} />;
}
