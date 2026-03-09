'use client';

import { motion } from 'motion/react';
import { FileText, Search, TrendingUp, Timer } from 'lucide-react';
import { useUiStore, useSessionStore } from '@/stores';
import { cn } from '@/lib/utils';

type ActiveView = 'session-report' | 'deep-dive' | 'progress' | 'debrief';

const NAV_ITEMS: { icon: typeof FileText; label: string; view: ActiveView }[] = [
  { icon: FileText, label: 'Report', view: 'session-report' },
  { icon: Search, label: 'Dive', view: 'deep-dive' },
  { icon: TrendingUp, label: 'Progress', view: 'progress' },
  { icon: Timer, label: 'Debrief', view: 'debrief' },
];

export function MobileBottomTabs() {
  const activeView = useUiStore((s) => s.activeView);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const setUploadPromptOpen = useUiStore((s) => s.setUploadPromptOpen);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);

  return (
    <div id="tab-bar-mobile" role="tablist" className="safe-area-bottom flex h-14 shrink-0 items-stretch border-t border-[var(--cata-border)] bg-[var(--bg-surface)] lg:hidden">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = activeView === item.view;
        return (
          <motion.button
            key={item.view}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-label={item.label}
            onClick={() => {
              if (!activeSessionId) {
                setUploadPromptOpen(true);
                return;
              }
              setActiveView(item.view);
            }}
            whileTap={{ scale: 0.95 }}
            transition={{ duration: 0.1 }}
            className={cn(
              'flex flex-1 flex-col items-center justify-center gap-0.5 transition-colors',
              isActive
                ? 'text-[var(--cata-accent)]'
                : 'text-[var(--text-secondary)] active:text-[var(--text-secondary)]',
            )}
          >
            <Icon className="h-5 w-5" />
            <span className="font-[family-name:var(--font-display)] text-[11px] font-medium">{item.label}</span>
          </motion.button>
        );
      })}
    </div>
  );
}
