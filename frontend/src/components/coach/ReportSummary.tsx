'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, Volume2, VolumeX } from 'lucide-react';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { GradeChip } from '@/components/shared/GradeChip';
import { AiInsight } from '@/components/shared/AiInsight';
import { Button } from '@/components/ui/button';
import { useSessionStore } from '@/stores';
import { useAutoReport } from '@/hooks/useAutoReport';
import { useSpeechSynthesis } from '@/hooks/useSpeechSynthesis';
import type { CoachingReport } from '@/lib/types';

function buildSpeechText(report: CoachingReport): string {
  const parts: string[] = [];

  if (report.summary) {
    parts.push(report.summary);
  }

  if (report.priority_corners.length > 0) {
    parts.push('Here are your top priorities.');
    report.priority_corners.slice(0, 3).forEach((pc, i) => {
      const ordinal = ['First', 'Second', 'Third'][i];
      parts.push(
        `${ordinal}: Turn ${pc.corner}. ${pc.issue}. ${pc.tip}. This costs you ${pc.time_cost_s.toFixed(2)} seconds per lap.`,
      );
    });
  }

  if (report.patterns.length > 0) {
    parts.push('Key patterns I noticed: ' + report.patterns.join('. ') + '.');
  }

  return parts.join(' ');
}

export function ReportSummary() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { report, isLoading, isGenerating, isError, retry } = useAutoReport(activeSessionId);
  const [gradesExpanded, setGradesExpanded] = useState(false);
  const speech = useSpeechSynthesis();

  const speechText = useMemo(
    () => (report?.status === 'ready' ? buildSpeechText(report) : ''),
    [report],
  );

  const handleToggleSpeech = useCallback(() => {
    speech.toggle(speechText);
  }, [speech, speechText]);

  // Stop speech when session changes
  useEffect(() => {
    speech.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]);

  if (!activeSessionId) {
    return (
      <div className="px-4 py-3 border-b border-[var(--cata-border)]">
        <p className="text-xs text-[var(--text-tertiary)]">
          Select a session to see coaching insights.
        </p>
      </div>
    );
  }

  if (isLoading || isGenerating) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--cata-border)]">
        <CircularProgress size={16} strokeWidth={2} />
        <span className="text-xs text-[var(--text-secondary)]">
          {isGenerating ? 'Generating coaching report...' : 'Loading report...'}
        </span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="px-4 py-3 border-b border-[var(--cata-border)]">
        <p className="text-xs text-[var(--grade-f)]">Failed to generate report.</p>
        <button
          onClick={retry}
          className="mt-1 text-xs text-[var(--cata-accent)] hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="border-b border-[var(--cata-border)]">
      {/* Summary */}
      {report.summary && (
        <div className="px-4 py-3">
          <AiInsight mode="compact">
            <span className="text-xs leading-relaxed">{report.summary}</span>
          </AiInsight>
          {speech.isSupported && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleToggleSpeech}
              className="mt-2 h-7 gap-1.5 text-[10px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            >
              {speech.state === 'idle' ? (
                <>
                  <Volume2 className="h-3.5 w-3.5" />
                  Listen
                </>
              ) : (
                <>
                  <VolumeX
                    className={`h-3.5 w-3.5 ${speech.state === 'speaking' ? 'animate-pulse' : ''}`}
                  />
                  {speech.state === 'speaking' ? 'Pause' : 'Resume'}
                </>
              )}
            </Button>
          )}
        </div>
      )}

      {/* Validation disclaimer */}
      {report.validation_failed && (
        <div className="mx-4 mb-2 flex items-start gap-2 rounded-md bg-amber-500/10 border border-amber-500/30 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" />
          <div>
            <p className="text-xs font-medium text-amber-400">
              Review with caution
            </p>
            <p className="text-[10px] text-amber-400/80 leading-relaxed mt-0.5">
              Automated checks flagged potential inaccuracies in this report.
              Verify advice against your own track knowledge before applying.
            </p>
          </div>
        </div>
      )}

      {/* Corner Grades */}
      {report.corner_grades.length > 0 && (
        <div className="px-4 pb-2">
          <button
            onClick={() => setGradesExpanded(!gradesExpanded)}
            className="flex items-center gap-1 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            {gradesExpanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            Corner Grades ({report.corner_grades.length})
          </button>

          {gradesExpanded && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="text-[var(--text-tertiary)]">
                    <th className="pb-1 pr-2 text-left font-medium">Corner</th>
                    <th className="pb-1 px-1 text-center font-medium">Brake</th>
                    <th className="pb-1 px-1 text-center font-medium">Trail</th>
                    <th className="pb-1 px-1 text-center font-medium">Speed</th>
                    <th className="pb-1 pl-1 text-center font-medium">Throttle</th>
                  </tr>
                </thead>
                <tbody>
                  {report.corner_grades.map((grade) => (
                    <tr key={grade.corner} className="border-t border-[var(--cata-border)]/50">
                      <td className="py-1 pr-2 text-[var(--text-primary)] font-medium">
                        T{grade.corner}
                      </td>
                      <td className="py-1 px-1 text-center">
                        <GradeChip grade={grade.braking} className="text-[9px] px-1.5 py-0" />
                      </td>
                      <td className="py-1 px-1 text-center">
                        <GradeChip grade={grade.trail_braking} className="text-[9px] px-1.5 py-0" />
                      </td>
                      <td className="py-1 px-1 text-center">
                        <GradeChip grade={grade.min_speed} className="text-[9px] px-1.5 py-0" />
                      </td>
                      <td className="py-1 pl-1 text-center">
                        <GradeChip grade={grade.throttle} className="text-[9px] px-1.5 py-0" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Patterns */}
      {report.patterns.length > 0 && (
        <div className="px-4 pb-2">
          <h4 className="text-[10px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider mb-1">
            Patterns
          </h4>
          <ul className="space-y-0.5">
            {report.patterns.map((pattern, i) => (
              <li key={i} className="text-xs text-[var(--text-secondary)] leading-relaxed">
                &bull; {pattern}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Drills */}
      {report.drills.length > 0 && (
        <div className="px-4 pb-3">
          <h4 className="text-[10px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider mb-1">
            Drills
          </h4>
          <ul className="space-y-0.5">
            {report.drills.map((drill, i) => (
              <li key={i} className="text-xs text-[var(--text-secondary)] leading-relaxed">
                &bull; {drill}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
