'use client';

import { useEffect, useRef } from 'react';
import { useCoachingReport, useGenerateReport } from '@/hooks/useCoaching';
import { useUiStore } from '@/stores';
import type { CoachingReport } from '@/lib/types';

interface UseAutoReportResult {
  report: CoachingReport | undefined;
  isLoading: boolean;
  isGenerating: boolean;
}

/**
 * Auto-triggers coaching report generation on mount if no report exists.
 * Returns the report data, loading state, and generation state.
 */
export function useAutoReport(sessionId: string | null): UseAutoReportResult {
  const { data: report, isLoading, isError } = useCoachingReport(sessionId);
  const generateReport = useGenerateReport();
  const skillLevel = useUiStore((s) => s.skillLevel);
  const hasTriggered = useRef(false);

  // Auto-trigger report generation if no report exists
  useEffect(() => {
    if (
      !isLoading &&
      (isError || !report) &&
      !generateReport.isPending &&
      !hasTriggered.current
    ) {
      hasTriggered.current = true;
      generateReport.mutate({ sessionId: sessionId!, skillLevel });
    }
  }, [sessionId, isLoading, isError, report, generateReport, skillLevel]);

  // Reset trigger flag when session changes
  useEffect(() => {
    hasTriggered.current = false;
  }, [sessionId]);

  return {
    report,
    isLoading: isLoading || generateReport.isPending,
    isGenerating: generateReport.isPending,
  };
}
