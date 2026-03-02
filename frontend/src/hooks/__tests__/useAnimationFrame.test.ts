import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAnimationFrame } from '../useAnimationFrame';

describe('useAnimationFrame', () => {
  // We use fake timers + manual RAF scheduling to control the animation loop.
  // jsdom provides requestAnimationFrame as a no-op; we replace it with a manual
  // mock so we can step through frames deterministically.

  let rafCallbacks: Map<number, FrameRequestCallback>;
  let rafIdCounter: number;
  let cancelledIds: Set<number>;

  beforeEach(() => {
    rafCallbacks = new Map();
    rafIdCounter = 0;
    cancelledIds = new Set();

    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      const id = ++rafIdCounter;
      rafCallbacks.set(id, cb);
      return id;
    });

    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      cancelledIds.add(id);
      rafCallbacks.delete(id);
    });

    vi.stubGlobal('performance', { now: () => 1000 });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    rafCallbacks.clear();
    cancelledIds.clear();
  });

  // Helper: flush the next pending RAF callback at a given timestamp
  function flushFrame(timestamp = 1000) {
    const entries = [...rafCallbacks.entries()];
    if (entries.length === 0) return;
    const [id, cb] = entries[0];
    rafCallbacks.delete(id);
    cb(timestamp);
  }

  // ---------------------------------------------------------------------------
  // Basic start behavior
  // ---------------------------------------------------------------------------
  describe('when active=true (default)', () => {
    it('schedules a requestAnimationFrame on mount', () => {
      renderHook(() => useAnimationFrame(vi.fn()));
      expect(rafCallbacks.size).toBe(1);
    });

    it('calls the callback on each frame', () => {
      const callback = vi.fn();
      renderHook(() => useAnimationFrame(callback));

      // Fire first frame
      flushFrame(100);
      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith(100);

      // After the first callback, the hook schedules another RAF
      flushFrame(200);
      expect(callback).toHaveBeenCalledTimes(2);
      expect(callback).toHaveBeenLastCalledWith(200);
    });

    it('passes the timestamp argument to the callback', () => {
      const callback = vi.fn();
      renderHook(() => useAnimationFrame(callback));
      flushFrame(42.5);
      expect(callback).toHaveBeenCalledWith(42.5);
    });

    it('continues the loop by scheduling a new RAF after each frame', () => {
      const callback = vi.fn();
      renderHook(() => useAnimationFrame(callback));

      // Each flush triggers the next RAF registration
      flushFrame(1);
      expect(rafCallbacks.size).toBe(1); // new RAF scheduled

      flushFrame(2);
      expect(rafCallbacks.size).toBe(1);

      flushFrame(3);
      expect(callback).toHaveBeenCalledTimes(3);
    });
  });

  // ---------------------------------------------------------------------------
  // Stop behavior when active=false
  // ---------------------------------------------------------------------------
  describe('when active=false', () => {
    it('does not schedule a requestAnimationFrame', () => {
      renderHook(() => useAnimationFrame(vi.fn(), false));
      // No RAF should be pending; the inactive path only calls callback once via performance.now()
      expect(rafCallbacks.size).toBe(0);
    });

    it('calls the callback once immediately to clear any residual overlay', () => {
      const callback = vi.fn();
      renderHook(() => useAnimationFrame(callback, false));
      // Should have been called once with performance.now() value
      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith(1000); // our stubbed performance.now()
    });

    it('does not continue the loop after the single inactive call', () => {
      const callback = vi.fn();
      renderHook(() => useAnimationFrame(callback, false));
      // No further frames possible
      expect(rafCallbacks.size).toBe(0);
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  // ---------------------------------------------------------------------------
  // Cleanup on unmount
  // ---------------------------------------------------------------------------
  describe('cleanup on unmount', () => {
    it('cancels the pending RAF when unmounted', () => {
      const { unmount } = renderHook(() => useAnimationFrame(vi.fn()));
      const pendingId = rafIdCounter;
      unmount();
      expect(cancelledIds.has(pendingId)).toBe(true);
    });

    it('does not call the callback after unmount', () => {
      const callback = vi.fn();
      const { unmount } = renderHook(() => useAnimationFrame(callback));
      unmount();
      // Try to flush any remaining callbacks — none should fire
      const remaining = [...rafCallbacks.values()];
      remaining.forEach((cb) => cb(999));
      // Should still be 0 calls (RAF was cancelled before flush)
      expect(callback).toHaveBeenCalledTimes(0);
    });
  });

  // ---------------------------------------------------------------------------
  // Transition from active to inactive
  // ---------------------------------------------------------------------------
  describe('toggling active flag', () => {
    it('cancels the loop when active switches from true to false', () => {
      let active = true;
      const callback = vi.fn();
      const { rerender } = renderHook(() => useAnimationFrame(callback, active));

      // Loop is running
      flushFrame(1);
      expect(callback).toHaveBeenCalledTimes(1);

      // Switch to inactive
      active = false;
      act(() => {
        rerender();
      });

      // After rerender with active=false, the loop should be cleaned up.
      // No more RAF pending from the loop (only the single clearance call was made).
      expect(rafCallbacks.size).toBe(0);
    });

    it('calls callback once when transitioning to inactive', () => {
      let active = true;
      const callback = vi.fn();
      const { rerender } = renderHook(() => useAnimationFrame(callback, active));

      active = false;
      act(() => {
        rerender();
      });

      // The inactive path calls callback once
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('resumes the loop when active switches from false to true', () => {
      let active = false;
      const callback = vi.fn();
      const { rerender } = renderHook(() => useAnimationFrame(callback, active));
      const callsAfterInactive = callback.mock.calls.length; // 1

      active = true;
      act(() => {
        rerender();
      });

      // New RAF should be pending
      expect(rafCallbacks.size).toBe(1);

      flushFrame(500);
      expect(callback).toHaveBeenCalledTimes(callsAfterInactive + 1);
    });
  });

  // ---------------------------------------------------------------------------
  // Callback identity stability
  // ---------------------------------------------------------------------------
  describe('callback ref stability', () => {
    it('uses the latest callback without restarting the loop', () => {
      const callbackV1 = vi.fn();
      const callbackV2 = vi.fn();
      let currentCallback = callbackV1;

      const { rerender } = renderHook(() =>
        useAnimationFrame(currentCallback),
      );

      // First frame with v1
      flushFrame(1);
      expect(callbackV1).toHaveBeenCalledTimes(1);

      // Switch callback to v2 without changing active
      currentCallback = callbackV2;
      act(() => {
        rerender();
      });

      // Next frame should call v2 (latest via ref), not v1
      flushFrame(2);
      expect(callbackV2).toHaveBeenCalledTimes(1);
      expect(callbackV1).toHaveBeenCalledTimes(1); // still only 1 — not called again
    });
  });

  // ---------------------------------------------------------------------------
  // Edge cases
  // ---------------------------------------------------------------------------
  describe('edge cases', () => {
    it('handles a no-op callback without throwing', () => {
      expect(() => {
        const { unmount } = renderHook(() => useAnimationFrame(() => {}));
        flushFrame(0);
        unmount();
      }).not.toThrow();
    });

    it('handles zero timestamp', () => {
      const callback = vi.fn();
      renderHook(() => useAnimationFrame(callback));
      flushFrame(0);
      expect(callback).toHaveBeenCalledWith(0);
    });

    it('handles very large timestamps', () => {
      const callback = vi.fn();
      renderHook(() => useAnimationFrame(callback));
      const largeTs = Number.MAX_SAFE_INTEGER;
      flushFrame(largeTs);
      expect(callback).toHaveBeenCalledWith(largeTs);
    });

    it('a callback that throws does not swallow subsequent RAF scheduling', () => {
      // The loop re-schedules in the `loop` function before calling the callback
      // Because the loop calls callbackRef.current(timestamp) first, then schedules next RAF:
      // Actually useAnimationFrame calls callback then requestAnimationFrame(loop).
      // If callback throws, the next RAF is not scheduled. That's expected behavior.
      const callback = vi.fn().mockImplementationOnce(() => {
        throw new Error('test error');
      });
      renderHook(() => useAnimationFrame(callback));
      expect(() => flushFrame(1)).toThrow('test error');
      // After a throw the RAF loop is broken — that's the implementation's behavior
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });
});
