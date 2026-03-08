import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StickyNote } from '../StickyNote';
import { useStickyStore } from '@/stores/useStickyStore';
import type { StickyViewport } from '@/components/shared/stickies/stickyLayout';

vi.mock('motion/react', () => ({
  motion: {
    div: ({
      children,
      whileHover: _whileHover,
      whileTap: _whileTap,
      drag: _drag,
      dragMomentum: _dragMomentum,
      dragControls: _dragControls,
      dragListener: _dragListener,
      ...props
    }: React.HTMLAttributes<HTMLDivElement> & Record<string, unknown>) => (
      <div {...props}>{children}</div>
    ),
    button: ({
      children,
      whileHover: _whileHover,
      whileTap: _whileTap,
      ...props
    }: React.ButtonHTMLAttributes<HTMLButtonElement> & Record<string, unknown>) => (
      <button {...props}>{children}</button>
    ),
  },
  useDragControls: () => ({ start: vi.fn() }),
}));

const desktopViewport: StickyViewport = {
  width: 1280,
  height: 800,
  isMobile: false,
};

const mobileViewport: StickyViewport = {
  width: 390,
  height: 844,
  isMobile: true,
  safeAreaBottom: 34,
};

function StickyHarness({ isMobile }: { isMobile: boolean }) {
  const sticky = useStickyStore((state) => state.stickies[0]);
  if (!sticky) return null;

  return (
    <StickyNote
      sticky={sticky}
      viewport={isMobile ? mobileViewport : desktopViewport}
      isMobile={isMobile}
      resolveObstacles={() => []}
      onPositionChange={vi.fn()}
      onContentChange={vi.fn()}
      onToneChange={vi.fn()}
      onCollapsedChange={vi.fn()}
      onDelete={(id) => useStickyStore.getState().removeSticky(id)}
    />
  );
}

describe('StickyNote', () => {
  beforeEach(() => {
    useStickyStore.setState({ stickies: [], maxZIndex: 100 });
  });

  it('opens, edits, and closes sticky notes', () => {
    useStickyStore.getState().addSticky(desktopViewport);
    render(<StickyHarness isMobile={false} />);

    fireEvent.click(screen.getByRole('button', { name: 'Open sticky note' }));
    const textarea = screen.getByPlaceholderText('Write a note…');
    fireEvent.change(textarea, { target: { value: 'Braking marker: 2 board' } });
    expect(useStickyStore.getState().stickies[0].text).toBe('Braking marker: 2 board');

    fireEvent.click(screen.getByRole('button', { name: 'Close sticky' }));
    expect(useStickyStore.getState().stickies).toHaveLength(0);
  });

  it('toggles mobile move mode explicitly', () => {
    useStickyStore.getState().addSticky(mobileViewport);
    render(<StickyHarness isMobile />);

    fireEvent.click(screen.getByRole('button', { name: 'Open sticky note' }));
    const moveButton = screen.getByRole('button', { name: 'Move note' });
    fireEvent.click(moveButton);
    expect(useStickyStore.getState().stickies[0].mobileMoveMode).toBe(true);
  });
});
