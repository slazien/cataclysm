'use client';

import { type ReactNode } from 'react';

/**
 * Match corner references: T5, T12, Turn 5, Turn 12
 * Match lap references: L7, L12, Lap 7, Lap 12
 * Combined into one regex for single-pass splitting.
 */
const REF_RE = /\b(?:T(\d+)|Turn\s+(\d+)|L(\d+)|Lap\s+(\d+))\b/g;

export interface CoachingLinkHandlers {
  onCornerClick?: (cornerNum: number) => void;
  onLapClick?: (lapNum: number) => void;
}

/**
 * Transform plain-text corner/lap references into clickable buttons.
 * Returns an array of ReactNode (strings + button elements).
 *
 * Usage: pass into a container that accepts ReactNode children,
 * e.g. `<p>{linkifyCoachingRefs(text, handlers)}</p>`.
 */
export function linkifyCoachingRefs(
  text: string,
  handlers: CoachingLinkHandlers,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;

  for (const match of text.matchAll(REF_RE)) {
    const fullMatch = match[0];
    const matchIndex = match.index!;

    // Push text before the match
    if (matchIndex > lastIndex) {
      nodes.push(text.slice(lastIndex, matchIndex));
    }

    // Determine if this is a corner or lap reference
    const cornerNum = match[1] ?? match[2]; // T(\d+) or Turn\s+(\d+)
    const lapNum = match[3] ?? match[4]; // L(\d+) or Lap\s+(\d+)

    if (cornerNum && handlers.onCornerClick) {
      const num = parseInt(cornerNum, 10);
      nodes.push(
        <button
          key={`ref-${key++}`}
          type="button"
          onClick={(e) => { e.stopPropagation(); handlers.onCornerClick!(num); }}
          className="inline cursor-pointer text-[var(--cata-accent)] underline decoration-dotted underline-offset-2 transition-colors hover:text-[var(--cata-accent)]/80"
        >
          {fullMatch}
        </button>,
      );
    } else if (lapNum && handlers.onLapClick) {
      const num = parseInt(lapNum, 10);
      nodes.push(
        <button
          key={`ref-${key++}`}
          type="button"
          onClick={(e) => { e.stopPropagation(); handlers.onLapClick!(num); }}
          className="inline cursor-pointer text-[var(--cata-accent)] underline decoration-dotted underline-offset-2 transition-colors hover:text-[var(--cata-accent)]/80"
        >
          {fullMatch}
        </button>,
      );
    } else {
      // No handler for this type — keep as plain text
      nodes.push(fullMatch);
    }

    lastIndex = matchIndex + fullMatch.length;
  }

  // Push remaining text
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length > 0 ? nodes : [text];
}
