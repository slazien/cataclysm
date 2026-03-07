import { describe, it, expect, beforeEach } from 'vitest';
import { useUiStore } from '../uiStore';
import type { Toast } from '../uiStore';

// Canonical initial state values matching the store defaults.
const INITIAL_STATE = {
  activeView: 'session-report' as const,
  skillLevel: 'intermediate' as const,
  sessionDrawerOpen: false,
  settingsPanelOpen: false,
  unitPreference: 'imperial' as const,
  toasts: [] as Toast[],
  uploadPromptOpen: false,
};

describe('uiStore', () => {
  beforeEach(() => {
    // Reset in-memory state. The persist middleware only reads from localStorage
    // during initial hydration, so forcing setState here is safe for unit tests.
    useUiStore.setState(INITIAL_STATE);
  });

  // --- initial state ---

  it('has correct initial state', () => {
    const state = useUiStore.getState();
    expect(state.activeView).toBe('session-report');
    expect(state.skillLevel).toBe('intermediate');
    expect(state.sessionDrawerOpen).toBe(false);
    expect(state.settingsPanelOpen).toBe(false);
    expect(state.unitPreference).toBe('imperial');
    expect(state.toasts).toEqual([]);
    expect(state.uploadPromptOpen).toBe(false);
  });

  // --- setActiveView ---

  describe('setActiveView', () => {
    it('switches to deep-dive view', () => {
      useUiStore.getState().setActiveView('deep-dive');
      expect(useUiStore.getState().activeView).toBe('deep-dive');
    });

    it('switches to progress view', () => {
      useUiStore.getState().setActiveView('progress');
      expect(useUiStore.getState().activeView).toBe('progress');
    });

    it('switches to debrief view', () => {
      useUiStore.getState().setActiveView('debrief');
      expect(useUiStore.getState().activeView).toBe('debrief');
    });

    it('switches back to session-report view', () => {
      useUiStore.getState().setActiveView('deep-dive');
      useUiStore.getState().setActiveView('session-report');
      expect(useUiStore.getState().activeView).toBe('session-report');
    });

    it('does not affect other state fields', () => {
      useUiStore.setState({ skillLevel: 'advanced', unitPreference: 'metric' });
      useUiStore.getState().setActiveView('progress');
      const state = useUiStore.getState();
      expect(state.skillLevel).toBe('advanced');
      expect(state.unitPreference).toBe('metric');
    });
  });

  // --- setSkillLevel ---

  describe('setSkillLevel', () => {
    it('sets skill level to novice', () => {
      useUiStore.getState().setSkillLevel('novice');
      expect(useUiStore.getState().skillLevel).toBe('novice');
    });

    it('sets skill level to advanced', () => {
      useUiStore.getState().setSkillLevel('advanced');
      expect(useUiStore.getState().skillLevel).toBe('advanced');
    });

    it('sets skill level back to intermediate', () => {
      useUiStore.getState().setSkillLevel('advanced');
      useUiStore.getState().setSkillLevel('intermediate');
      expect(useUiStore.getState().skillLevel).toBe('intermediate');
    });

    it('does not affect other state fields', () => {
      useUiStore.setState({ activeView: 'deep-dive', unitPreference: 'metric' });
      useUiStore.getState().setSkillLevel('novice');
      const state = useUiStore.getState();
      expect(state.activeView).toBe('deep-dive');
      expect(state.unitPreference).toBe('metric');
    });
  });

  // --- toggleSessionDrawer ---

  describe('toggleSessionDrawer', () => {
    it('opens drawer when it is closed', () => {
      useUiStore.getState().toggleSessionDrawer();
      expect(useUiStore.getState().sessionDrawerOpen).toBe(true);
    });

    it('closes drawer when it is open', () => {
      useUiStore.setState({ sessionDrawerOpen: true });
      useUiStore.getState().toggleSessionDrawer();
      expect(useUiStore.getState().sessionDrawerOpen).toBe(false);
    });

    it('toggles correctly across multiple calls', () => {
      useUiStore.getState().toggleSessionDrawer(); // -> true
      useUiStore.getState().toggleSessionDrawer(); // -> false
      useUiStore.getState().toggleSessionDrawer(); // -> true
      expect(useUiStore.getState().sessionDrawerOpen).toBe(true);
    });

    it('does not affect settingsPanelOpen', () => {
      useUiStore.setState({ settingsPanelOpen: true });
      useUiStore.getState().toggleSessionDrawer();
      expect(useUiStore.getState().settingsPanelOpen).toBe(true);
    });
  });

  // --- toggleSettingsPanel ---

  describe('toggleSettingsPanel', () => {
    it('opens settings panel when it is closed', () => {
      useUiStore.getState().toggleSettingsPanel();
      expect(useUiStore.getState().settingsPanelOpen).toBe(true);
    });

    it('closes settings panel when it is open', () => {
      useUiStore.setState({ settingsPanelOpen: true });
      useUiStore.getState().toggleSettingsPanel();
      expect(useUiStore.getState().settingsPanelOpen).toBe(false);
    });

    it('toggles correctly across multiple calls', () => {
      useUiStore.getState().toggleSettingsPanel(); // -> true
      useUiStore.getState().toggleSettingsPanel(); // -> false
      useUiStore.getState().toggleSettingsPanel(); // -> true
      expect(useUiStore.getState().settingsPanelOpen).toBe(true);
    });

    it('does not affect sessionDrawerOpen', () => {
      useUiStore.setState({ sessionDrawerOpen: true });
      useUiStore.getState().toggleSettingsPanel();
      expect(useUiStore.getState().sessionDrawerOpen).toBe(true);
    });
  });

  // --- setUnitPreference ---

  describe('setUnitPreference', () => {
    it('switches to metric', () => {
      useUiStore.getState().setUnitPreference('metric');
      expect(useUiStore.getState().unitPreference).toBe('metric');
    });

    it('switches back to imperial', () => {
      useUiStore.getState().setUnitPreference('metric');
      useUiStore.getState().setUnitPreference('imperial');
      expect(useUiStore.getState().unitPreference).toBe('imperial');
    });

    it('does not affect skillLevel or activeView', () => {
      useUiStore.setState({ skillLevel: 'advanced', activeView: 'progress' });
      useUiStore.getState().setUnitPreference('metric');
      const state = useUiStore.getState();
      expect(state.skillLevel).toBe('advanced');
      expect(state.activeView).toBe('progress');
    });
  });

  // --- addToast ---

  describe('addToast', () => {
    it('adds a pb toast to an empty list', () => {
      useUiStore.getState().addToast({ message: 'New PB!', type: 'pb' });
      const { toasts } = useUiStore.getState();
      expect(toasts).toHaveLength(1);
      expect(toasts[0].message).toBe('New PB!');
      expect(toasts[0].type).toBe('pb');
    });

    it('assigns a unique string id to each toast', () => {
      useUiStore.getState().addToast({ message: 'First', type: 'info' });
      useUiStore.getState().addToast({ message: 'Second', type: 'info' });
      const { toasts } = useUiStore.getState();
      expect(toasts[0].id).toBeTruthy();
      expect(toasts[1].id).toBeTruthy();
      expect(toasts[0].id).not.toBe(toasts[1].id);
    });

    it('appends toasts in order', () => {
      useUiStore.getState().addToast({ message: 'A', type: 'info' });
      useUiStore.getState().addToast({ message: 'B', type: 'milestone' });
      useUiStore.getState().addToast({ message: 'C', type: 'pb' });
      const { toasts } = useUiStore.getState();
      expect(toasts.map((t) => t.message)).toEqual(['A', 'B', 'C']);
    });

    it('preserves optional duration field', () => {
      useUiStore.getState().addToast({ message: 'Timed', type: 'info', duration: 3000 });
      const { toasts } = useUiStore.getState();
      expect(toasts[0].duration).toBe(3000);
    });

    it('does not affect other state when adding a toast', () => {
      useUiStore.setState({ activeView: 'deep-dive', settingsPanelOpen: true });
      useUiStore.getState().addToast({ message: 'Hi', type: 'info' });
      const state = useUiStore.getState();
      expect(state.activeView).toBe('deep-dive');
      expect(state.settingsPanelOpen).toBe(true);
    });
  });

  // --- removeToast ---

  describe('removeToast', () => {
    it('removes a toast by id', () => {
      useUiStore.getState().addToast({ message: 'Remove me', type: 'info' });
      const { toasts } = useUiStore.getState();
      const id = toasts[0].id;
      useUiStore.getState().removeToast(id);
      expect(useUiStore.getState().toasts).toHaveLength(0);
    });

    it('removes only the targeted toast, leaving others intact', () => {
      useUiStore.getState().addToast({ message: 'Keep', type: 'info' });
      useUiStore.getState().addToast({ message: 'Remove', type: 'pb' });
      useUiStore.getState().addToast({ message: 'Keep too', type: 'milestone' });

      const { toasts } = useUiStore.getState();
      const removeId = toasts[1].id;
      useUiStore.getState().removeToast(removeId);

      const remaining = useUiStore.getState().toasts;
      expect(remaining).toHaveLength(2);
      expect(remaining.map((t) => t.message)).toEqual(['Keep', 'Keep too']);
    });

    it('is a no-op when removing a non-existent id', () => {
      useUiStore.getState().addToast({ message: 'Stay', type: 'info' });
      useUiStore.getState().removeToast('nonexistent-id');
      expect(useUiStore.getState().toasts).toHaveLength(1);
    });

    it('is a no-op on an empty toasts list', () => {
      useUiStore.getState().removeToast('ghost-id');
      expect(useUiStore.getState().toasts).toEqual([]);
    });
  });

  // --- setUploadPromptOpen ---

  describe('setUploadPromptOpen', () => {
    it('opens upload prompt', () => {
      useUiStore.getState().setUploadPromptOpen(true);
      expect(useUiStore.getState().uploadPromptOpen).toBe(true);
    });

    it('closes upload prompt', () => {
      useUiStore.setState({ uploadPromptOpen: true });
      useUiStore.getState().setUploadPromptOpen(false);
      expect(useUiStore.getState().uploadPromptOpen).toBe(false);
    });
  });

  // --- drawer / panel mutual independence ---

  describe('drawer and panel independence', () => {
    it('session drawer and settings panel can be open simultaneously', () => {
      useUiStore.getState().toggleSessionDrawer();
      useUiStore.getState().toggleSettingsPanel();
      const state = useUiStore.getState();
      expect(state.sessionDrawerOpen).toBe(true);
      expect(state.settingsPanelOpen).toBe(true);
    });

    it('closing one panel does not close the other', () => {
      useUiStore.setState({ sessionDrawerOpen: true, settingsPanelOpen: true });
      useUiStore.getState().toggleSessionDrawer(); // close drawer
      const state = useUiStore.getState();
      expect(state.sessionDrawerOpen).toBe(false);
      expect(state.settingsPanelOpen).toBe(true);
    });
  });

  // --- state independence ---

  describe('state independence', () => {
    it('all fields can be set independently without side effects', () => {
      useUiStore.getState().setActiveView('deep-dive');
      useUiStore.getState().setSkillLevel('advanced');
      useUiStore.getState().setUnitPreference('metric');
      useUiStore.getState().toggleSessionDrawer();
      useUiStore.getState().addToast({ message: 'Test toast', type: 'pb' });

      const state = useUiStore.getState();
      expect(state.activeView).toBe('deep-dive');
      expect(state.skillLevel).toBe('advanced');
      expect(state.unitPreference).toBe('metric');
      expect(state.sessionDrawerOpen).toBe(true);
      expect(state.settingsPanelOpen).toBe(false);
      expect(state.toasts).toHaveLength(1);
    });
  });
});
