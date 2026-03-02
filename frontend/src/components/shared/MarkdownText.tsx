'use client';

/**
 * Lightweight inline markdown renderer.
 * Converts **bold**, *italic*, and `code` to React elements
 * without adding any wrapper elements — safe inside <span>, <p>, <li>.
 */

const INLINE_MD_RE = /(\*\*.*?\*\*|\*.*?\*|`[^`]+`)/g;

interface MarkdownTextProps {
  children: string;
}

export function MarkdownText({ children }: MarkdownTextProps) {
  const segments = children.split(INLINE_MD_RE);

  // Fast path: no markdown found
  if (segments.length === 1) return <>{children}</>;

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.startsWith('**') && seg.endsWith('**') && seg.length > 4) {
          return <strong key={i}>{seg.slice(2, -2)}</strong>;
        }
        if (seg.startsWith('*') && seg.endsWith('*') && seg.length > 2) {
          return <em key={i}>{seg.slice(1, -1)}</em>;
        }
        if (seg.startsWith('`') && seg.endsWith('`') && seg.length > 2) {
          return (
            <code
              key={i}
              className="rounded bg-[var(--bg-elevated)] px-1 py-0.5 text-[0.9em]"
            >
              {seg.slice(1, -1)}
            </code>
          );
        }
        return seg;
      })}
    </>
  );
}
