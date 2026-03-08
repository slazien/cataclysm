import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMediaQuery, useIsMobile, useIsTablet } from '../useMediaQuery';

// jsdom doesn't implement window.matchMedia — we stub it with a factory that
// lets each test control the initial `matches` value and fire change events.

type ChangeHandler = (e: MediaQueryListEvent) => void;

function makeMql(matches: boolean) {
  const handlers: ChangeHandler[] = [];
  return {
    matches,
    addEventListener: vi.fn((_type: string, handler: ChangeHandler) => {
      handlers.push(handler);
    }),
    removeEventListener: vi.fn((_type: string, handler: ChangeHandler) => {
      const idx = handlers.indexOf(handler);
      if (idx !== -1) handlers.splice(idx, 1);
    }),
    // Helper: fire a change event on all registered listeners
    _fire(newMatches: boolean) {
      handlers.forEach((h) => h({ matches: newMatches } as MediaQueryListEvent));
    },
    _handlers: handlers,
  };
}

describe('useMediaQuery', () => {
  let mql: ReturnType<typeof makeMql>;

  beforeEach(() => {
    mql = makeMql(false);
    vi.stubGlobal('matchMedia', vi.fn(() => mql));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns false on initial render (SSR-safe default)', () => {
    // The hook initialises state to false before useEffect runs.
    // This prevents hydration mismatches on the server.
    mql = makeMql(true); // even when media matches, initial render is false
    vi.stubGlobal('matchMedia', vi.fn(() => mql));

    const { result } = renderHook(() => useMediaQuery('(max-width: 1023px)'));
    // After mount, useEffect has fired and updated to mql.matches
    expect(result.current).toBe(true);
  });

  it('returns false when media does not match', () => {
    mql = makeMql(false);
    vi.stubGlobal('matchMedia', vi.fn(() => mql));

    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'));
    expect(result.current).toBe(false);
  });

  it('returns true when media matches on mount', () => {
    mql = makeMql(true);
    vi.stubGlobal('matchMedia', vi.fn(() => mql));

    const { result } = renderHook(() => useMediaQuery('(max-width: 1023px)'));
    expect(result.current).toBe(true);
  });

  it('updates when the media query fires a change event', () => {
    mql = makeMql(false);
    vi.stubGlobal('matchMedia', vi.fn(() => mql));

    const { result } = renderHook(() => useMediaQuery('(max-width: 1023px)'));
    expect(result.current).toBe(false);

    act(() => {
      mql._fire(true);
    });

    expect(result.current).toBe(true);
  });

  it('can toggle back from true to false on change event', () => {
    mql = makeMql(true);
    vi.stubGlobal('matchMedia', vi.fn(() => mql));

    const { result } = renderHook(() => useMediaQuery('(max-width: 1023px)'));
    expect(result.current).toBe(true);

    act(() => {
      mql._fire(false);
    });

    expect(result.current).toBe(false);
  });

  it('registers a change listener on mount', () => {
    renderHook(() => useMediaQuery('(max-width: 1023px)'));
    expect(mql.addEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('removes the change listener on unmount', () => {
    const { unmount } = renderHook(() => useMediaQuery('(max-width: 1023px)'));
    unmount();
    expect(mql.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('does not update state after unmount', () => {
    const { result, unmount } = renderHook(() =>
      useMediaQuery('(max-width: 1023px)'),
    );
    unmount();

    // Fire change after unmount — should not throw or update
    expect(() => {
      act(() => {
        mql._fire(true);
      });
    }).not.toThrow();

    // Result should remain at pre-unmount value (false)
    expect(result.current).toBe(false);
  });

  it('passes the query string to matchMedia', () => {
    const query = '(min-width: 768px) and (max-width: 1023px)';
    renderHook(() => useMediaQuery(query));
    expect(window.matchMedia).toHaveBeenCalledWith(query);
  });

  it('re-subscribes when the query string changes', () => {
    let query = '(max-width: 767px)';
    const { rerender } = renderHook(() => useMediaQuery(query));

    expect(window.matchMedia).toHaveBeenCalledTimes(1);

    query = '(max-width: 1023px)';
    rerender();

    expect(window.matchMedia).toHaveBeenCalledTimes(2);
    expect(window.matchMedia).toHaveBeenLastCalledWith('(max-width: 1023px)');
  });
});

describe('useIsMobile', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('uses the correct lg breakpoint query (max-width: 1023px)', () => {
    const mql = makeMql(false);
    vi.stubGlobal('matchMedia', vi.fn(() => mql));

    renderHook(() => useIsMobile());

    expect(window.matchMedia).toHaveBeenCalledWith('(max-width: 1023px)');
  });

  it('returns true when viewport is below 1024px', () => {
    vi.stubGlobal('matchMedia', vi.fn(() => makeMql(true)));
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it('returns false when viewport is 1024px or above', () => {
    vi.stubGlobal('matchMedia', vi.fn(() => makeMql(false)));
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });
});

describe('useIsTablet', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('uses the correct tablet range query (768–1023px)', () => {
    const mql = makeMql(false);
    vi.stubGlobal('matchMedia', vi.fn(() => mql));

    renderHook(() => useIsTablet());

    expect(window.matchMedia).toHaveBeenCalledWith(
      '(min-width: 768px) and (max-width: 1023px)',
    );
  });

  it('returns true when viewport is in tablet range', () => {
    vi.stubGlobal('matchMedia', vi.fn(() => makeMql(true)));
    const { result } = renderHook(() => useIsTablet());
    expect(result.current).toBe(true);
  });

  it('returns false outside the tablet range', () => {
    vi.stubGlobal('matchMedia', vi.fn(() => makeMql(false)));
    const { result } = renderHook(() => useIsTablet());
    expect(result.current).toBe(false);
  });
});
