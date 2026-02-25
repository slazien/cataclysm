'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Send, Loader2, WifiOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AiInsight } from '@/components/shared/AiInsight';
import { useCoachStore, useSessionStore } from '@/stores';
import { API_BASE } from '@/lib/constants';
import type { ChatMessage } from '@/lib/types';

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

export function ChatInterface() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const chatHistory = useCoachStore((s) => s.chatHistory);
  const contextChips = useCoachStore((s) => s.contextChips);
  const addMessage = useCoachStore((s) => s.addMessage);
  const clearChat = useCoachStore((s) => s.clearChat);
  const panelOpen = useCoachStore((s) => s.panelOpen);
  const pendingQuestion = useCoachStore((s) => s.pendingQuestion);
  const setPendingQuestion = useCoachStore((s) => s.setPendingQuestion);

  const [input, setInput] = useState('');
  const [isWaiting, setIsWaiting] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');

  const wsRef = useRef<WebSocket | null>(null);
  const scrollEndRef = useRef<HTMLDivElement>(null);

  // Keep addMessage in a ref to avoid rebuilding the WebSocket on store changes
  const addMessageRef = useRef(addMessage);
  useEffect(() => { addMessageRef.current = addMessage; });

  // Clear chat history when session changes
  useEffect(() => {
    clearChat();
  }, [activeSessionId, clearChat]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    scrollEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isWaiting]);

  // WebSocket connection lifecycle
  useEffect(() => {
    if (!panelOpen || !activeSessionId) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
        setConnectionState('disconnected');
      }
      return;
    }

    // Derive WebSocket URL from the API base constant
    // Handle empty API_BASE (proxied setup) and https → wss
    const wsBase = API_BASE
      ? API_BASE.replace(/^https/, 'wss').replace(/^http/, 'ws')
      : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
    const url = `${wsBase}/api/coaching/${activeSessionId}/chat`;

    setConnectionState('connecting');
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionState('connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as { role: string; content: string };
        const msg: ChatMessage = {
          role: data.role as 'assistant',
          content: data.content,
        };
        addMessageRef.current(msg);
        setIsWaiting(false);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      setConnectionState('error');
      setIsWaiting(false);
    };

    ws.onclose = () => {
      setConnectionState('disconnected');
      wsRef.current = null;
      setIsWaiting(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [panelOpen, activeSessionId]);

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      // Add user message to history
      addMessage({ role: 'user', content: trimmed });

      // Build context from chips
      const context: Record<string, unknown> = {};
      if (activeSessionId) context.session_id = activeSessionId;
      for (const chip of contextChips) {
        if (chip.label === 'Laps') {
          context.laps = chip.value.split(', ').map(Number);
        } else if (chip.label === 'Corner') {
          context.corner = chip.value.replace('Turn ', 'T');
        } else if (chip.label === 'View') {
          context.view = chip.value.toLowerCase().replaceAll(' ', '-');
        }
      }

      // Send via WebSocket -- backend expects { content: string }
      wsRef.current.send(JSON.stringify({ content: trimmed, context }));
      setIsWaiting(true);
      setInput('');
    },
    [addMessage, activeSessionId, contextChips],
  );

  // Consume pending questions from SuggestedQuestions
  useEffect(() => {
    if (pendingQuestion && connectionState === 'connected' && !isWaiting) {
      sendMessage(pendingQuestion);
      setPendingQuestion(null);
    }
  }, [pendingQuestion, connectionState, isWaiting, sendMessage, setPendingQuestion]);

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

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Connection status indicator */}
      {connectionState === 'error' && (
        <div className="flex items-center gap-1.5 px-4 py-1.5 bg-[var(--grade-f)]/10 text-[var(--grade-f)]">
          <WifiOff className="h-3 w-3" />
          <span className="text-[10px]">Connection lost. Messages may not send.</span>
        </div>
      )}

      {/* Messages area */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="flex flex-col gap-3 px-4 py-3">
          {chatHistory.length === 0 && !isWaiting && (
            <p className="text-xs text-[var(--text-tertiary)] text-center py-8">
              Ask a question about your driving to get started.
            </p>
          )}

          {chatHistory.map((msg, i) => (
            <ChatBubble key={i} message={msg} />
          ))}

          {isWaiting && (
            <div className="flex items-start gap-2">
              <AiInsight mode="compact">
                <span className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
                  <Loader2 className="h-3 w-3 animate-spin" />
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
            disabled={connectionState !== 'connected'}
          />
          <Button
            type="submit"
            size="icon"
            variant="ghost"
            disabled={!input.trim() || isWaiting || connectionState !== 'connected'}
            className="h-8 w-8 shrink-0 text-[var(--cata-accent)] hover:bg-[var(--cata-accent)]/10 disabled:opacity-30"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        {connectionState === 'connecting' && (
          <p className="mt-1 text-[10px] text-[var(--text-tertiary)]">Connecting...</p>
        )}
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
