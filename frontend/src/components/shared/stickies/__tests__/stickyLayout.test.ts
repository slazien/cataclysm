import { describe, expect, it } from 'vitest';
import {
  avoidStickyObstacles,
  clampStickyPosition,
  getSpawnPosition,
  snapStickyToRail,
  type StickyObstacle,
  type StickyViewport,
} from '@/components/shared/stickies/stickyLayout';

describe('stickyLayout', () => {
  const desktopViewport: StickyViewport = {
    width: 1440,
    height: 900,
    isMobile: false,
  };

  const mobileViewport: StickyViewport = {
    width: 390,
    height: 844,
    isMobile: true,
    safeAreaBottom: 34,
  };

  it('clamps X to viewport bounds, allows page-relative Y beyond viewport', () => {
    const clamped = clampStickyPosition(
      { x: -120, y: 1200 },
      { width: 280, height: 220 },
      desktopViewport,
    );

    expect(clamped.x).toBeGreaterThanOrEqual(0);
    expect(clamped.y).toBeGreaterThanOrEqual(0);
    expect(clamped.x).toBeLessThanOrEqual(desktopViewport.width - 280);
    // Y is page-relative — can exceed viewport height (sticky scrolls with content)
    expect(clamped.y).toBe(1200);
  });

  it('snaps centered sticky positions to an edge rail to avoid central data obstruction', () => {
    const snapped = snapStickyToRail(
      { x: 640, y: 320 },
      { width: 280, height: 220 },
      desktopViewport,
    );

    const atLeft = snapped.x <= 32;
    const atRight = snapped.x >= desktopViewport.width - 280 - 32;
    const atTop = snapped.y <= 32;
    const atBottom = snapped.y >= desktopViewport.height - 220 - 32;

    expect(atLeft || atRight || atTop || atBottom).toBe(true);
  });

  it('spawns desktop stickies on safe edge rails instead of the chart center', () => {
    const first = getSpawnPosition(0, { width: 280, height: 220 }, desktopViewport);

    const atLeftRail = first.x <= 48;
    const atRightRail = first.x >= desktopViewport.width - 280 - 48;
    expect(atLeftRail || atRightRail).toBe(true);
    expect(first.y).toBeGreaterThan(48);
  });

  it('spawns mobile stickies within visible area', () => {
    const first = getSpawnPosition(0, { width: 272, height: 208 }, mobileViewport);

    // Spawns with Y >= header reserve
    expect(first.y).toBeGreaterThan(48);
    expect(first.x).toBeGreaterThanOrEqual(0);
    expect(first.x).toBeLessThanOrEqual(mobileViewport.width - 272);
  });

  it('nudges stickies outside protected obstacle regions after placement', () => {
    const obstacle: StickyObstacle = {
      left: 420,
      top: 180,
      right: 980,
      bottom: 620,
    };

    const adjusted = avoidStickyObstacles(
      { x: 560, y: 320 },
      { width: 292, height: 230 },
      desktopViewport,
      [obstacle],
    );

    const overlapsX = adjusted.x < obstacle.right && adjusted.x + 292 > obstacle.left;
    const overlapsY = adjusted.y < obstacle.bottom && adjusted.y + 230 > obstacle.top;
    expect(overlapsX && overlapsY).toBe(false);
  });
});
