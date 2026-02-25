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
 * Returns the report data, loading state, generation state, error state, and retry function.
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
      (queryError || !report) &&
      !generateReportRef.current.isPending &&
      !hasTriggered.current
    ) {
      hasTriggered.current = true;
      generateReportRef.current.mutate({ sessionId, skillLevel });
    }
  }, [sessionId, isLoading, queryError, report, skillLevel]);

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

  const hasError = generateReport.isError;

  return {
    report,
    isLoading: isLoading || generateReport.isPending,
    isGenerating: generateReport.isPending,
    isError: hasError,
    retry,
  };
}
