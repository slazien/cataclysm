'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CornerPreviewMap } from './CornerPreviewMap';

interface CornerRefLinkProps {
  cornerNum: number;
  label: string;
  onNavigate: (cornerNum: number) => void;
}

/** Detect touch-primary device (no hover support). */
function useIsTouch(): boolean {
  const [isTouch, setIsTouch] = useState(false);
  useEffect(() => {
    setIsTouch(window.matchMedia('(hover: none)').matches);
  }, []);
  return isTouch;
}

export function CornerRefLink({ cornerNum, label, onNavigate }: CornerRefLinkProps) {
  const [open, setOpen] = useState(false);
  const isTouch = useIsTouch();
  const enterTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const leaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimers = useCallback(() => {
    if (enterTimer.current) { clearTimeout(enterTimer.current); enterTimer.current = null; }
    if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
  }, []);

  // Cleanup on unmount
  useEffect(() => clearTimers, [clearTimers]);

  const handleMouseEnter = useCallback(() => {
    if (isTouch) return;
    clearTimers();
    enterTimer.current = setTimeout(() => setOpen(true), 300);
  }, [isTouch, clearTimers]);

  const handleMouseLeave = useCallback(() => {
    if (isTouch) return;
    clearTimers();
    leaveTimer.current = setTimeout(() => setOpen(false), 200);
  }, [isTouch, clearTimers]);

  const handleContentEnter = useCallback(() => {
    if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
  }, []);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (isTouch) {
        // Mobile: toggle popover, don't navigate
        setOpen((v) => !v);
      } else {
        // Desktop: navigate immediately
        clearTimers();
        setOpen(false);
        onNavigate(cornerNum);
      }
    },
    [isTouch, cornerNum, onNavigate, clearTimers],
  );

  const handleGoToCorner = useCallback(() => {
    setOpen(false);
    onNavigate(cornerNum);
  }, [cornerNum, onNavigate]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          onClick={handleClick}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          className="inline cursor-pointer text-[var(--cata-accent)] underline decoration-dotted underline-offset-2 transition-colors hover:text-[var(--cata-accent)]/80"
        >
          {label}
        </button>
      </PopoverTrigger>

      <PopoverContent
        side="top"
        sideOffset={8}
        align="center"
        onMouseEnter={handleContentEnter}
        onMouseLeave={handleMouseLeave}
        className="w-auto border-[var(--cata-border)] bg-[var(--bg-surface)] p-0 shadow-xl"
      >
        {/* Only render map when popover is open (saves WebGL contexts) */}
        {open && (
          <div className="flex flex-col">
            <CornerPreviewMap
              cornerNum={cornerNum}
              width={isTouch ? 280 : 320}
              height={isTouch ? 180 : 220}
            />

            {/* Legend + action row */}
            <div className="flex items-center justify-between border-t border-[var(--cata-border)] px-3 py-2">
              <div className="flex items-center gap-3 text-[10px] text-[var(--text-secondary)]">
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-[#ef4444]" />
                  Slow
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-[#22c55e]" />
                  Fast
                </span>
              </div>

              <button
                type="button"
                onClick={handleGoToCorner}
                className="min-h-[36px] rounded-md bg-[var(--cata-accent)] px-3 py-1 text-xs font-semibold text-black transition-colors hover:bg-[var(--cata-accent)]/80"
              >
                T{cornerNum} Corner Focus
              </button>
            </div>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
