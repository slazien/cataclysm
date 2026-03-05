'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle, ChevronDown, ChevronRight, Volume2, VolumeX } from 'lucide-react';
import { SkillLevelMismatchBanner } from '@/components/coach/SkillLevelMismatchBanner';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { GradeChip } from '@/components/shared/GradeChip';
import { AiInsight } from '@/components/shared/AiInsight';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { Button } from '@/components/ui/button';
import { useSessionStore, useUiStore } from '@/stores';
import { useAutoReport } from '@/hooks/useAutoReport';
import { useSpeechSynthesis } from '@/hooks/useSpeechSynthesis';
import { useUnits } from '@/hooks/useUnits';
import { formatCoachingText } from '@/lib/textUtils';
import type { CoachingReport } from '@/lib/types';

const gradeContainerVariants = {
  initial: {},
  animate: {
    transition: { staggerChildren: 0.04 },
  },
};

const gradeChipVariants = {
  initial: { opacity: 0, scale: 0.8 },
  animate: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.2, ease: 'easeOut' as const },
  },
};

function buildSpeechText(
  report: CoachingReport,
  resolveSpeed: (t: string) => string,
): string {
  const parts: string[] = [];

  if (report.primary_focus) {
    parts.push('Your primary focus: ' + resolveSpeed(report.primary_focus));
  }

  if (report.summary) {
    parts.push(resolveSpeed(report.summary));
  }

  if (report.priority_corners.length > 0) {
    parts.push('Here are your top priorities.');
    report.priority_corners.slice(0, 3).forEach((pc, i) => {
      const ordinal = ['First', 'Second', 'Third'][i];
      parts.push(
        `${ordinal}: Turn ${pc.corner}. ${resolveSpeed(pc.issue)}. ${resolveSpeed(pc.tip)}. This costs you ${pc.time_cost_s.toFixed(2)} seconds per lap.`,
      );
    });
  }

  if (report.patterns.length > 0) {
    parts.push(
      'Key patterns I noticed: ' + report.patterns.map(resolveSpeed).join('. ') + '.',
    );
  }

  return parts.join(' ');
}

export function ReportSummary() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { report, isLoading, isGenerating, isError, isSkillMismatch, retry, regenerate } = useAutoReport(activeSessionId);
  const skillLevel = useUiStore((s) => s.skillLevel);
  const [gradesExpanded, setGradesExpanded] = useState(false);
  const speech = useSpeechSynthesis();
  const { resolveSpeed } = useUnits();

  const speechText = useMemo(
    () => (report?.status === 'ready' ? buildSpeechText(report, resolveSpeed) : ''),
    [report, resolveSpeed],
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
      {/* Skill level mismatch banner */}
      {isSkillMismatch && report.skill_level && (
        <div className="pt-2">
          <SkillLevelMismatchBanner
            reportLevel={report.skill_level}
            currentLevel={skillLevel}
            onRegenerate={regenerate}
          />
        </div>
      )}

      {/* Primary Focus — the ONE thing to work on */}
      {report.primary_focus && (
        <div className="px-4 pt-3 pb-1">
          <div className="rounded-md bg-[var(--cata-accent)]/10 border border-[var(--cata-accent)]/30 px-3 py-2">
            <h4 className="text-[10px] font-medium text-[var(--cata-accent)] uppercase tracking-wider mb-1">
              Primary Focus
            </h4>
            <p className="text-xs text-[var(--text-primary)] leading-relaxed">
              <MarkdownText>{formatCoachingText(resolveSpeed(report.primary_focus))}</MarkdownText>
            </p>
          </div>
        </div>
      )}

      {/* Summary */}
      {report.summary && (
        <div className="px-4 py-3">
          <AiInsight mode="compact">
            <span className="text-xs leading-relaxed"><MarkdownText>{formatCoachingText(resolveSpeed(report.summary))}</MarkdownText></span>
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

          <AnimatePresence>
            {gradesExpanded && (
              <motion.div
                className="mt-2 overflow-x-auto"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
              >
                <motion.table
                  className="w-full text-[10px]"
                  variants={gradeContainerVariants}
                  initial="initial"
                  animate="animate"
                >
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
                      <motion.tr
                        key={grade.corner}
                        className="border-t border-[var(--cata-border)]/50"
                        variants={gradeChipVariants}
                      >
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
                      </motion.tr>
                    ))}
                  </tbody>
                </motion.table>
              </motion.div>
            )}
          </AnimatePresence>
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
                &bull; <MarkdownText>{formatCoachingText(resolveSpeed(pattern))}</MarkdownText>
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
                &bull; <MarkdownText>{formatCoachingText(resolveSpeed(drill))}</MarkdownText>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Report provenance */}
      {report.skill_level && (
        <div className="px-4 pb-2">
          <p className="text-[10px] text-[var(--text-tertiary)]">
            Generated for {report.skill_level.charAt(0).toUpperCase() + report.skill_level.slice(1)}
          </p>
        </div>
      )}
    </div>
  );
}
