import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useUiStore } from '@/stores/uiStore';
import { useAnalysisStore } from '@/stores/analysisStore';
import { useCoachStore } from '@/stores/coachStore';
import { useSessionStore } from '@/stores/sessionStore';

// Mock useCorners — the hook calls it internally to get corners data.
vi.mock('@/hooks/useAnalysis', () => ({
  useCorners: vi.fn(() => ({ data: [] })),
}));

import { useKeyboardShortcuts } from '../useKeyboardShortcuts';
import { useCorners } from '@/hooks/useAnalysis';

// Helper: fire a keydown event on window, wrapped in act() so React processes
// any synchronous state updates that result from the event handler.
function fireKey(key: string, options: Partial<KeyboardEventInit> & { target?: HTMLElement } = {}) {
  act(() => {
    const { target, ...init } = options;
    const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init });
    if (target) {
      Object.defineProperty(event, 'target', { value: target, configurable: true });
    }
    window.dispatchEvent(event);
  });
}

describe('useKeyboardShortcuts', () => {
  beforeEach(() => {
    // Reset all stores to known initial state
    useUiStore.setState({
      activeView: 'session-report',
      sessionDrawerOpen: false,
      settingsPanelOpen: false,
    });
    useAnalysisStore.setState({
      selectedCorner: null,
      deepDiveMode: 'speed',
      cursorDistance: null,
      selectedLaps: [],
      zoomRange: null,
    });
    useCoachStore.setState({
      panelOpen: false,
    });
    useSessionStore.setState({
      activeSessionId: null,
    });

    vi.mocked(useCorners).mockReturnValue({ data: [] } as ReturnType<typeof useCorners>);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ---------------------------------------------------------------------------
  // View navigation shortcuts
  // ---------------------------------------------------------------------------
  describe('view navigation', () => {
    it('pressing "1" navigates to session-report view', () => {
      useUiStore.setState({ activeView: 'deep-dive' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('1');
      expect(useUiStore.getState().activeView).toBe('session-report');
    });

    it('pressing "2" navigates to deep-dive view', () => {
      useUiStore.setState({ activeView: 'session-report' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('2');
      expect(useUiStore.getState().activeView).toBe('deep-dive');
    });

    it('pressing "3" navigates to progress view', () => {
      useUiStore.setState({ activeView: 'session-report' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('3');
      expect(useUiStore.getState().activeView).toBe('progress');
    });

    it('pressing "1" is idempotent when already on session-report', () => {
      useUiStore.setState({ activeView: 'session-report' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('1');
      expect(useUiStore.getState().activeView).toBe('session-report');
    });
  });

  // ---------------------------------------------------------------------------
  // Escape key behavior
  // ---------------------------------------------------------------------------
  describe('Escape key', () => {
    it('closes the session drawer when it is open', () => {
      useUiStore.setState({ sessionDrawerOpen: true });
      renderHook(() => useKeyboardShortcuts());
      fireKey('Escape');
      expect(useUiStore.getState().sessionDrawerOpen).toBe(false);
    });

    it('closes the coach panel when drawer is closed and panel is open', () => {
      useUiStore.setState({ sessionDrawerOpen: false });
      useCoachStore.setState({ panelOpen: true });
      renderHook(() => useKeyboardShortcuts());
      fireKey('Escape');
      expect(useCoachStore.getState().panelOpen).toBe(false);
    });

    it('does nothing when both drawer and panel are closed', () => {
      useUiStore.setState({ sessionDrawerOpen: false });
      useCoachStore.setState({ panelOpen: false });
      renderHook(() => useKeyboardShortcuts());
      fireKey('Escape');
      expect(useUiStore.getState().sessionDrawerOpen).toBe(false);
      expect(useCoachStore.getState().panelOpen).toBe(false);
    });

    it('Escape key works even when target is an INPUT element', () => {
      // The hook allows Escape through even for inputs/textareas
      useUiStore.setState({ sessionDrawerOpen: true });
      renderHook(() => useKeyboardShortcuts());
      const input = document.createElement('input');
      fireKey('Escape', { target: input });
      expect(useUiStore.getState().sessionDrawerOpen).toBe(false);
    });

    it('prioritizes drawer close over panel close when both open', () => {
      // Escape should close drawer first (the if-else branch order)
      useUiStore.setState({ sessionDrawerOpen: true });
      useCoachStore.setState({ panelOpen: true });
      renderHook(() => useKeyboardShortcuts());
      fireKey('Escape');
      // Drawer gets closed; panel untouched on first Escape
      expect(useUiStore.getState().sessionDrawerOpen).toBe(false);
      expect(useCoachStore.getState().panelOpen).toBe(true);
    });
  });

  // ---------------------------------------------------------------------------
  // "/" shortcut — open coach panel
  // ---------------------------------------------------------------------------
  describe('"/" shortcut', () => {
    it('opens coach panel when "/" is pressed and panel is closed', () => {
      useCoachStore.setState({ panelOpen: false });
      renderHook(() => useKeyboardShortcuts());
      fireKey('/');
      expect(useCoachStore.getState().panelOpen).toBe(true);
    });

    it('does not toggle panel again when "/" is pressed and panel is already open', () => {
      useCoachStore.setState({ panelOpen: true });
      renderHook(() => useKeyboardShortcuts());
      fireKey('/');
      // panelOpen stays true (if (!panelOpen) guard prevents double-toggle)
      expect(useCoachStore.getState().panelOpen).toBe(true);
    });
  });

  // ---------------------------------------------------------------------------
  // Input field suppression (tagName-based)
  // ---------------------------------------------------------------------------
  describe('input field suppression', () => {
    it('ignores "1" key press when target is INPUT', () => {
      useUiStore.setState({ activeView: 'session-report' });
      renderHook(() => useKeyboardShortcuts());
      const input = document.createElement('input');
      fireKey('1', { target: input });
      expect(useUiStore.getState().activeView).toBe('session-report');
    });

    it('ignores "2" key press when target is TEXTAREA', () => {
      useUiStore.setState({ activeView: 'session-report' });
      renderHook(() => useKeyboardShortcuts());
      const textarea = document.createElement('textarea');
      fireKey('2', { target: textarea });
      expect(useUiStore.getState().activeView).toBe('session-report');
    });

    it('ignores "3" key press when target is INPUT', () => {
      useUiStore.setState({ activeView: 'session-report' });
      renderHook(() => useKeyboardShortcuts());
      const input = document.createElement('input');
      fireKey('3', { target: input });
      expect(useUiStore.getState().activeView).toBe('session-report');
    });

    it('ignores "/" key press when target is TEXTAREA', () => {
      useCoachStore.setState({ panelOpen: false });
      renderHook(() => useKeyboardShortcuts());
      const textarea = document.createElement('textarea');
      fireKey('/', { target: textarea });
      // Panel should NOT open because the user is typing in a textarea
      expect(useCoachStore.getState().panelOpen).toBe(false);
    });

    it('ignores ArrowRight when target is INPUT (in deep-dive corner mode)', () => {
      useUiStore.setState({ activeView: 'deep-dive' });
      useAnalysisStore.setState({ deepDiveMode: 'corner', selectedCorner: null });
      vi.mocked(useCorners).mockReturnValue({
        data: [{ number: 1 }, { number: 2 }],
      } as ReturnType<typeof useCorners>);
      renderHook(() => useKeyboardShortcuts());
      const input = document.createElement('input');
      fireKey('ArrowRight', { target: input });
      // Corner should NOT change because user is in an input
      expect(useAnalysisStore.getState().selectedCorner).toBeNull();
    });
  });

  // ---------------------------------------------------------------------------
  // ArrowLeft / ArrowRight corner cycling
  // ---------------------------------------------------------------------------
  describe('corner navigation (ArrowLeft / ArrowRight)', () => {
    beforeEach(() => {
      useUiStore.setState({ activeView: 'deep-dive' });
      useAnalysisStore.setState({ deepDiveMode: 'corner', selectedCorner: null });
      vi.mocked(useCorners).mockReturnValue({
        data: [{ number: 1 }, { number: 2 }, { number: 3 }],
      } as ReturnType<typeof useCorners>);
    });

    it('ArrowRight selects T1 when no corner is selected', () => {
      renderHook(() => useKeyboardShortcuts());
      fireKey('ArrowRight');
      // currentNum=0 from null → indexOf(0) === -1 → nextIdx=0 → T1
      expect(useAnalysisStore.getState().selectedCorner).toBe('T1');
    });

    it('ArrowRight advances to the next corner', () => {
      useAnalysisStore.setState({ selectedCorner: 'T1' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('ArrowRight');
      expect(useAnalysisStore.getState().selectedCorner).toBe('T2');
    });

    it('ArrowRight wraps around from last corner to first', () => {
      useAnalysisStore.setState({ selectedCorner: 'T3' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('ArrowRight');
      expect(useAnalysisStore.getState().selectedCorner).toBe('T1');
    });

    it('ArrowLeft wraps from first corner to last', () => {
      useAnalysisStore.setState({ selectedCorner: 'T1' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('ArrowLeft');
      expect(useAnalysisStore.getState().selectedCorner).toBe('T3');
    });

    it('ArrowLeft goes to previous corner', () => {
      useAnalysisStore.setState({ selectedCorner: 'T3' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('ArrowLeft');
      expect(useAnalysisStore.getState().selectedCorner).toBe('T2');
    });

    it('ArrowRight does nothing when not in deep-dive view', () => {
      useUiStore.setState({ activeView: 'session-report' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('ArrowRight');
      expect(useAnalysisStore.getState().selectedCorner).toBeNull();
    });

    it('ArrowRight does nothing when not in corner deepDiveMode', () => {
      useUiStore.setState({ activeView: 'deep-dive' });
      useAnalysisStore.setState({ deepDiveMode: 'speed' });
      renderHook(() => useKeyboardShortcuts());
      fireKey('ArrowRight');
      expect(useAnalysisStore.getState().selectedCorner).toBeNull();
    });

    it('ArrowRight does nothing when corners array is empty', () => {
      vi.mocked(useCorners).mockReturnValue({ data: [] } as ReturnType<typeof useCorners>);
      renderHook(() => useKeyboardShortcuts());
      fireKey('ArrowRight');
      expect(useAnalysisStore.getState().selectedCorner).toBeNull();
    });

    it('ArrowRight does nothing when corners data is undefined', () => {
      vi.mocked(useCorners).mockReturnValue({ data: undefined } as ReturnType<typeof useCorners>);
      renderHook(() => useKeyboardShortcuts());
      fireKey('ArrowRight');
      expect(useAnalysisStore.getState().selectedCorner).toBeNull();
    });
  });

  // ---------------------------------------------------------------------------
  // Cleanup — event listener is removed on unmount
  // ---------------------------------------------------------------------------
  describe('cleanup on unmount', () => {
    it('does not fire callbacks after the hook is unmounted', () => {
      useUiStore.setState({ activeView: 'session-report' });
      const { unmount } = renderHook(() => useKeyboardShortcuts());
      unmount();
      fireKey('2');
      expect(useUiStore.getState().activeView).toBe('session-report');
    });

    it('multiple mounts and unmounts do not accumulate listeners', () => {
      useUiStore.setState({ activeView: 'session-report' });
      const { unmount: u1 } = renderHook(() => useKeyboardShortcuts());
      const { unmount: u2 } = renderHook(() => useKeyboardShortcuts());
      u1();
      u2();
      fireKey('2');
      // Both unmounted — view should be unchanged
      expect(useUiStore.getState().activeView).toBe('session-report');
    });
  });
});
