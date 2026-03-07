import { describe, it, expect } from 'vitest';
import {
  useAnalysisStore,
  useSessionStore,
  useCoachStore,
  useUiStore,
} from '../index';

describe('stores/index re-exports', () => {
  it('exports useAnalysisStore', () => {
    expect(useAnalysisStore).toBeDefined();
    expect(typeof useAnalysisStore.getState).toBe('function');
  });

  it('exports useSessionStore', () => {
    expect(useSessionStore).toBeDefined();
    expect(typeof useSessionStore.getState).toBe('function');
  });

  it('exports useCoachStore', () => {
    expect(useCoachStore).toBeDefined();
    expect(typeof useCoachStore.getState).toBe('function');
  });

  it('exports useUiStore', () => {
    expect(useUiStore).toBeDefined();
    expect(typeof useUiStore.getState).toBe('function');
  });
});
