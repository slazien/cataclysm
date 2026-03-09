export interface StickyViewport {
  width: number;
  height: number;
  isMobile: boolean;
  safeAreaTop?: number;
  safeAreaBottom?: number;
  /** Scroll offset of the content container — positions are page-relative. */
  scrollY?: number;
}

export interface StickyObstacle {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface StickySize {
  width: number;
  height: number;
}

export interface StickyPosition {
  x: number;
  y: number;
}

const EDGE_GUTTER = 20;
const HEADER_RESERVE = 72;
const MOBILE_TAB_RESERVE = 70;
const OBSTACLE_PADDING = 14;

function getInsets(viewport: StickyViewport) {
  return {
    top: HEADER_RESERVE + (viewport.safeAreaTop ?? 0),
    right: EDGE_GUTTER,
    bottom:
      EDGE_GUTTER +
      (viewport.safeAreaBottom ?? 0) +
      (viewport.isMobile ? MOBILE_TAB_RESERVE : 0),
    left: EDGE_GUTTER,
  };
}

export function clampStickyPosition(
  position: StickyPosition,
  size: StickySize,
  viewport: StickyViewport,
): StickyPosition {
  const insets = getInsets(viewport);
  const minX = insets.left;
  const maxX = Math.max(insets.left, viewport.width - size.width - insets.right);

  return {
    x: Math.min(maxX, Math.max(minX, position.x)),
    // Page-relative: only enforce y >= 0, no upper bound (page can be any height)
    y: Math.max(0, position.y),
  };
}

export function snapStickyToRail(
  position: StickyPosition,
  size: StickySize,
  viewport: StickyViewport,
): StickyPosition {
  const clamped = clampStickyPosition(position, size, viewport);
  const insets = getInsets(viewport);
  const scrollY = viewport.scrollY ?? 0;
  const leftX = insets.left;
  const rightX = Math.max(insets.left, viewport.width - size.width - insets.right);
  const topY = scrollY + insets.top;
  const bottomY = Math.max(topY, scrollY + viewport.height - size.height - insets.bottom);

  const distances = viewport.isMobile
    ? ([
        { edge: 'left', value: Math.abs(clamped.x - leftX) },
        { edge: 'right', value: Math.abs(clamped.x - rightX) },
        { edge: 'top', value: Math.abs(clamped.y - topY) },
        { edge: 'bottom', value: Math.abs(clamped.y - bottomY) },
      ] as const)
    : ([
        { edge: 'left', value: Math.abs(clamped.x - leftX) },
        { edge: 'right', value: Math.abs(clamped.x - rightX) },
      ] as const);

  const nearest = distances.reduce((best, current) =>
    current.value < best.value ? current : best,
  );

  if (nearest.edge === 'left') {
    return { x: leftX, y: clamped.y };
  }
  if (nearest.edge === 'right') {
    return { x: rightX, y: clamped.y };
  }
  if (nearest.edge === 'top') {
    return { x: clamped.x, y: topY };
  }
  return { x: clamped.x, y: bottomY };
}

export function getSpawnPosition(
  index: number,
  size: StickySize,
  viewport: StickyViewport,
): StickyPosition {
  const insets = getInsets(viewport);
  const scrollY = viewport.scrollY ?? 0;
  const stackOffset = (index % 6) * 72;
  const leftRailX = insets.left;
  const rightRailX = Math.max(insets.left, viewport.width - size.width - insets.right);
  const y = scrollY + insets.top + 16 + stackOffset;
  const base = {
    x: index % 2 === 0 ? rightRailX : leftRailX,
    y,
  };

  return clampStickyPosition(base, size, viewport);
}

function getOverlapArea(
  position: StickyPosition,
  size: StickySize,
  obstacle: StickyObstacle,
): number {
  const stickyLeft = position.x;
  const stickyTop = position.y;
  const stickyRight = position.x + size.width;
  const stickyBottom = position.y + size.height;

  const obstacleLeft = obstacle.left - OBSTACLE_PADDING;
  const obstacleTop = obstacle.top - OBSTACLE_PADDING;
  const obstacleRight = obstacle.right + OBSTACLE_PADDING;
  const obstacleBottom = obstacle.bottom + OBSTACLE_PADDING;

  const overlapWidth = Math.max(
    0,
    Math.min(stickyRight, obstacleRight) - Math.max(stickyLeft, obstacleLeft),
  );
  const overlapHeight = Math.max(
    0,
    Math.min(stickyBottom, obstacleBottom) - Math.max(stickyTop, obstacleTop),
  );

  return overlapWidth * overlapHeight;
}

function totalOverlapArea(
  position: StickyPosition,
  size: StickySize,
  obstacles: StickyObstacle[],
): number {
  return obstacles.reduce((total, obstacle) => total + getOverlapArea(position, size, obstacle), 0);
}

function dedupePositions(positions: StickyPosition[]): StickyPosition[] {
  const seen = new Set<string>();
  const result: StickyPosition[] = [];

  for (const position of positions) {
    const key = `${Math.round(position.x)}:${Math.round(position.y)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(position);
  }

  return result;
}

export function avoidStickyObstacles(
  position: StickyPosition,
  size: StickySize,
  viewport: StickyViewport,
  obstacles: StickyObstacle[],
): StickyPosition {
  if (obstacles.length === 0) {
    return clampStickyPosition(position, size, viewport);
  }

  const clamped = clampStickyPosition(position, size, viewport);
  const normalizedObstacles = obstacles
    .filter((obstacle) => obstacle.right > obstacle.left && obstacle.bottom > obstacle.top)
    .map((obstacle) => clampObstacleToViewport(obstacle, viewport));

  if (normalizedObstacles.length === 0) {
    return clamped;
  }

  if (totalOverlapArea(clamped, size, normalizedObstacles) === 0) {
    return clamped;
  }

  const margin = OBSTACLE_PADDING + 8;
  const candidates: StickyPosition[] = [clamped, snapStickyToRail(clamped, size, viewport)];

  for (const obstacle of normalizedObstacles) {
    const aroundObstacle = [
      { x: obstacle.left - size.width - margin, y: clamped.y },
      { x: obstacle.right + margin, y: clamped.y },
      { x: clamped.x, y: obstacle.top - size.height - margin },
      { x: clamped.x, y: obstacle.bottom + margin },
      { x: obstacle.left - size.width - margin, y: obstacle.top - size.height - margin },
      { x: obstacle.right + margin, y: obstacle.top - size.height - margin },
      { x: obstacle.left - size.width - margin, y: obstacle.bottom + margin },
      { x: obstacle.right + margin, y: obstacle.bottom + margin },
    ];

    for (const candidate of aroundObstacle) {
      candidates.push(clampStickyPosition(candidate, size, viewport));
    }
  }

  const uniqueCandidates = dedupePositions(candidates);
  const scored = uniqueCandidates.map((candidate) => {
    const overlap = totalOverlapArea(candidate, size, normalizedObstacles);
    const distance = Math.hypot(candidate.x - clamped.x, candidate.y - clamped.y);
    return {
      candidate,
      score: overlap * 10_000 + distance,
      overlap,
    };
  });

  scored.sort((a, b) => a.score - b.score);
  const best = scored[0];
  if (!best) {
    return snapStickyToRail(clamped, size, viewport);
  }

  if (best.overlap > 0) {
    return snapStickyToRail(clamped, size, viewport);
  }

  return best.candidate;
}

function clampObstacleToViewport(
  obstacle: StickyObstacle,
  viewport: StickyViewport,
): StickyObstacle {
  const scrollY = viewport.scrollY ?? 0;
  return {
    left: Math.max(0, Math.min(viewport.width, obstacle.left)),
    top: Math.max(0, Math.min(scrollY + viewport.height, obstacle.top)),
    right: Math.max(0, Math.min(viewport.width, obstacle.right)),
    bottom: Math.max(0, Math.min(scrollY + viewport.height, obstacle.bottom)),
  };
}
