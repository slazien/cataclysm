'use client';

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useSessionStore, useUiStore, useAnalysisStore } from '@/stores';
import { ViewErrorBoundary } from '@/components/shared/ViewErrorBoundary';
import { WelcomeScreen } from '@/components/shared/WelcomeScreen';
import { SessionDashboard } from '@/components/dashboard/SessionDashboard';
import { SessionReport } from '@/components/session-report';
import { DeepDive } from '@/components/deep-dive/DeepDive';
import { ProgressView } from '@/components/progress/ProgressView';
import { PitLaneDebrief } from '@/components/debrief/PitLaneDebrief';

function ViewContent({ activeView, activeSessionId }: { activeView: string; activeSessionId: string }) {
  switch (activeView) {
    case 'session-report':
      return (
        <ViewErrorBoundary key={activeSessionId}>
          <SessionReport />
        </ViewErrorBoundary>
      );
    case 'deep-dive':
      return (
        <ViewErrorBoundary key={activeSessionId}>
          <DeepDive />
        </ViewErrorBoundary>
      );
    case 'progress':
      return (
        <ViewErrorBoundary key={activeSessionId}>
          <ProgressView />
        </ViewErrorBoundary>
      );
    case 'debrief':
      return (
        <ViewErrorBoundary key={activeSessionId}>
          <PitLaneDebrief />
        </ViewErrorBoundary>
      );
    default:
      return (
        <ViewErrorBoundary key={activeSessionId}>
          <SessionDashboard />
        </ViewErrorBoundary>
      );
  }
}

export function ViewRouter() {
  const activeView = useUiStore((s) => s.activeView);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const resetAnalysis = useAnalysisStore((s) => s.reset);
  const prevSessionId = useRef(activeSessionId);

  // Reset analysis state when switching sessions to prevent stale data crashes
  useEffect(() => {
    if (prevSessionId.current !== null && activeSessionId !== prevSessionId.current) {
      resetAnalysis();
    }
    prevSessionId.current = activeSessionId;
  }, [activeSessionId, resetAnalysis]);

  if (!activeSessionId) {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto">
        <WelcomeScreen />
      </div>
    );
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={activeView}
        className="min-h-0 flex-1 overflow-y-auto"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
      >
        <ViewContent activeView={activeView} activeSessionId={activeSessionId} />
      </motion.div>
    </AnimatePresence>
  );
}
