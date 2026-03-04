'use client';

import ReactMarkdown from 'react-markdown';

/**
 * Markdown renderer with two modes:
 * - Inline (default): strips <p> tags so it can nest inside <span>/<li>.
 * - Block: renders proper <p> tags with spacing for multi-paragraph text.
 */

interface MarkdownTextProps {
  children: string;
  /** When true, renders block-level elements (paragraphs with spacing). */
  block?: boolean;
}

export function MarkdownText({ children, block }: MarkdownTextProps) {
  if (block) {
    return (
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="mb-2 list-disc pl-4 last:mb-0">{children}</ul>,
          ol: ({ children }) => <ol className="mb-2 list-decimal pl-4 last:mb-0">{children}</ol>,
          li: ({ children }) => <li className="mb-1">{children}</li>,
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
        p: ({ children }) => <>{children}</>,
      }}
      allowedElements={['p', 'strong', 'em', 'code', 'a', 'del', 'br']}
      unwrapDisallowed
    >
      {children}
    </ReactMarkdown>
  );
}
