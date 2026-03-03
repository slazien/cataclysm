'use client';

import ReactMarkdown from 'react-markdown';

/**
 * Block-level markdown renderer for AI coach chat messages.
 * Supports headings, paragraphs, lists, blockquotes, code blocks, etc.
 * Unlike MarkdownText (inline-safe), this outputs proper block elements with spacing.
 */

interface ChatMarkdownProps {
  children: string;
}

export function ChatMarkdown({ children }: ChatMarkdownProps) {
  return (
    <div className="chat-markdown text-xs leading-relaxed">
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          h1: ({ children }) => (
            <h3 className="mb-2 mt-3 first:mt-0 text-sm font-bold">{children}</h3>
          ),
          h2: ({ children }) => (
            <h4 className="mb-2 mt-3 first:mt-0 text-sm font-bold">{children}</h4>
          ),
          h3: ({ children }) => (
            <h5 className="mb-1.5 mt-2.5 first:mt-0 text-xs font-bold">{children}</h5>
          ),
          h4: ({ children }) => (
            <h6 className="mb-1 mt-2 first:mt-0 text-xs font-semibold">{children}</h6>
          ),
          ul: ({ children }) => <ul className="mb-2 ml-4 list-disc last:mb-0">{children}</ul>,
          ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal last:mb-0">{children}</ol>,
          li: ({ children }) => <li className="mb-0.5">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="mb-2 border-l-2 border-[var(--cata-accent)] pl-3 text-[var(--text-secondary)] last:mb-0">
              {children}
            </blockquote>
          ),
          code: ({ children, className }) => {
            const isBlock = className?.includes('language-');
            if (isBlock) {
              return (
                <code className="block mb-2 rounded bg-[var(--bg-elevated)] p-2 text-[11px] font-mono overflow-x-auto last:mb-0">
                  {children}
                </code>
              );
            }
            return (
              <code className="rounded bg-[var(--bg-elevated)] px-1 py-0.5 text-[11px] font-mono">
                {children}
              </code>
            );
          },
          pre: ({ children }) => <pre className="mb-2 last:mb-0">{children}</pre>,
          hr: () => <hr className="my-3 border-[var(--cata-border)]" />,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          a: ({ children, href }) => (
            <a
              href={href}
              className="text-[var(--cata-accent)] underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
