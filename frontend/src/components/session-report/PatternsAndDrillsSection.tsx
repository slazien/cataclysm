'use client';

import { useState } from 'react';
import { TrendingUp, Target, ChevronDown, ChevronUp } from 'lucide-react';
import { extractActionTitle, extractDetailText, formatCoachingText } from '@/lib/textUtils';
import { useUnits } from '@/hooks/useUnits';
import { MarkdownText } from '@/components/shared/MarkdownText';

const DEFAULT_VISIBLE = 3;

interface PatternsAndDrillsSectionProps {
  patterns: string[];
  drills: string[];
}

function ExpandableItem({ text, bullet }: { text: string; bullet: string }) {
  const [expanded, setExpanded] = useState(false);
  const title = extractActionTitle(text);
  const detail = extractDetailText(text);
  const hasDetail = detail.length > 0;

  return (
    <li className="text-sm text-[var(--text-secondary)]">
      <div className="flex items-start gap-1">
        <span className="mt-0.5 shrink-0 text-[var(--text-muted)]">{bullet}</span>
        <div className="min-w-0">
          <span><MarkdownText>{title}</MarkdownText></span>
          {hasDetail && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="ml-1.5 inline-flex items-center gap-0.5 text-xs text-[var(--text-muted)] transition-colors hover:text-[var(--text-secondary)]"
            >
              {expanded ? (
                <>Less <ChevronUp className="inline h-3 w-3" /></>
              ) : (
                <>More <ChevronDown className="inline h-3 w-3" /></>
              )}
            </button>
          )}
          {expanded && detail && (
            <div className="mt-1 text-[var(--text-muted)]">
              <MarkdownText block>{detail}</MarkdownText>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

export function PatternsAndDrillsSection({ patterns, drills }: PatternsAndDrillsSectionProps) {
  const [showAllPatterns, setShowAllPatterns] = useState(false);
  const { resolveSpeed } = useUnits();
  const resolvedPatterns = patterns.map((t) => formatCoachingText(resolveSpeed(t)));
  const resolvedDrills = drills.map((t) => formatCoachingText(resolveSpeed(t)));
  const visiblePatterns = showAllPatterns ? resolvedPatterns : resolvedPatterns.slice(0, DEFAULT_VISIBLE);
  const hiddenCount = resolvedPatterns.length - DEFAULT_VISIBLE;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {patterns.length > 0 && (
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-[var(--cata-accent)]" />
            <h4 className="font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-primary)]">Patterns</h4>
          </div>
          <ul className="space-y-1.5">
            {visiblePatterns.map((p, i) => (
              <ExpandableItem key={i} text={p} bullet="&bull;" />
            ))}
          </ul>
          {hiddenCount > 0 && (
            <button
              type="button"
              onClick={() => setShowAllPatterns(!showAllPatterns)}
              className="mt-2 flex items-center gap-1 text-xs text-[var(--text-muted)] transition-colors hover:text-[var(--text-secondary)]"
            >
              {showAllPatterns ? (
                <>Show less <ChevronUp className="h-3 w-3" /></>
              ) : (
                <>Show {hiddenCount} more <ChevronDown className="h-3 w-3" /></>
              )}
            </button>
          )}
        </div>
      )}
      {drills.length > 0 && (
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Target className="h-4 w-4 text-[var(--cata-accent)]" />
            <h4 className="font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-primary)]">Recommended Drills</h4>
          </div>
          <ul className="space-y-1.5">
            {resolvedDrills.map((d, i) => (
              <ExpandableItem key={i} text={d} bullet={`${i + 1}.`} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
