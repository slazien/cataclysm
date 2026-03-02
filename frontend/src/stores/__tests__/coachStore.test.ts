import { describe, it, expect, beforeEach } from 'vitest';
import { useCoachStore } from '../coachStore';
import type { CoachingReport, ChatMessage } from '@/lib/types';

// Minimal fixtures
const REPORT: CoachingReport = {
  session_id: 'sess-001',
  status: 'ready',
  summary: 'Smooth lap overall.',
  priority_corners: [
    { corner: 5, time_cost_s: 0.3, issue: 'late apex', tip: 'hit earlier apex' },
  ],
  corner_grades: [
    {
      corner: 5,
      braking: 'A',
      trail_braking: 'B',
      min_speed: 'C',
      throttle: 'B',
      notes: 'good effort',
    },
  ],
  patterns: ['Consistent trail braking'],
  drills: ['Focus on turn-in point'],
};

const USER_MSG: ChatMessage = { role: 'user', content: 'How do I improve T5?' };
const ASSISTANT_MSG: ChatMessage = { role: 'assistant', content: 'Hit the apex earlier.' };

describe('coachStore', () => {
  beforeEach(() => {
    useCoachStore.setState({
      panelOpen: false,
      report: null,
      chatHistory: [],
      contextChips: [],
      pendingQuestion: null,
      isWaiting: false,
    });
  });

  // --- initial state ---

  it('has correct initial state', () => {
    const state = useCoachStore.getState();
    expect(state.panelOpen).toBe(false);
    expect(state.report).toBeNull();
    expect(state.chatHistory).toEqual([]);
    expect(state.contextChips).toEqual([]);
    expect(state.pendingQuestion).toBeNull();
    expect(state.isWaiting).toBe(false);
  });

  // --- togglePanel ---

  describe('togglePanel', () => {
    it('opens panel when it is closed', () => {
      useCoachStore.getState().togglePanel();
      expect(useCoachStore.getState().panelOpen).toBe(true);
    });

    it('closes panel when it is open', () => {
      useCoachStore.setState({ panelOpen: true });
      useCoachStore.getState().togglePanel();
      expect(useCoachStore.getState().panelOpen).toBe(false);
    });

    it('toggles correctly on repeated calls', () => {
      useCoachStore.getState().togglePanel(); // false -> true
      useCoachStore.getState().togglePanel(); // true -> false
      useCoachStore.getState().togglePanel(); // false -> true
      expect(useCoachStore.getState().panelOpen).toBe(true);
    });
  });

  // --- setReport ---

  describe('setReport', () => {
    it('sets a coaching report', () => {
      useCoachStore.getState().setReport(REPORT);
      expect(useCoachStore.getState().report).toEqual(REPORT);
    });

    it('replaces an existing report', () => {
      useCoachStore.getState().setReport(REPORT);
      const updated: CoachingReport = { ...REPORT, summary: 'Updated summary.' };
      useCoachStore.getState().setReport(updated);
      expect(useCoachStore.getState().report?.summary).toBe('Updated summary.');
    });

    it('clears the report with null', () => {
      useCoachStore.getState().setReport(REPORT);
      useCoachStore.getState().setReport(null);
      expect(useCoachStore.getState().report).toBeNull();
    });

    it('does not affect other state', () => {
      useCoachStore.setState({ panelOpen: true, isWaiting: true });
      useCoachStore.getState().setReport(REPORT);
      const state = useCoachStore.getState();
      expect(state.panelOpen).toBe(true);
      expect(state.isWaiting).toBe(true);
    });
  });

  // --- addMessage ---

  describe('addMessage', () => {
    it('appends a user message to empty history', () => {
      useCoachStore.getState().addMessage(USER_MSG);
      expect(useCoachStore.getState().chatHistory).toEqual([USER_MSG]);
    });

    it('appends an assistant message after a user message', () => {
      useCoachStore.getState().addMessage(USER_MSG);
      useCoachStore.getState().addMessage(ASSISTANT_MSG);
      expect(useCoachStore.getState().chatHistory).toEqual([USER_MSG, ASSISTANT_MSG]);
    });

    it('preserves order of multiple messages', () => {
      const msg1: ChatMessage = { role: 'user', content: 'First' };
      const msg2: ChatMessage = { role: 'assistant', content: 'Second' };
      const msg3: ChatMessage = { role: 'user', content: 'Third' };
      useCoachStore.getState().addMessage(msg1);
      useCoachStore.getState().addMessage(msg2);
      useCoachStore.getState().addMessage(msg3);
      expect(useCoachStore.getState().chatHistory).toEqual([msg1, msg2, msg3]);
    });

    it('does not mutate the previous history array', () => {
      useCoachStore.getState().addMessage(USER_MSG);
      const historyAfterFirst = useCoachStore.getState().chatHistory;
      useCoachStore.getState().addMessage(ASSISTANT_MSG);
      // historyAfterFirst should still have only one entry
      expect(historyAfterFirst).toHaveLength(1);
      expect(useCoachStore.getState().chatHistory).toHaveLength(2);
    });
  });

  // --- clearChat ---

  describe('clearChat', () => {
    it('clears a populated chat history', () => {
      useCoachStore.getState().addMessage(USER_MSG);
      useCoachStore.getState().addMessage(ASSISTANT_MSG);
      useCoachStore.getState().clearChat();
      expect(useCoachStore.getState().chatHistory).toEqual([]);
    });

    it('is idempotent on empty history', () => {
      useCoachStore.getState().clearChat();
      expect(useCoachStore.getState().chatHistory).toEqual([]);
    });

    it('does not affect report or panelOpen', () => {
      useCoachStore.setState({ report: REPORT, panelOpen: true });
      useCoachStore.getState().addMessage(USER_MSG);
      useCoachStore.getState().clearChat();
      const state = useCoachStore.getState();
      expect(state.report).toEqual(REPORT);
      expect(state.panelOpen).toBe(true);
    });
  });

  // --- setContextChips ---

  describe('setContextChips', () => {
    it('sets context chips', () => {
      const chips = [
        { label: 'Corner', value: 'T5' },
        { label: 'Lap', value: '7' },
      ];
      useCoachStore.getState().setContextChips(chips);
      expect(useCoachStore.getState().contextChips).toEqual(chips);
    });

    it('replaces existing chips', () => {
      useCoachStore.getState().setContextChips([{ label: 'Old', value: 'val' }]);
      useCoachStore.getState().setContextChips([{ label: 'New', value: 'val2' }]);
      expect(useCoachStore.getState().contextChips).toEqual([{ label: 'New', value: 'val2' }]);
    });

    it('clears chips with empty array', () => {
      useCoachStore.getState().setContextChips([{ label: 'X', value: 'Y' }]);
      useCoachStore.getState().setContextChips([]);
      expect(useCoachStore.getState().contextChips).toEqual([]);
    });
  });

  // --- setPendingQuestion ---

  describe('setPendingQuestion', () => {
    it('sets a pending question string', () => {
      useCoachStore.getState().setPendingQuestion('What is my weakest corner?');
      expect(useCoachStore.getState().pendingQuestion).toBe('What is my weakest corner?');
    });

    it('clears the pending question with null', () => {
      useCoachStore.getState().setPendingQuestion('Something');
      useCoachStore.getState().setPendingQuestion(null);
      expect(useCoachStore.getState().pendingQuestion).toBeNull();
    });

    it('replaces a previous question', () => {
      useCoachStore.getState().setPendingQuestion('First question');
      useCoachStore.getState().setPendingQuestion('Second question');
      expect(useCoachStore.getState().pendingQuestion).toBe('Second question');
    });
  });

  // --- setIsWaiting ---

  describe('setIsWaiting', () => {
    it('sets isWaiting to true', () => {
      useCoachStore.getState().setIsWaiting(true);
      expect(useCoachStore.getState().isWaiting).toBe(true);
    });

    it('sets isWaiting back to false', () => {
      useCoachStore.getState().setIsWaiting(true);
      useCoachStore.getState().setIsWaiting(false);
      expect(useCoachStore.getState().isWaiting).toBe(false);
    });

    it('does not affect panelOpen or report', () => {
      useCoachStore.setState({ panelOpen: true, report: REPORT });
      useCoachStore.getState().setIsWaiting(true);
      const state = useCoachStore.getState();
      expect(state.panelOpen).toBe(true);
      expect(state.report).toEqual(REPORT);
    });
  });

  // --- state independence ---

  describe('state independence', () => {
    it('multiple unrelated fields can be set independently', () => {
      useCoachStore.getState().setReport(REPORT);
      useCoachStore.getState().setIsWaiting(true);
      useCoachStore.getState().setPendingQuestion('Q?');
      useCoachStore.getState().addMessage(USER_MSG);

      const state = useCoachStore.getState();
      expect(state.report).toEqual(REPORT);
      expect(state.isWaiting).toBe(true);
      expect(state.pendingQuestion).toBe('Q?');
      expect(state.chatHistory).toHaveLength(1);
      expect(state.panelOpen).toBe(false);
      expect(state.contextChips).toEqual([]);
    });
  });
});
