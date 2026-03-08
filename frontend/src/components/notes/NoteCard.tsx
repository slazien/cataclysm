'use client';

import { useState, useRef, useEffect, useCallback, Fragment } from 'react';
import { Pin, Trash2, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Note, NoteColor, NoteUpdate } from '@/lib/types';
import { useAutoSaveNote, useDeleteNote, useUpdateNote } from '@/hooks/useNotes';
import { useUiStore, useAnalysisStore, useNotesStore } from '@/stores';

const COLOR_CLASSES: Record<NoteColor, string> = {
  yellow: 'bg-yellow-500/10 border-yellow-500/30',
  blue: 'bg-blue-500/10 border-blue-500/30',
  green: 'bg-green-500/10 border-green-500/30',
  pink: 'bg-pink-500/10 border-pink-500/30',
  purple: 'bg-purple-500/10 border-purple-500/30',
};

const COLOR_DOT: Record<NoteColor, string> = {
  yellow: 'bg-yellow-400',
  blue: 'bg-blue-400',
  green: 'bg-green-400',
  pink: 'bg-pink-400',
  purple: 'bg-purple-400',
};

const COLORS: NoteColor[] = ['yellow', 'blue', 'green', 'pink', 'purple'];

/** Parse @-references and render as clickable navigation chips. */
function renderContent(
  content: string,
  onNavigate: (ref: string, type: string) => void,
) {
  const regex = /@(T\d{1,2}|L\d{1,2}|braking|apex_speed|consistency|coaching)/g;
  const parts: (string | { ref: string; type: string })[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index));
    }
    const ref = match[1];
    const type = ref.startsWith('T')
      ? 'corner'
      : ref.startsWith('L')
        ? 'lap'
        : 'metric';
    parts.push({ ref, type });
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex));
  }

  return parts.map((part, i) => {
    if (typeof part === 'string') {
      return <Fragment key={i}>{part}</Fragment>;
    }
    return (
      <button
        key={i}
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onNavigate(part.ref, part.type);
        }}
        className="inline-flex items-center rounded bg-[var(--cata-accent)]/20 px-1 py-0.5 text-xs font-medium text-[var(--cata-accent)] transition-colors hover:bg-[var(--cata-accent)]/40 cursor-pointer"
        title={`Go to ${part.ref}`}
      >
        @{part.ref}
      </button>
    );
  });
}

interface NoteCardProps {
  note: Note;
}

export function NoteCard({ note }: NoteCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [content, setContent] = useState(note.content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { saveStatus, debouncedSave, flush } = useAutoSaveNote(
    note.id,
    note.session_id,
  );
  const deleteMutation = useDeleteNote();
  const updateMutation = useUpdateNote();
  const color = (note.color ?? 'yellow') as NoteColor;

  const setActiveView = useUiStore((s) => s.setActiveView);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const selectLaps = useAnalysisStore((s) => s.selectLaps);
  const setMode = useAnalysisStore((s) => s.setMode);
  const toggleNotesPanel = useNotesStore((s) => s.togglePanel);

  /** Navigate to the referenced corner, lap, or metric view. */
  const handleNavigate = useCallback(
    (ref: string, type: string) => {
      // Close the notes drawer so user sees the destination
      toggleNotesPanel();
      if (type === 'corner') {
        setActiveView('deep-dive');
        setMode('corner');
        selectCorner(ref);
      } else if (type === 'lap') {
        const lapNum = parseInt(ref.replace('L', ''), 10);
        setActiveView('deep-dive');
        setMode('speed');
        selectLaps([lapNum]);
      } else {
        // Metrics like @braking, @consistency → go to report
        setActiveView('session-report');
      }
    },
    [setActiveView, selectCorner, selectLaps, setMode, toggleNotesPanel],
  );

  // Sync content from server when not editing (e.g., after refetch)
  useEffect(() => {
    if (!isEditing) setContent(note.content);
  }, [note.content, isEditing]);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.selectionStart = textareaRef.current.value.length;
    }
  }, [isEditing]);

  const handleContentChange = (value: string) => {
    setContent(value);
    debouncedSave({ content: value });
  };

  const handleFinishEdit = () => {
    flush();
    setIsEditing(false);
  };

  const handleTogglePin = () => {
    updateMutation.mutate({
      noteId: note.id,
      body: { is_pinned: !note.is_pinned },
      sessionId: note.session_id,
    });
  };

  const handleDelete = () => {
    deleteMutation.mutate({
      noteId: note.id,
      sessionId: note.session_id,
    });
  };

  const handleColorChange = (c: NoteColor) => {
    updateMutation.mutate({
      noteId: note.id,
      body: { color: c },
      sessionId: note.session_id,
    });
  };

  return (
    <div
      className={cn(
        'group relative rounded-lg border p-3 transition-colors',
        COLOR_CLASSES[color],
      )}
    >
      {/* Top bar: pin, color dots, delete */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleTogglePin}
            className={cn(
              'rounded p-1 transition-colors hover:bg-white/10',
              note.is_pinned
                ? 'text-[var(--cata-accent)]'
                : 'text-[var(--text-muted)] opacity-0 group-hover:opacity-100',
            )}
            title={note.is_pinned ? 'Unpin' : 'Pin'}
          >
            <Pin className="h-3.5 w-3.5" />
          </button>
          {/* Color dots */}
          <div className="flex gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
            {COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => handleColorChange(c)}
                className={cn(
                  'h-3 w-3 rounded-full transition-transform hover:scale-125',
                  COLOR_DOT[c],
                  c === color && 'ring-1 ring-white/50',
                )}
                title={c}
              />
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1">
          {/* Save status */}
          {isEditing && (
            <span className="text-[10px] text-[var(--text-muted)]">
              {saveStatus === 'saving'
                ? 'Saving...'
                : saveStatus === 'saved'
                  ? 'Saved'
                  : 'Unsaved'}
            </span>
          )}
          {isEditing && (
            <button
              type="button"
              onClick={handleFinishEdit}
              className="rounded p-1 text-green-400 transition-colors hover:bg-white/10"
              title="Done editing"
            >
              <Check className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            type="button"
            onClick={handleDelete}
            className="rounded p-1 text-[var(--text-muted)] opacity-0 transition-all hover:text-red-400 group-hover:opacity-100"
            title="Delete"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Anchor badge */}
      {note.anchor_type && note.anchor_id && (
        <div className="mb-1.5">
          <span className="inline-flex items-center rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
            {note.anchor_type === 'corner' ? `Turn ${note.anchor_id.replace('T', '')}` : note.anchor_id}
          </span>
        </div>
      )}

      {/* Content */}
      {isEditing ? (
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => handleContentChange(e.target.value)}
          onBlur={handleFinishEdit}
          className="w-full resize-none rounded bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
          rows={3}
          maxLength={10000}
        />
      ) : (
        <div
          className="cursor-text whitespace-pre-wrap text-sm text-[var(--text-primary)]"
          onClick={() => setIsEditing(true)}
        >
          {renderContent(content, handleNavigate)}
        </div>
      )}

      {/* Timestamp */}
      <div className="mt-2 text-[10px] text-[var(--text-muted)]">
        {new Date(note.updated_at).toLocaleDateString(undefined, {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        })}
      </div>
    </div>
  );
}
