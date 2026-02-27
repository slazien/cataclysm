'use client';

import { useMemo } from 'react';
import { useCoachingReport } from '@/hooks/useCoaching';
import { RadarChart } from '@/components/shared/RadarChart';
import {
  computeSkillDimensions,
  dimensionsToArray,
  SKILL_AXES,
} from '@/lib/skillDimensions';

interface SkillRadarProps {
  sessionId: string;
}

export function SkillRadar({ sessionId }: SkillRadarProps) {
  const { data: report } = useCoachingReport(sessionId);

  const dimensions = useMemo(() => {
    if (!report?.corner_grades || report.corner_grades.length === 0) return null;
    return computeSkillDimensions(report.corner_grades);
  }, [report]);

  if (!dimensions) return null;

  const values = dimensionsToArray(dimensions);
  const avgScore = Math.round(values.reduce((a, b) => a + b, 0) / values.length);

  return (
    <div className="self-start rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Skill Profile</h3>
        <span className="text-xs text-[var(--text-tertiary)]">Avg: {avgScore}/100</span>
      </div>
      <RadarChart
        axes={SKILL_AXES}
        datasets={[{ label: 'Session', values, color: '#6366f1' }]}
        size={200}
      />
    </div>
  );
}
