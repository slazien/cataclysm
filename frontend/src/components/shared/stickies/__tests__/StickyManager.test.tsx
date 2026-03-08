import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StickyManager } from '../StickyManager';
import { useStickyStore } from '@/stores/useStickyStore';

function stripMotionProps(props: Record<string, unknown>) {
  const domProps = { ...props };
  delete domProps.whileHover;
  delete domProps.whileTap;
  delete domProps.drag;
  delete domProps.dragMomentum;
  delete domProps.dragControls;
  delete domProps.dragListener;
  return domProps;
}

vi.mock('motion/react', () => ({
  motion: {
    div: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement> & Record<string, unknown>) => (
      <div {...stripMotionProps(props)}>{children}</div>
    ),
    button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & Record<string, unknown>) => (
      <button {...stripMotionProps(props)}>{children}</button>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useDragControls: () => ({ start: vi.fn() }),
}));

vi.mock('@/hooks/useMediaQuery', () => ({
  useIsMobile: () => false,
}));

const stableApiData = { items: [], total: 0 };
const stableMutate = vi.fn();

vi.mock('@/hooks/useStickies', () => ({
  useStickies: () => ({ data: stableApiData }),
  useCreateSticky: () => ({ mutate: stableMutate }),
  useUpdateSticky: () => ({ mutate: vi.fn() }),
  useDeleteSticky: () => ({ mutate: vi.fn() }),
}));

describe('StickyManager', () => {
  beforeEach(() => {
    useStickyStore.setState({ stickies: [], maxZIndex: 100, hydrated: false });
  });

  it('adds a sticky when the add button is pressed', async () => {
    render(<StickyManager />);

    const addButton = await screen.findByRole('button', { name: 'Create sticky note' });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(useStickyStore.getState().stickies).toHaveLength(1);
    });
  });
});
