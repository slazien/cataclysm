'use client';

import ReactMarkdown from 'react-markdown';

/**
 * Inline-safe markdown renderer using react-markdown.
 * Overrides <p> to render as a fragment so it can be used inside
 * <span>, <p>, <li>, etc. without creating invalid nested HTML.
 */

interface MarkdownTextProps {
  children: string;
}

export function MarkdownText({ children }: MarkdownTextProps) {
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
