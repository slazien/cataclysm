import { useMemo } from 'react';
import type { CoachingReport, OptimalComparisonData, MergedPriority } from '@/lib/types';

/**
 * Merge physics-ranked corner_opportunities with LLM coaching text.
 * Physics provides ranking + time costs; LLM provides issue/tip text.
 * Falls back to LLM-only priority_corners when physics unavailable.
 */
export function useMergedPriorities(
  report: CoachingReport | undefined,
  optimalComparison: OptimalComparisonData | undefined,
  maxCorners: number,
): MergedPriority[] {
  return useMemo(() => {
    if (!report) return [];

    const opportunities = optimalComparison?.corner_opportunities;
    const priorities = report.priority_corners;

    // Physics path: rank by corner_opportunities, attach LLM text.
    // Only include corners with meaningful time cost (>0) — corners where
    // the driver matches/exceeds optimal shouldn't appear as priorities.
    if (opportunities && opportunities.length > 0) {
      const validOpps = opportunities.filter((opp) => opp.time_cost_s > 0);
      if (validOpps.length > 0) {
        const priorityMap = new Map(
          priorities?.map((p) => [p.corner, p]) ?? [],
        );
        return validOpps.slice(0, maxCorners).map((opp) => {
          const llm = priorityMap.get(opp.corner_number);
          return {
            corner: opp.corner_number,
            time_cost_s: opp.time_cost_s,
            issue: llm?.issue ?? null,
            tip: llm?.tip ?? null,
            source: 'physics' as const,
            speed_gap_mph: opp.speed_gap_mph,
            brake_gap_m: opp.brake_gap_m ?? null,
            exit_straight_time_cost_s: opp.exit_straight_time_cost_s,
          };
        });
      }
      // All physics corners have zero time cost — fall through to LLM path
    }

    // Fallback: LLM-only (no physics available)
    if (priorities && priorities.length > 0) {
      return priorities.slice(0, maxCorners).map((p) => ({
        corner: p.corner,
        time_cost_s: p.time_cost_s,
        issue: p.issue,
        tip: p.tip,
        source: 'llm' as const,
        speed_gap_mph: null,
        brake_gap_m: null,
        exit_straight_time_cost_s: null,
      }));
    }

    return [];
  }, [report, optimalComparison, maxCorners]);
}
