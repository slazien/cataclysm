'use client';

import { useEffect, useCallback } from 'react';
import { useUiStore, useAnalysisStore, useCoachStore } from '@/stores';
import { useCorners } from '@/hooks/useAnalysis';
import { useSessionStore } from '@/stores';

export function useKeyboardShortcuts() {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const activeView = useUiStore((s) => s.activeView);
  const sessionDrawerOpen = useUiStore((s) => s.sessionDrawerOpen);
  const toggleSessionDrawer = useUiStore((s) => s.toggleSessionDrawer);

  const activeSessionId = useSessionStore((s) => s.activeSessionId);

  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const deepDiveMode = useAnalysisStore((s) => s.deepDiveMode);

  const panelOpen = useCoachStore((s) => s.panelOpen);
  const togglePanel = useCoachStore((s) => s.togglePanel);

  const { data: corners } = useCorners(activeSessionId);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Ignore if user is typing in an input/textarea/contenteditable
      const target = e.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        // Allow Escape even when typing
        if (e.key !== 'Escape') return;
      }

      switch (e.key) {
        case '1':
          e.preventDefault();
          setActiveView('dashboard');
          break;
        case '2':
          e.preventDefault();
          setActiveView('deep-dive');
          break;
        case '3':
          e.preventDefault();
          setActiveView('progress');
          break;
        case 'Escape':
          e.preventDefault();
          if (sessionDrawerOpen) {
            toggleSessionDrawer();
          } else if (panelOpen) {
            togglePanel();
          }
          break;
        case '/':
          e.preventDefault();
          if (!panelOpen) {
            togglePanel();
          }
          // Focus chat input after panel opens
          setTimeout(() => {
            const chatInput = document.querySelector<HTMLInputElement>(
              '[data-chat-input]',
            );
            chatInput?.focus();
          }, 100);
          break;
        case 'ArrowLeft':
        case 'ArrowRight': {
          if (
            activeView !== 'deep-dive' ||
            deepDiveMode !== 'corner' ||
            !corners ||
            corners.length === 0
          )
            break;
          e.preventDefault();

          // Parse current corner number
          const currentNum = selectedCorner
            ? parseInt(selectedCorner.replace('T', ''), 10)
            : 0;
          const cornerNumbers = corners
            .map((c) => c.number)
            .sort((a, b) => a - b);
          const currentIdx = cornerNumbers.indexOf(currentNum);

          let nextIdx: number;
          if (e.key === 'ArrowRight') {
            nextIdx =
              currentIdx < cornerNumbers.length - 1 ? currentIdx + 1 : 0;
          } else {
            nextIdx =
              currentIdx > 0 ? currentIdx - 1 : cornerNumbers.length - 1;
          }
          selectCorner(`T${cornerNumbers[nextIdx]}`);
          break;
        }
      }
    },
    [
      setActiveView,
      activeView,
      sessionDrawerOpen,
      toggleSessionDrawer,
      panelOpen,
      togglePanel,
      selectedCorner,
      selectCorner,
      deepDiveMode,
      corners,
    ],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
