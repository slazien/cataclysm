import { beforeEach, describe, expect, it } from 'vitest';
import { useStickyStore } from '@/stores/useStickyStore';
import type {
  StickyObstacle,
  StickyViewport,
} from '@/components/shared/stickies/stickyLayout';

describe('useStickyStore', () => {
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

  beforeEach(() => {
    useStickyStore.setState({
      stickies: [],
      maxZIndex: 100,
    });
  });

  it('adds new stickies collapsed by default and positioned on a safe rail', () => {
    useStickyStore.getState().addSticky(desktopViewport);
    const sticky = useStickyStore.getState().stickies[0];

    expect(sticky).toBeDefined();
    expect(sticky.collapsed).toBe(true);
    expect(sticky.x <= 48 || sticky.x >= desktopViewport.width - sticky.width - 48).toBe(
      true,
    );
  });

  it('moves stickies with rail snapping when requested', () => {
    useStickyStore.getState().addSticky(desktopViewport);
    const id = useStickyStore.getState().stickies[0].id;

    useStickyStore
      .getState()
      .moveSticky(id, { x: 620, y: 300 }, desktopViewport, { snapToRail: true });

    const sticky = useStickyStore.getState().stickies[0];
    const atLeft = sticky.x <= 48;
    const atRight = sticky.x >= desktopViewport.width - sticky.width - 48;
    expect(atLeft || atRight).toBe(true);
  });

  it('keeps mobile stickies in move mode only when explicitly toggled', () => {
    useStickyStore.getState().addSticky(mobileViewport);
    const id = useStickyStore.getState().stickies[0].id;

    expect(useStickyStore.getState().stickies[0].mobileMoveMode).toBe(false);
    useStickyStore.getState().setMobileMoveMode(id, true);
    expect(useStickyStore.getState().stickies[0].mobileMoveMode).toBe(true);
    useStickyStore.getState().setMobileMoveMode(id, false);
    expect(useStickyStore.getState().stickies[0].mobileMoveMode).toBe(false);
  });

  it('repositions dropped stickies away from protected obstacles', () => {
    useStickyStore.getState().addSticky(desktopViewport);
    const sticky = useStickyStore.getState().stickies[0];
    const obstacle: StickyObstacle = {
      left: 420,
      top: 180,
      right: 980,
      bottom: 620,
    };

    useStickyStore.getState().moveSticky(
      sticky.id,
      { x: 620, y: 300 },
      desktopViewport,
      { avoidObstacles: [obstacle] },
    );

    const moved = useStickyStore.getState().stickies[0];
    const overlapsX = moved.x < obstacle.right && moved.x + moved.width > obstacle.left;
    const overlapsY = moved.y < obstacle.bottom && moved.y + moved.height > obstacle.top;
    expect(overlapsX && overlapsY).toBe(false);
  });
});
