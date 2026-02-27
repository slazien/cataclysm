'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AiInsight } from '@/components/shared/AiInsight';
import { useCoachStore, useSessionStore } from '@/stores';
import { useCoachingReport } from '@/hooks/useCoaching';
import type { ChatMessage } from '@/lib/types';

export function ChatInterface() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const chatHistory = useCoachStore((s) => s.chatHistory);
  const contextChips = useCoachStore((s) => s.contextChips);
  const addMessage = useCoachStore((s) => s.addMessage);
  const clearChat = useCoachStore((s) => s.clearChat);
  const pendingQuestion = useCoachStore((s) => s.pendingQuestion);
  const setPendingQuestion = useCoachStore((s) => s.setPendingQuestion);

  const { data: reportData } = useCoachingReport(activeSessionId);
  const reportReady = reportData?.status === 'ready';

  const [input, setInput] = useState('');
  const [isWaiting, setIsWaiting] = useState(false);

  const scrollEndRef = useRef<HTMLDivElement>(null);

  // Clear chat history when session changes
  useEffect(() => {
    clearChat();
  }, [activeSessionId, clearChat]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    scrollEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isWaiting]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !activeSessionId || !reportReady) return;

      // Add user message to history
      addMessage({ role: 'user', content: trimmed });
      setInput('');
      setIsWaiting(true);

      // Build context from chips
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
    [addMessage, activeSessionId, contextChips, reportReady],
  );

  // Consume pending questions from SuggestedQuestions
  useEffect(() => {
    if (pendingQuestion && reportReady && !isWaiting) {
      sendMessage(pendingQuestion);
      setPendingQuestion(null);
    }
  }, [pendingQuestion, reportReady, isWaiting, sendMessage, setPendingQuestion]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  if (!activeSessionId) {
    return (
      <div className="flex flex-1 items-center justify-center px-4">
        <p className="text-xs text-[var(--text-tertiary)] text-center">
          Select a session to start chatting with your AI coach.
        </p>
      </div>
    );
  }

  const inputDisabled = !reportReady || isWaiting;

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Messages area */}
      <ScrollArea className="flex-1 min-h-0">
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
      </ScrollArea>

      {/* Input area */}
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
    </div>
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
