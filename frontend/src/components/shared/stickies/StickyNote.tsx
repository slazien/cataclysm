import React, { useRef, useState } from 'react';
import { motion, useDragControls, type PanInfo } from 'motion/react';
import {
  GripHorizontal,
  Move,
  Palette,
  Pin,
  StickyNote as StickyIcon,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useStickyStore,
  type Sticky,
  type StickyTone,
} from '@/stores/useStickyStore';
import type {
  StickyObstacle,
  StickyViewport,
} from '@/components/shared/stickies/stickyLayout';

interface StickyNoteProps {
  sticky: Sticky;
  viewport: StickyViewport;
  isMobile: boolean;
  /** Returns current scroll offset for page-relative coordinate conversion. */
  getScrollY: () => number;
  resolveObstacles: () => StickyObstacle[];
  onPositionChange: (stickyId: string) => void;
  onContentChange: (stickyId: string, content: string) => void;
  onToneChange: (stickyId: string, tone: StickyTone) => void;
  onCollapsedChange: (stickyId: string, collapsed: boolean) => void;
  onDelete: (stickyId: string) => void;
}

/** Small colored pin for collapsed state. */
const PIN_BG: Record<StickyTone, string> = {
  amber: 'bg-amber-400/80',
  sky: 'bg-sky-400/80',
  mint: 'bg-emerald-400/80',
  rose: 'bg-rose-400/80',
  violet: 'bg-violet-400/80',
  peach: 'bg-orange-400/80',
};

/** Thin accent line at top of expanded card. */
const TONE_ACCENT: Record<StickyTone, string> = {
  amber: 'bg-amber-400',
  sky: 'bg-sky-400',
  mint: 'bg-emerald-400',
  rose: 'bg-rose-400',
  violet: 'bg-violet-400',
  peach: 'bg-orange-400',
};

const TONE_PICKER: Record<StickyTone, string> = {
  amber: 'bg-amber-400',
  sky: 'bg-sky-400',
  mint: 'bg-emerald-400',
  rose: 'bg-rose-400',
  violet: 'bg-violet-400',
  peach: 'bg-orange-400',
};

const TONE_OPTIONS: StickyTone[] = ['amber', 'sky', 'mint', 'rose', 'violet', 'peach'];

export function StickyNote({
  sticky,
  viewport,
  isMobile,
  getScrollY,
  resolveObstacles,
  onPositionChange,
  onContentChange,
  onToneChange,
  onCollapsedChange,
  onDelete,
}: StickyNoteProps) {
  const {
    bringToFront,
    moveSticky,
    setMobileMoveMode,
    setStickyText,
    setStickyTone,
    toggleCollapsed,
  } = useStickyStore();
  const [colorPickerOpen, setColorPickerOpen] = useState(false);
  const dragControls = useDragControls();
  const didDragRef = useRef(false);

  const dragEnabled = isMobile ? sticky.mobileMoveMode : true;

  const startDrag = (event: React.PointerEvent) => {
    if (!dragEnabled) return;
    dragControls.start(event);
    bringToFront(sticky.id);
  };

  const handleDragEnd = (
    _event: MouseEvent | TouchEvent | PointerEvent,
    info: PanInfo,
  ) => {
    didDragRef.current = true;
    const vp = { ...viewport, scrollY: getScrollY() };
    moveSticky(
      sticky.id,
      {
        x: sticky.x + info.offset.x,
        y: sticky.y + info.offset.y,
      },
      vp,
      { avoidObstacles: resolveObstacles() },
    );
    onPositionChange(sticky.id);
    if (isMobile && sticky.mobileMoveMode) {
      setMobileMoveMode(sticky.id, false);
    }
  };

  const handleToggleCollapsed = () => {
    const nextCollapsed = !sticky.collapsed;
    const vp = { ...viewport, scrollY: getScrollY() };
    toggleCollapsed(sticky.id, vp, resolveObstacles());
    bringToFront(sticky.id);
    onCollapsedChange(sticky.id, nextCollapsed);
  };

  const handleToneChange = (tone: StickyTone) => {
    setStickyTone(sticky.id, tone);
    setColorPickerOpen(false);
    onToneChange(sticky.id, tone);
  };

  const handleTextChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = event.target.value;
    setStickyText(sticky.id, text);
    onContentChange(sticky.id, text);
  };

  /* ────────────────────────────────────────────
   * Collapsed: tiny colored pin dot
   * ──────────────────────────────────────────── */
  if (sticky.collapsed) {
    return (
      <motion.div
        className="pointer-events-auto absolute"
        style={{ zIndex: sticky.zIndex }}
        animate={{ x: sticky.x, y: sticky.y, opacity: 1, scale: 1 }}
        initial={{ x: sticky.x, y: sticky.y, opacity: 0, scale: 0.4 }}
        exit={{ opacity: 0, scale: 0.4 }}
        transition={{ type: 'spring', stiffness: 420, damping: 30, mass: 0.6 }}
        drag={dragEnabled}
        dragMomentum={false}
        dragControls={dragControls}
        dragListener={false}
        onDragEnd={handleDragEnd}
        onPointerDown={() => bringToFront(sticky.id)}
      >
        <button
          type="button"
          onPointerDown={(e) => {
            didDragRef.current = false;
            if (!isMobile) startDrag(e);
          }}
          onClick={() => {
            if (!didDragRef.current) handleToggleCollapsed();
          }}
          aria-label={`Open note: ${sticky.text.trim().slice(0, 30) || 'Empty note'}`}
          className={cn(
            'group relative flex items-center justify-center rounded-full',
            'shadow-[0_4px_14px_-3px_rgba(0,0,0,0.4)] backdrop-blur-sm',
            'border border-white/25',
            'transition-transform hover:scale-110 active:scale-95',
            isMobile ? 'h-11 w-11' : 'h-9 w-9',
            PIN_BG[sticky.tone],
          )}
        >
          <StickyIcon className={cn(
            'text-white/90 drop-shadow-sm',
            isMobile ? 'h-5 w-5' : 'h-4 w-4',
          )} />

          {/* Hover preview — desktop only */}
          {!isMobile && sticky.text.trim() && (
            <span className="pointer-events-none absolute left-full ml-2.5 hidden max-w-[200px] truncate whitespace-nowrap rounded-lg bg-black/85 px-2.5 py-1.5 text-[11px] font-medium leading-tight text-white/90 shadow-lg backdrop-blur-sm group-hover:block">
              {sticky.text.trim().slice(0, 60)}
            </span>
          )}
        </button>
      </motion.div>
    );
  }

  /* ────────────────────────────────────────────
   * Expanded: dark glassmorphic card
   * ──────────────────────────────────────────── */
  return (
    <motion.div
      className={cn(
        'pointer-events-auto absolute flex flex-col overflow-hidden rounded-xl',
        'border border-white/[0.08]',
        'bg-[var(--bg-surface)]/70 backdrop-blur-xl',
        'shadow-[0_20px_50px_-16px_rgba(0,0,0,0.55)]',
      )}
      style={{ zIndex: sticky.zIndex, width: sticky.width, minHeight: sticky.height }}
      animate={{ x: sticky.x, y: sticky.y, opacity: 1, scale: 1 }}
      initial={{ x: sticky.x, y: sticky.y, opacity: 0, scale: 0.92 }}
      exit={{ opacity: 0, scale: 0.92 }}
      transition={{ type: 'spring', stiffness: 420, damping: 34, mass: 0.72 }}
      drag={dragEnabled}
      dragMomentum={false}
      dragControls={dragControls}
      dragListener={false}
      onDragEnd={handleDragEnd}
      onPointerDown={() => bringToFront(sticky.id)}
    >
      {/* Tone accent strip */}
      <div className={cn('h-[2px]', TONE_ACCENT[sticky.tone])} />

      {/* Header */}
      <div className="flex items-center justify-between px-1.5 py-1">
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            aria-label="Minimize to pin"
            onClick={handleToggleCollapsed}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-muted)] transition hover:bg-white/10 hover:text-[var(--text-secondary)]"
          >
            <Pin className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            aria-label="Change color"
            onClick={() => setColorPickerOpen((open) => !open)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-muted)] transition hover:bg-white/10 hover:text-[var(--text-secondary)]"
          >
            <Palette className="h-3.5 w-3.5" />
          </button>
          {isMobile && (
            <button
              type="button"
              aria-label="Move note"
              onClick={() => setMobileMoveMode(sticky.id, !sticky.mobileMoveMode)}
              className={cn(
                'flex h-8 items-center gap-1 rounded-lg px-2 text-[11px] font-semibold tracking-wide transition',
                sticky.mobileMoveMode
                  ? 'bg-[var(--cata-accent)] text-black'
                  : 'text-[var(--text-muted)] hover:bg-white/10',
              )}
            >
              <Move className="h-3 w-3" />
              Move
            </button>
          )}
        </div>

        <div className="flex items-center gap-0.5">
          {/* Drag handle — desktop always, mobile only in move mode */}
          {(!isMobile || sticky.mobileMoveMode) && (
            <button
              type="button"
              aria-label="Drag sticky note"
              onPointerDown={startDrag}
              className="flex h-8 w-8 cursor-grab items-center justify-center rounded-lg text-[var(--text-muted)] transition hover:bg-white/10 hover:text-[var(--text-secondary)] active:cursor-grabbing"
            >
              <GripHorizontal className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            type="button"
            aria-label="Delete sticky"
            onClick={() => onDelete(sticky.id)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-muted)] transition hover:bg-red-500/20 hover:text-red-400"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Color picker */}
      {colorPickerOpen && (
        <div className="grid grid-cols-6 gap-2 border-t border-white/[0.06] bg-white/[0.03] px-3 py-2">
          {TONE_OPTIONS.map((tone) => (
            <button
              key={tone}
              type="button"
              aria-label={`Set ${tone} color`}
              onClick={() => handleToneChange(tone)}
              className={cn(
                'h-6 w-6 rounded-full border border-white/20 shadow-sm transition hover:scale-110',
                TONE_PICKER[tone],
                tone === sticky.tone && 'ring-2 ring-white/50',
              )}
            />
          ))}
        </div>
      )}

      {/* Content */}
      <textarea
        value={sticky.text}
        onChange={handleTextChange}
        placeholder="Write a note…"
        className="min-h-[100px] w-full resize-none bg-transparent px-3 py-2 text-sm leading-relaxed text-[var(--text-primary)]/85 placeholder:text-[var(--text-muted)] focus:outline-none"
        onBlur={() => {
          const vp = { ...viewport, scrollY: getScrollY() };
          moveSticky(
            sticky.id,
            { x: sticky.x, y: sticky.y },
            vp,
            { avoidObstacles: resolveObstacles() },
          );
          onPositionChange(sticky.id);
        }}
        onPointerDown={(event) => event.stopPropagation()}
      />

      {/* Mobile move-mode hint */}
      {isMobile && sticky.mobileMoveMode && (
        <div className="border-t border-white/[0.06] bg-white/[0.03] px-3 py-1.5 text-[11px] font-medium text-[var(--text-muted)]">
          Drag anywhere to reposition, then release.
        </div>
      )}
    </motion.div>
  );
}
