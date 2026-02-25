'use client';

import { useMemo } from 'react';
import { useAnalysisStore, useUiStore } from '@/stores';

interface SuggestedQuestionsProps {
  onAsk: (question: string) => void;
}

export function SuggestedQuestions({ onAsk }: SuggestedQuestionsProps) {
  const activeView = useUiStore((s) => s.activeView);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);

  const questions = useMemo(() => {
    if (activeView === 'progress') {
      return ['Am I improving?', "What's my biggest gain area?"];
    }

    if (activeView === 'deep-dive') {
      const qs: string[] = [];

      if (selectedCorner) {
        const turnNum = selectedCorner.replace('T', '');
        qs.push(`How do I improve Turn ${turnNum}?`);
        qs.push("What's my brake point issue?");
      }

      if (selectedLaps.length === 2) {
        qs.push(`Why was lap ${selectedLaps[0]} faster?`);
        qs.push('Where am I losing time?');
      }

      if (qs.length === 0) {
        qs.push('What should I focus on in this session?');
        qs.push('Which corner costs me the most time?');
      }

      return qs;
    }

    // Dashboard default
    return ['What should I focus on?', 'How can I be more consistent?'];
  }, [activeView, selectedLaps, selectedCorner]);

  return (
    <div className="px-4 py-2 border-b border-[var(--cata-border)]">
      <p className="text-[10px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider mb-1.5">
        Suggested
      </p>
      <div className="flex flex-wrap gap-1.5">
        {questions.map((q) => (
          <button
            key={q}
            onClick={() => onAsk(q)}
            className="rounded-full border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-3 py-1 text-[11px] text-[var(--text-secondary)] hover:border-[var(--cata-accent)] hover:text-[var(--text-primary)] transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
