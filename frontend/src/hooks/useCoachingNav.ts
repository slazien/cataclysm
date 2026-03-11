import { useCallback } from 'react';
import { useUiStore, useAnalysisStore } from '@/stores';
import type { CoachingLinkHandlers } from '@/lib/coachingLinks';

/**
 * Returns CoachingLinkHandlers that navigate to corners/laps in Deep Dive.
 * Pass the result directly to MarkdownText's `linkHandlers` prop.
 */
export function useCoachingNav(): CoachingLinkHandlers {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const setMode = useAnalysisStore((s) => s.setMode);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const selectLaps = useAnalysisStore((s) => s.selectLaps);

  const onCornerClick = useCallback(
    (cornerNum: number) => {
      selectCorner(`T${cornerNum}`);
      setMode('corner');
      setActiveView('deep-dive');
    },
    [selectCorner, setMode, setActiveView],
  );

  const onLapClick = useCallback(
    (lapNum: number) => {
      selectLaps([lapNum]);
      setMode('speed');
      setActiveView('deep-dive');
    },
    [selectLaps, setMode, setActiveView],
  );

  return { onCornerClick, onLapClick };
}
