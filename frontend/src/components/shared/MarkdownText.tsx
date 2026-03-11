'use client';

import ReactMarkdown from 'react-markdown';
import { type CoachingLinkHandlers, linkifyCoachingRefs } from '@/lib/coachingLinks';

/**
 * Markdown renderer with two modes:
 * - Inline (default): strips <p> tags so it can nest inside <span>/<li>.
 * - Block: renders proper <p> tags with spacing for multi-paragraph text.
 *
 * Optional `linkHandlers` prop enables clickable corner/lap references
 * (T5 → corner navigation, L7 → lap navigation) within rendered text.
 */

interface MarkdownTextProps {
  children: string;
  /** When true, renders block-level elements (paragraphs with spacing). */
  block?: boolean;
  /** When provided, transforms T5/L7 etc. into clickable navigation links. */
  linkHandlers?: CoachingLinkHandlers;
}

/** Recursively walk React children and linkify any string nodes. */
function linkifyChildren(
  children: React.ReactNode,
  handlers: CoachingLinkHandlers,
): React.ReactNode {
  if (typeof children === 'string') {
    return <>{linkifyCoachingRefs(children, handlers)}</>;
  }
  if (Array.isArray(children)) {
    return children.map((child, i) =>
      typeof child === 'string' ? <span key={i}>{linkifyCoachingRefs(child, handlers)}</span> : child,
    );
  }
  return children;
}

export function MarkdownText({ children, block, linkHandlers }: MarkdownTextProps) {
  if (block) {
    return (
      <ReactMarkdown
        components={{
          p: ({ children: c }) => <p className="mb-2 last:mb-0">{linkHandlers ? linkifyChildren(c, linkHandlers) : c}</p>,
          ul: ({ children: c }) => <ul className="mb-2 list-disc pl-4 last:mb-0">{c}</ul>,
          ol: ({ children: c }) => <ol className="mb-2 list-decimal pl-4 last:mb-0">{c}</ol>,
          li: ({ children: c }) => <li className="mb-1">{linkHandlers ? linkifyChildren(c, linkHandlers) : c}</li>,
        }}
        allowedElements={['p', 'strong', 'em', 'code', 'a', 'del', 'br', 'ul', 'ol', 'li']}
        unwrapDisallowed
      >
        {children}
      </ReactMarkdown>
    );
  }

  return (
    <ReactMarkdown
      components={{
        p: ({ children: c }) => <>{linkHandlers ? linkifyChildren(c, linkHandlers) : c}</>,
      }}
      allowedElements={['p', 'strong', 'em', 'code', 'a', 'del', 'br']}
      unwrapDisallowed
    >
      {children}
    </ReactMarkdown>
  );
}
