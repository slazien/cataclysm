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
 * 2. POST to trigger generation → returns {status: "generating"} immediately
 * 3. useCoachingReport polls GET every 2s until status is "ready"
 */
export function useAutoReport(sessionId: string | null): UseAutoReportResult {
  const { data: report, isLoading, isError: queryError } = useCoachingReport(sessionId);
  const generateReport = useGenerateReport();
  const skillLevel = useUiStore((s) => s.skillLevel);
  const hasTriggered = useRef(false);

  // Keep generateReport in a ref to avoid re-triggering the effect on mutation object changes
  const generateReportRef = useRef(generateReport);
  useEffect(() => { generateReportRef.current = generateReport; });

  // Auto-trigger report generation if no report exists
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

  // Allow manual retry by resetting the trigger flag and re-triggering
  const retry = useCallback(() => {
    if (sessionId !== null) {
      hasTriggered.current = false;
      generateReportRef.current.mutate({ sessionId, skillLevel });
    }
  }, [sessionId, skillLevel]);

  // Report is "generating" if we have data with status "generating"
  const isGenerating = report?.status === 'generating' || generateReport.isPending;

  // Only show error if the mutation itself failed (not if GET returned 404 — that's expected)
  const hasError = generateReport.isError || report?.status === 'error';

  // Report is ready when we have actual content
  const isReady = report?.status === 'ready';

  return {
    report: isReady ? report : undefined,
    isLoading: isLoading || isGenerating,
    isGenerating,
    isError: hasError,
    retry,
  };
}
