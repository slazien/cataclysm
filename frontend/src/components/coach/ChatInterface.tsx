'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { AiInsight } from '@/components/shared/AiInsight';
import { useCoachStore, useSessionStore } from '@/stores';
import { useCoachingReport } from '@/hooks/useCoaching';
import type { ChatMessage } from '@/lib/types';

/**
 * Shared hook for sending chat messages.
 * Uses Zustand store for isWaiting so both ChatMessages and ChatInput stay in sync.
 */
function useChatSend() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const addMessage = useCoachStore((s) => s.addMessage);
  const contextChips = useCoachStore((s) => s.contextChips);
  const isWaiting = useCoachStore((s) => s.isWaiting);
  const setIsWaiting = useCoachStore((s) => s.setIsWaiting);
  const { data: reportData } = useCoachingReport(activeSessionId);
  const reportReady = reportData?.status === 'ready';

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !activeSessionId || !reportReady) return;

      addMessage({ role: 'user', content: trimmed });
      setIsWaiting(true);

      const context: Record<string, unknown> = {};
      context.session_id = activeSessionId;
      for (const chip of contextChips) {
        if (chip.label === 'Laps') {
          context.laps = chip.value.split(', ').map(Number);
        } else if (chip.label === 'Corner') {
          context.corner = chip.value.replace('Turn ', 'T');
        } else if (chip.label === 'View') {
          context.view = chip.value.toLowerCase().replaceAll(' ', '-');
        }
      }

      try {
        const resp = await fetch(`/api/coaching/${activeSessionId}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: trimmed, context }),
        });

        if (!resp.ok) {
          const errText = await resp.text();
          addMessage({
            role: 'assistant',
            content: `Sorry, something went wrong. ${resp.status === 401 ? 'Please sign in.' : errText}`,
          });
          return;
        }

        const data = (await resp.json()) as { role: string; content: string };
        const msg: ChatMessage = {
          role: data.role as 'assistant',
          content: data.content,
        };
        addMessage(msg);
      } catch {
        addMessage({
          role: 'assistant',
          content: 'Failed to reach the AI coach. Please try again.',
        });
      } finally {
        setIsWaiting(false);
      }
    },
    [addMessage, activeSessionId, contextChips, reportReady, setIsWaiting],
  );

  return { sendMessage, isWaiting, reportReady, activeSessionId };
}

/**
 * Chat messages area — renders inside the scrollable report area.
 */
export function ChatMessages() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const chatHistory = useCoachStore((s) => s.chatHistory);
  const clearChat = useCoachStore((s) => s.clearChat);
  const isWaiting = useCoachStore((s) => s.isWaiting);
  const pendingQuestion = useCoachStore((s) => s.pendingQuestion);
  const setPendingQuestion = useCoachStore((s) => s.setPendingQuestion);
  const { data: reportData } = useCoachingReport(activeSessionId);
  const reportReady = reportData?.status === 'ready';

  const { sendMessage } = useChatSend();
  const scrollEndRef = useRef<HTMLDivElement>(null);

  // Clear chat history when session changes
  useEffect(() => {
    clearChat();
  }, [activeSessionId, clearChat]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    scrollEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isWaiting]);

  // Consume pending questions from SuggestedQuestions
  useEffect(() => {
    if (pendingQuestion && reportReady && !isWaiting) {
      sendMessage(pendingQuestion);
      setPendingQuestion(null);
    }
  }, [pendingQuestion, reportReady, isWaiting, sendMessage, setPendingQuestion]);

  if (!activeSessionId) return null;

  return (
    <div className="flex flex-col gap-3 px-4 py-3">
      {chatHistory.length === 0 && !isWaiting && (
        <p className="text-xs text-[var(--text-tertiary)] text-center py-8">
          {reportReady
            ? 'Ask a question about your driving to get started.'
            : 'Chat will be available once the coaching report is ready.'}
        </p>
      )}

      {chatHistory.map((msg, i) => (
        <ChatBubble key={i} message={msg} />
      ))}

      {isWaiting && (
        <div className="flex items-start gap-2">
          <AiInsight mode="compact">
            <span className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
              <CircularProgress size={12} strokeWidth={1.5} />
              Thinking...
            </span>
          </AiInsight>
        </div>
      )}

      <div ref={scrollEndRef} />
    </div>
  );
}

/**
 * Chat input form — rendered outside the scroll area, always pinned at bottom.
 */
export function ChatInput() {
  const [input, setInput] = useState('');
  const { sendMessage, isWaiting, reportReady, activeSessionId } = useChatSend();

  if (!activeSessionId) return null;

  const inputDisabled = !reportReady || isWaiting;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      sendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim()) {
        sendMessage(input);
        setInput('');
      }
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="shrink-0 border-t border-[var(--cata-border)] px-3 py-2"
    >
      <div className="flex items-end gap-2">
        <textarea
          data-chat-input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your driving..."
          rows={1}
          className="flex-1 resize-none rounded-lg border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-3 py-2 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--cata-accent)] focus:outline-none"
          disabled={inputDisabled}
        />
        <Button
          type="submit"
          size="icon"
          variant="ghost"
          disabled={!input.trim() || isWaiting || !reportReady}
          className="h-8 w-8 shrink-0 text-[var(--cata-accent)] hover:bg-[var(--cata-accent)]/10 disabled:opacity-30"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-[var(--bg-elevated)] px-3 py-2 text-xs text-[var(--text-primary)] leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[95%]">
        <AiInsight>
          <span className="text-xs leading-relaxed whitespace-pre-wrap">{message.content}</span>
        </AiInsight>
      </div>
    </div>
  );
}
