import React, { useMemo, useState } from 'react';
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
  resolveObstacles: () => StickyObstacle[];
  onPositionChange: (stickyId: string) => void;
  onContentChange: (stickyId: string, content: string) => void;
  onToneChange: (stickyId: string, tone: StickyTone) => void;
  onCollapsedChange: (stickyId: string, collapsed: boolean) => void;
  onDelete: (stickyId: string) => void;
}

const TONE_STYLES: Record<StickyTone, string> = {
  amber:
    'bg-[linear-gradient(180deg,rgba(255,251,235,0.97),rgba(254,243,199,0.92))] text-amber-950',
  sky: 'bg-[linear-gradient(180deg,rgba(239,246,255,0.97),rgba(224,242,254,0.92))] text-sky-950',
  mint: 'bg-[linear-gradient(180deg,rgba(236,253,245,0.97),rgba(209,250,229,0.92))] text-emerald-950',
  rose:
    'bg-[linear-gradient(180deg,rgba(255,241,242,0.97),rgba(255,228,230,0.92))] text-rose-950',
  violet:
    'bg-[linear-gradient(180deg,rgba(245,243,255,0.97),rgba(237,233,254,0.92))] text-violet-950',
  peach:
    'bg-[linear-gradient(180deg,rgba(255,247,237,0.97),rgba(255,237,213,0.92))] text-orange-950',
};

const TONE_BUTTON: Record<StickyTone, string> = {
  amber: 'bg-amber-300',
  sky: 'bg-sky-300',
  mint: 'bg-emerald-300',
  rose: 'bg-rose-300',
  violet: 'bg-violet-300',
  peach: 'bg-orange-300',
};

const TONE_OPTIONS: StickyTone[] = ['amber', 'sky', 'mint', 'rose', 'violet', 'peach'];

export function StickyNote({
  sticky,
  viewport,
  isMobile,
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

  const dragEnabled = isMobile ? sticky.mobileMoveMode : true;

  const dragClass = useMemo(() => {
    if (dragEnabled) return 'cursor-grab active:cursor-grabbing';
    return 'cursor-default';
  }, [dragEnabled]);

  const startDrag = (event: React.PointerEvent) => {
    if (!dragEnabled) return;
    dragControls.start(event);
    bringToFront(sticky.id);
  };

  const handleDragEnd = (
    _event: MouseEvent | TouchEvent | PointerEvent,
    info: PanInfo,
  ) => {
    moveSticky(
      sticky.id,
      {
        x: sticky.x + info.offset.x,
        y: sticky.y + info.offset.y,
      },
      viewport,
      {
        avoidObstacles: resolveObstacles(),
      },
    );
    onPositionChange(sticky.id);
    if (isMobile && sticky.mobileMoveMode) {
      setMobileMoveMode(sticky.id, false);
    }
  };

  const handleToggleCollapsed = () => {
    const nextCollapsed = !sticky.collapsed;
    toggleCollapsed(sticky.id, viewport, resolveObstacles());
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

  if (sticky.collapsed) {
    return (
      <motion.div
        className={cn(
          'pointer-events-auto absolute rounded-2xl border border-white/70 shadow-[0_16px_38px_-20px_rgba(15,23,42,0.75)] backdrop-blur-xl',
          TONE_STYLES[sticky.tone],
          dragClass,
        )}
        style={{ zIndex: sticky.zIndex, maxWidth: Math.max(210, sticky.width - 48) }}
        animate={{ x: sticky.x, y: sticky.y, opacity: 1, scale: 1 }}
        initial={{ x: sticky.x, y: sticky.y, opacity: 0, scale: 0.92 }}
        exit={{ opacity: 0, scale: 0.92 }}
        transition={{ type: 'spring', stiffness: 420, damping: 34, mass: 0.7 }}
        drag={dragEnabled}
        dragMomentum={false}
        dragControls={dragControls}
        dragListener={false}
        onDragEnd={handleDragEnd}
        onPointerDown={() => bringToFront(sticky.id)}
      >
        <div className="flex items-center gap-1 p-1.5">
          <button
            type="button"
            onClick={handleToggleCollapsed}
            aria-label="Open sticky note"
            className="flex min-h-11 min-w-0 items-center gap-2 rounded-xl px-3 text-left transition hover:bg-white/55"
          >
            <StickyIcon className="h-4 w-4 shrink-0 text-amber-900/80" />
            <span className="max-w-[132px] truncate text-xs font-semibold">
              {sticky.text.trim() || 'New note'}
            </span>
          </button>
          <button
            type="button"
            aria-label="Drag sticky note"
            className="flex h-9 w-9 items-center justify-center rounded-lg text-amber-900/70 transition hover:bg-white/55"
            onPointerDown={startDrag}
          >
            <GripHorizontal className="h-4 w-4" />
          </button>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      className={cn(
        'pointer-events-auto absolute flex flex-col overflow-hidden rounded-2xl border border-white/70 shadow-[0_25px_50px_-24px_rgba(15,23,42,0.88)] backdrop-blur-xl',
        TONE_STYLES[sticky.tone],
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
      <div
        className={cn(
          'flex min-h-12 items-center justify-between gap-1.5 border-b border-black/10 px-2.5',
          dragClass,
        )}
      >
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            aria-label="Collapse sticky note"
            onClick={handleToggleCollapsed}
            className="flex h-9 w-9 items-center justify-center rounded-lg transition hover:bg-white/60"
          >
            <Pin className="h-4 w-4 text-black/70" />
          </button>
          <button
            type="button"
            aria-label="Change sticky tone"
            onClick={() => setColorPickerOpen((open) => !open)}
            className="flex h-9 w-9 items-center justify-center rounded-lg transition hover:bg-white/60"
          >
            <Palette className="h-4 w-4 text-black/70" />
          </button>
          {isMobile && (
            <button
              type="button"
              aria-label="Move note"
              onClick={() => setMobileMoveMode(sticky.id, !sticky.mobileMoveMode)}
              className={cn(
                'flex h-7 items-center gap-1 rounded-lg px-2 text-[11px] font-semibold tracking-wide transition',
                sticky.mobileMoveMode
                  ? 'bg-black/75 text-white'
                  : 'bg-white/55 text-black/70 hover:bg-white/75',
              )}
            >
              <Move className="h-3.5 w-3.5" />
              Move
            </button>
          )}
        </div>

        <button
          type="button"
          aria-label="Close sticky"
          onClick={() => onDelete(sticky.id)}
          className="flex h-9 w-9 items-center justify-center rounded-lg transition hover:bg-red-500/20"
        >
          <X className="h-4 w-4 text-black/70" />
        </button>
      </div>

      <button
        type="button"
        className={cn(
          'flex h-8 items-center justify-center border-b border-black/10 text-black/50',
          'hover:bg-white/45',
          dragClass,
        )}
        onPointerDown={startDrag}
        aria-label="Drag sticky note"
      >
        <GripHorizontal className="h-4 w-4" />
      </button>

      {colorPickerOpen && (
        <div className="grid grid-cols-6 gap-2 border-b border-black/10 bg-white/45 px-3 py-2">
          {TONE_OPTIONS.map((tone) => (
            <button
              key={tone}
              type="button"
              aria-label={`Set ${tone} tone`}
              onClick={() => handleToneChange(tone)}
              className={cn(
                'h-6 w-6 rounded-full border border-black/20 shadow-sm transition hover:scale-110',
                TONE_BUTTON[tone],
                tone === sticky.tone && 'ring-2 ring-black/45',
              )}
            />
          ))}
        </div>
      )}

      <textarea
        value={sticky.text}
        onChange={handleTextChange}
        placeholder="Write a note…"
        className="min-h-[150px] w-full resize-none bg-transparent px-3 py-2.5 text-sm leading-relaxed text-black/80 placeholder:text-black/45 focus:outline-none"
        onBlur={() => {
          moveSticky(
            sticky.id,
            { x: sticky.x, y: sticky.y },
            viewport,
            { avoidObstacles: resolveObstacles() },
          );
          onPositionChange(sticky.id);
        }}
        onPointerDown={(event) => event.stopPropagation()}
      />

      {isMobile && sticky.mobileMoveMode && (
        <div className="border-t border-black/10 bg-white/45 px-3 py-1.5 text-[11px] font-medium text-black/70">
          Drag using the handle, then release to dock safely.
        </div>
      )}
    </motion.div>
  );
}
