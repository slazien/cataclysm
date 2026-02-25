import { describe, it, expect, beforeEach } from 'vitest';
import { useAnalysisStore } from '../analysisStore';

describe('analysisStore', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useAnalysisStore.setState({
      cursorDistance: null,
      selectedLaps: [],
      selectedCorner: null,
      deepDiveMode: 'speed',
      zoomRange: null,
    });
  });

  it('has correct initial state', () => {
    const state = useAnalysisStore.getState();
    expect(state.cursorDistance).toBeNull();
    expect(state.selectedLaps).toEqual([]);
    expect(state.selectedCorner).toBeNull();
    expect(state.deepDiveMode).toBe('speed');
    expect(state.zoomRange).toBeNull();
  });

  describe('setCursorDistance', () => {
    it('sets cursor distance to a number', () => {
      useAnalysisStore.getState().setCursorDistance(150.5);
      expect(useAnalysisStore.getState().cursorDistance).toBe(150.5);
    });

    it('sets cursor distance to null', () => {
      useAnalysisStore.getState().setCursorDistance(100);
      useAnalysisStore.getState().setCursorDistance(null);
      expect(useAnalysisStore.getState().cursorDistance).toBeNull();
    });

    it('sets cursor distance to zero', () => {
      useAnalysisStore.getState().setCursorDistance(0);
      expect(useAnalysisStore.getState().cursorDistance).toBe(0);
    });
  });

  describe('selectLaps', () => {
    it('selects multiple laps', () => {
      useAnalysisStore.getState().selectLaps([1, 3, 5]);
      expect(useAnalysisStore.getState().selectedLaps).toEqual([1, 3, 5]);
    });

    it('replaces previous selection', () => {
      useAnalysisStore.getState().selectLaps([1, 2]);
      useAnalysisStore.getState().selectLaps([3, 4]);
      expect(useAnalysisStore.getState().selectedLaps).toEqual([3, 4]);
    });

    it('clears selection with empty array', () => {
      useAnalysisStore.getState().selectLaps([1, 2, 3]);
      useAnalysisStore.getState().selectLaps([]);
      expect(useAnalysisStore.getState().selectedLaps).toEqual([]);
    });
  });

  describe('selectCorner', () => {
    it('selects a corner by id', () => {
      useAnalysisStore.getState().selectCorner('corner-5');
      expect(useAnalysisStore.getState().selectedCorner).toBe('corner-5');
    });

    it('deselects corner with null', () => {
      useAnalysisStore.getState().selectCorner('corner-3');
      useAnalysisStore.getState().selectCorner(null);
      expect(useAnalysisStore.getState().selectedCorner).toBeNull();
    });
  });

  describe('setMode', () => {
    it('switches to corner mode', () => {
      useAnalysisStore.getState().setMode('corner');
      expect(useAnalysisStore.getState().deepDiveMode).toBe('corner');
    });

    it('switches to custom mode', () => {
      useAnalysisStore.getState().setMode('custom');
      expect(useAnalysisStore.getState().deepDiveMode).toBe('custom');
    });

    it('switches back to speed mode', () => {
      useAnalysisStore.getState().setMode('corner');
      useAnalysisStore.getState().setMode('speed');
      expect(useAnalysisStore.getState().deepDiveMode).toBe('speed');
    });
  });

  describe('setZoom', () => {
    it('sets a zoom range', () => {
      useAnalysisStore.getState().setZoom([100, 500]);
      expect(useAnalysisStore.getState().zoomRange).toEqual([100, 500]);
    });

    it('clears zoom with null', () => {
      useAnalysisStore.getState().setZoom([100, 500]);
      useAnalysisStore.getState().setZoom(null);
      expect(useAnalysisStore.getState().zoomRange).toBeNull();
    });

    it('updates zoom range', () => {
      useAnalysisStore.getState().setZoom([0, 1000]);
      useAnalysisStore.getState().setZoom([200, 800]);
      expect(useAnalysisStore.getState().zoomRange).toEqual([200, 800]);
    });
  });

  describe('state independence', () => {
    it('setting one field does not affect others', () => {
      useAnalysisStore.getState().selectLaps([1, 2]);
      useAnalysisStore.getState().setCursorDistance(300);

      const state = useAnalysisStore.getState();
      expect(state.selectedLaps).toEqual([1, 2]);
      expect(state.cursorDistance).toBe(300);
      expect(state.selectedCorner).toBeNull();
      expect(state.deepDiveMode).toBe('speed');
      expect(state.zoomRange).toBeNull();
    });
  });
});
