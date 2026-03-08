'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { NoteColor, NoteAnchorType } from '@/lib/types';
import { useCreateNote } from '@/hooks/useNotes';

const COLOR_DOT: Record<NoteColor, string> = {
  yellow: 'bg-yellow-400',
  blue: 'bg-blue-400',
  green: 'bg-green-400',
  pink: 'bg-pink-400',
  purple: 'bg-purple-400',
};

const COLORS: NoteColor[] = ['yellow', 'blue', 'green', 'pink', 'purple'];

interface MentionSuggestion {
  label: string;
  value: string;
}

interface NoteEditorProps {
  sessionId: string | null;
  /** Pre-fill anchor for contextual note creation (e.g., from corner grades) */
  anchorType?: NoteAnchorType;
  anchorId?: string;
  /** Available corners/laps for @-mention autocomplete */
  corners?: string[];
  laps?: number[];
  onCreated?: () => void;
}

export function NoteEditor({
  sessionId,
  anchorType,
  anchorId,
  corners = [],
  laps = [],
  onCreated,
}: NoteEditorProps) {
  const [content, setContent] = useState('');
  const [color, setColor] = useState<NoteColor>('yellow');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState<MentionSuggestion[]>([]);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [mentionStart, setMentionStart] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const createNote = useCreateNote();

  const allSuggestions: MentionSuggestion[] = [
    ...corners.map((c) => ({ label: c, value: c })),
    ...laps.map((l) => ({ label: `L${l}`, value: `L${l}` })),
    { label: 'braking', value: 'braking' },
    { label: 'apex_speed', value: 'apex_speed' },
    { label: 'consistency', value: 'consistency' },
    { label: 'coaching', value: 'coaching' },
  ];

  const handleChange = useCallback(
    (value: string) => {
      setContent(value);

      // Check for @ trigger
      const textarea = textareaRef.current;
      if (!textarea) return;
      const cursorPos = textarea.selectionStart;
      const textBefore = value.slice(0, cursorPos);
      const atIndex = textBefore.lastIndexOf('@');

      if (atIndex >= 0 && (atIndex === 0 || textBefore[atIndex - 1] === ' ')) {
        const query = textBefore.slice(atIndex + 1).toLowerCase();
        const filtered = allSuggestions.filter((s) =>
          s.label.toLowerCase().startsWith(query),
        );
        if (filtered.length > 0) {
          setSuggestions(filtered);
          setShowSuggestions(true);
          setSelectedSuggestion(0);
          setMentionStart(atIndex);
          return;
        }
      }
      setShowSuggestions(false);
    },
    [allSuggestions],
  );

  const insertMention = useCallback(
    (mention: MentionSuggestion) => {
      if (mentionStart === null) return;
      const before = content.slice(0, mentionStart);
      const textarea = textareaRef.current;
      const cursorPos = textarea?.selectionStart ?? content.length;
      const after = content.slice(cursorPos);
      const newContent = `${before}@${mention.value} ${after}`;
      setContent(newContent);
      setShowSuggestions(false);
      setMentionStart(null);
      // Restore cursor position
      setTimeout(() => {
        if (textarea) {
          const newPos = before.length + mention.value.length + 2; // @mention + space
          textarea.selectionStart = newPos;
          textarea.selectionEnd = newPos;
          textarea.focus();
        }
      }, 0);
    },
    [content, mentionStart],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSuggestions) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedSuggestion((prev) =>
          Math.min(prev + 1, suggestions.length - 1),
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedSuggestion((prev) => Math.max(prev - 1, 0));
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(suggestions[selectedSuggestion]);
      } else if (e.key === 'Escape') {
        setShowSuggestions(false);
      }
    } else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    const trimmed = content.trim();
    if (!trimmed) return;
    createNote.mutate(
      {
        content: trimmed,
        session_id: sessionId,
        color,
        anchor_type: anchorType,
        anchor_id: anchorId,
      },
      {
        onSuccess: () => {
          setContent('');
          onCreated?.();
        },
      },
    );
  };

  return (
    <div className="relative rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-3">
      {/* Color picker */}
      <div className="mb-2 flex items-center gap-1">
        {COLORS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setColor(c)}
            className={cn(
              'h-4 w-4 rounded-full transition-transform hover:scale-125',
              COLOR_DOT[c],
              c === color && 'ring-2 ring-white/50 ring-offset-1 ring-offset-[var(--bg-surface)]',
            )}
            title={c}
          />
        ))}
        {anchorType && anchorId && (
          <span className="ml-2 text-[10px] text-[var(--text-muted)]">
            Anchored to {anchorType}: {anchorId}
          </span>
        )}
      </div>

      {/* Textarea with @-mention */}
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Write a note... (@ to reference corners, laps, metrics)"
          className="w-full resize-none rounded bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
          rows={3}
          maxLength={10000}
        />

        {/* @-mention suggestions dropdown */}
        {showSuggestions && (
          <div className="absolute bottom-full left-0 z-50 mb-1 w-48 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] py-1 shadow-lg">
            {suggestions.map((s, i) => (
              <button
                key={s.value}
                type="button"
                className={cn(
                  'w-full px-3 py-1.5 text-left text-sm transition-colors',
                  i === selectedSuggestion
                    ? 'bg-[var(--cata-accent)]/20 text-[var(--cata-accent)]'
                    : 'text-[var(--text-primary)] hover:bg-white/5',
                )}
                onMouseDown={(e) => {
                  e.preventDefault();
                  insertMention(s);
                }}
              >
                @{s.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Submit button */}
      <div className="mt-2 flex justify-end">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!content.trim() || createNote.isPending}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            'bg-[var(--cata-accent)] text-white hover:bg-[var(--cata-accent)]/80',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          <Plus className="h-3.5 w-3.5" />
          {createNote.isPending ? 'Saving...' : 'Add Note'}
        </button>
      </div>
    </div>
  );
}
