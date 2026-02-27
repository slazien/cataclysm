'use client';

import { LayoutDashboard, Search, TrendingUp, Bot, Timer } from 'lucide-react';
import { useUiStore, useCoachStore } from '@/stores';
import { cn } from '@/lib/utils';

type ActiveView = 'dashboard' | 'deep-dive' | 'progress' | 'debrief';

const NAV_ITEMS: { icon: typeof LayoutDashboard; label: string; view: ActiveView }[] = [
  { icon: LayoutDashboard, label: 'Dashboard', view: 'dashboard' },
  { icon: Search, label: 'Dive', view: 'deep-dive' },
  { icon: TrendingUp, label: 'Progress', view: 'progress' },
  { icon: Timer, label: 'Debrief', view: 'debrief' },
];

export function MobileBottomTabs() {
  const activeView = useUiStore((s) => s.activeView);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const panelOpen = useCoachStore((s) => s.panelOpen);
  const togglePanel = useCoachStore((s) => s.togglePanel);

  return (
    <div className="flex h-14 shrink-0 items-center border-t border-[var(--cata-border)] bg-[var(--bg-surface)] lg:hidden">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = activeView === item.view;
        return (
          <button
            key={item.view}
            type="button"
            onClick={() => setActiveView(item.view)}
            className={cn(
              'flex flex-1 flex-col items-center justify-center gap-0.5 transition-colors',
              isActive
                ? 'text-[var(--cata-accent)]'
                : 'text-[var(--text-muted)] active:text-[var(--text-secondary)]',
            )}
          >
            <Icon className="h-5 w-5" />
            <span className="text-[10px] font-medium">{item.label}</span>
          </button>
        );
      })}
      <button
        type="button"
        onClick={togglePanel}
        className={cn(
          'flex flex-1 flex-col items-center justify-center gap-0.5 transition-colors',
          panelOpen
            ? 'text-[var(--cata-accent)]'
            : 'text-[var(--text-muted)] active:text-[var(--text-secondary)]',
        )}
      >
        <Bot className="h-5 w-5" />
        <span className="text-[10px] font-medium">Coach</span>
      </button>
    </div>
  );
}
