'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type SpeechState = 'idle' | 'speaking' | 'paused';

interface UseSpeechSynthesisReturn {
  state: SpeechState;
  isSupported: boolean;
  speak: (text: string) => void;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  toggle: (text: string) => void;
}

export function useSpeechSynthesis(): UseSpeechSynthesisReturn {
  const [state, setState] = useState<SpeechState>('idle');
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;

  const stop = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    utteranceRef.current = null;
    setState('idle');
  }, [isSupported]);

  const speak = useCallback(
    (text: string) => {
      if (!isSupported) return;
      // Cancel any ongoing speech first
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      utterance.onend = () => setState('idle');
      utterance.onerror = () => setState('idle');

      utteranceRef.current = utterance;
      setState('speaking');
      window.speechSynthesis.speak(utterance);
    },
    [isSupported],
  );

  const pause = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.pause();
    setState('paused');
  }, [isSupported]);

  const resume = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.resume();
    setState('speaking');
  }, [isSupported]);

  const toggle = useCallback(
    (text: string) => {
      if (state === 'speaking') {
        pause();
      } else if (state === 'paused') {
        resume();
      } else {
        speak(text);
      }
    },
    [state, speak, pause, resume],
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (isSupported) {
        window.speechSynthesis.cancel();
      }
    };
  }, [isSupported]);

  return { state, isSupported, speak, pause, resume, stop, toggle };
}
