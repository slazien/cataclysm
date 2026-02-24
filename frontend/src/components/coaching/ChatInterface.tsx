"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { ChatMessage } from "@/lib/types";
import Spinner from "@/components/ui/Spinner";

interface ChatInterfaceProps {
  sessionId: string;
}

export default function ChatInterface({ sessionId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const ws = new WebSocket(
      `${protocol}//${host}/api/coaching/${sessionId}/chat`,
    );

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as ChatMessage;
      setMessages((prev) => [...prev, data]);
      setIsLoading(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    ws.onerror = () => {
      setError("Connection error. Please try again.");
      setIsLoading(false);
      setIsConnected(false);
    };

    wsRef.current = ws;
  }, [sessionId]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, [sessionId]);

  const handleSend = useCallback(() => {
    if (!input.trim() || isLoading) return;

    // Connect on first message
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connect();
      // Queue the message to send after connection
      const ws = wsRef.current;
      if (ws) {
        const msg = input.trim();
        ws.onopen = () => {
          setIsConnected(true);
          setError(null);
          setMessages((prev) => [...prev, { role: "user", content: msg }]);
          setIsLoading(true);
          ws.send(JSON.stringify({ content: msg }));
        };
      }
      setInput("");
      return;
    }

    const msg = input.trim();
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setIsLoading(true);
    setInput("");
    wsRef.current.send(JSON.stringify({ content: msg }));
  }, [input, isLoading, connect]);

  return (
    <div className="flex flex-col rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)]">
      {/* Messages Area */}
      <div className="max-h-80 flex-1 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="text-center text-sm text-[var(--text-muted)]">
            Ask the AI coach about your driving -- specific corners, techniques,
            or anything from the report.
          </p>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`mb-3 flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-[var(--accent-blue)] bg-opacity-20 text-[var(--text-primary)]"
                  : "bg-[var(--bg-secondary)] text-[var(--text-secondary)]"
              }`}
            >
              <pre className="whitespace-pre-wrap font-[inherit]">
                {msg.content}
              </pre>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="mb-3 flex justify-start">
            <div className="flex items-center gap-2 rounded-lg bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-muted)]">
              <Spinner size="sm" />
              Thinking...
            </div>
          </div>
        )}

        {error && (
          <p className="mb-2 text-center text-xs text-[var(--accent-red)]">
            {error}
          </p>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="flex gap-2 border-t border-[var(--border-color)] p-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Ask about a corner, technique, or tip..."
          className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus:border-[var(--accent-blue)]"
          disabled={isLoading}
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          className="rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </div>
  );
}
