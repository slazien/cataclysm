'use client';

import { useCallback, useEffect, useRef } from 'react';
import { useCoachingReport, useGenerateReport } from '@/hooks/useCoaching';
import { useUiStore } from '@/stores';
import type { CoachingReport } from '@/lib/types';

interface UseAutoReportResult {
  report: CoachingReport | undefined;
  isLoading: boolean;
  isGenerating: boolean;
  isError: boolean;
  retry: () => void;
}

/**
 * Auto-triggers coaching report generation on mount if no report exists.
 *
 * Flow:
 * 1. GET report → 404 means no report exists
 * 2. POST to trigger generation → returns {status: "generating"} instantly
 * 3. POST onSuccess invalidates the query → GET now returns {status: "generating"}
 * 4. refetchInterval polls GET every 2s until status is "ready"
 */
export function useAutoReport(sessionId: string | null): UseAutoReportResult {
  const { data: report, isLoading, isError: queryError, isFetching } = useCoachingReport(sessionId);
  const generateReport = useGenerateReport();
  const skillLevel = useUiStore((s) => s.skillLevel);
  const hasTriggered = useRef(false);

  const generateReportRef = useRef(generateReport);
  useEffect(() => { generateReportRef.current = generateReport; });

  // Auto-trigger report generation when GET returns 404
  useEffect(() => {
    if (
      sessionId !== null &&
      !isLoading &&
      queryError &&
      !generateReportRef.current.isPending &&
      !hasTriggered.current
    ) {
      hasTriggered.current = true;
      generateReportRef.current.mutate({ sessionId, skillLevel });
    }
  }, [sessionId, isLoading, queryError, skillLevel]);

  // Reset trigger flag when session changes
  useEffect(() => {
    hasTriggered.current = false;
  }, [sessionId]);

  const retry = useCallback(() => {
    if (sessionId !== null) {
      hasTriggered.current = true;
      generateReportRef.current.mutate({ sessionId, skillLevel });
    }
  }, [sessionId, skillLevel]);

  const isGenerating = report?.status === 'generating' || generateReport.isPending;
  const hasError = generateReport.isError || report?.status === 'error';
  const isReady = report?.status === 'ready';

  return {
    report: isReady ? report : undefined,
    // Show loading state during: initial fetch, mutation pending, refetching, or generating
    isLoading: isLoading || generateReport.isPending || isGenerating || (isFetching && !isReady),
    isGenerating,
    isError: hasError && !isGenerating,
    retry,
  };
}
