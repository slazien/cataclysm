import { describe, it, expect, beforeEach } from 'vitest';
import { useAnalysisStore } from '@/stores/analysisStore';

describe('cursor sync integration', () => {
  beforeEach(() => {
    useAnalysisStore.setState({
      cursorDistance: null,
      selectedLaps: [],
      selectedCorner: null,
      deepDiveMode: 'speed',
      zoomRange: null,
    });
  });

  it('cursor distance propagates to all subscribers', () => {
    // Simulate one chart setting the cursor distance (e.g., SpeedTrace mousemove)
    useAnalysisStore.getState().setCursorDistance(450.5);

    // All other charts should read the same value
    const state = useAnalysisStore.getState();
    expect(state.cursorDistance).toBe(450.5);
  });

  it('cursor distance clears on mouseleave', () => {
    useAnalysisStore.getState().setCursorDistance(300);
    expect(useAnalysisStore.getState().cursorDistance).toBe(300);

    // Simulate mouseleave
    useAnalysisStore.getState().setCursorDistance(null);
    expect(useAnalysisStore.getState().cursorDistance).toBeNull();
  });

  it('cursor distance updates rapidly without dropping state', () => {
    // Simulate rapid mouse movement across a chart
    const distances = [100, 150, 200, 250, 300, 350, 400, 450, 500];
    for (const d of distances) {
      useAnalysisStore.getState().setCursorDistance(d);
    }
    // Final value should be the last one set
    expect(useAnalysisStore.getState().cursorDistance).toBe(500);
  });

  it('cursor distance is independent of selected laps', () => {
    useAnalysisStore.getState().selectLaps([1, 3]);
    useAnalysisStore.getState().setCursorDistance(275);

    const state = useAnalysisStore.getState();
    expect(state.cursorDistance).toBe(275);
    expect(state.selectedLaps).toEqual([1, 3]);
  });

  it('cursor distance is independent of selected corner', () => {
    useAnalysisStore.getState().selectCorner('T5');
    useAnalysisStore.getState().setCursorDistance(800);

    const state = useAnalysisStore.getState();
    expect(state.cursorDistance).toBe(800);
    expect(state.selectedCorner).toBe('T5');
  });

  it('cursor works with zero distance', () => {
    useAnalysisStore.getState().setCursorDistance(0);
    expect(useAnalysisStore.getState().cursorDistance).toBe(0);
  });

  it('corner selection triggers from track map click', () => {
    useAnalysisStore.getState().selectCorner('T3');
    expect(useAnalysisStore.getState().selectedCorner).toBe('T3');

    // Toggle off
    useAnalysisStore.getState().selectCorner(null);
    expect(useAnalysisStore.getState().selectedCorner).toBeNull();
  });

  it('mode switch from corner quick card works', () => {
    expect(useAnalysisStore.getState().deepDiveMode).toBe('speed');
    useAnalysisStore.getState().setMode('corner');
    expect(useAnalysisStore.getState().deepDiveMode).toBe('corner');
  });

  it('cursor state persists across mode switches', () => {
    useAnalysisStore.getState().setCursorDistance(600);
    useAnalysisStore.getState().setMode('corner');

    const state = useAnalysisStore.getState();
    expect(state.cursorDistance).toBe(600);
    expect(state.deepDiveMode).toBe('corner');
  });
});
