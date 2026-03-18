'use client';

import { useMemo, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMultiLapData } from '@/hooks/useAnalysis';
import { useAnalysisStore } from '@/stores';
import { useIsMobile } from '@/hooks/useMediaQuery';
import { colors } from '@/lib/design-tokens';
import {
  computeProjection,
  applyProjection,
  interpolateCursorPosition,
  computeGhostDistance,
} from '@/lib/trackProjection';

const MINI_W = 144;
const MINI_H = 96;
const MINI_PAD = 6;
/** Delay (ms) before the overlay starts fading out after the cursor clears. */
const FADE_OUT_DELAY_MS = 600;
/** Duration (ms) of the opacity/scale transition itself. */
const TRANSITION_MS = 200;

interface MiniTrackMapProps {
  sessionId: string;
  /** Ref to the main track map container — used to detect when it scrolls out of view. */
  trackMapRef: React.RefObject<HTMLDivElement | null>;
}

/**
 * Lightweight floating mini-map overlay for mobile.
 *
 * Appears at bottom-left when:
 *  1. viewport < 1024px (mobile)
 *  2. the main track map is scrolled out of view
 *  3. the user is actively scrubbing (cursorDistance !== null)
 *
 * Shows the track outline + animated cursor dot.
 * Uses CSS transition-delay for the fade-out linger (no JS timers).
 */
export function MiniTrackMap({ sessionId, trackMapRef }: MiniTrackMapProps) {
  const isMobile = useIsMobile();
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const cursorDistance = useAnalysisStore((s) => s.cursorDistance);

  // Track whether the main map is out of viewport
  const [mapOutOfView, setMapOutOfView] = useState(false);

  useEffect(() => {
    const el = trackMapRef.current;
    if (!el || !isMobile) return;
    const observer = new IntersectionObserver(
      ([entry]) => setMapOutOfView(!entry.isIntersecting),
      { threshold: 0.1 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [trackMapRef, isMobile]);

  // Derive visibility from state — CSS handles the delayed fade-out
  const shouldShow = isMobile && mapOutOfView && cursorDistance !== null;

  // Fetch lap data — React Query deduplicates with the main TrackMapInteractive
  const { data: lapDataArr } = useMultiLapData(sessionId, selectedLaps);
  const lapData = lapDataArr?.[0] ?? null;
  const compLapData = lapDataArr && lapDataArr.length >= 2 ? lapDataArr[1] : null;

  // Build simplified track outline (single polyline, no segments/colors)
  const { projected, polyline, compProjected } = useMemo(() => {
    if (!lapData) return { projected: null, polyline: null, compProjected: null };

    // Include both laps in projection bounds for consistent coordinate frame
    const allLats = compLapData ? [lapData.lat, compLapData.lat] : [lapData.lat];
    const allLons = compLapData ? [lapData.lon, compLapData.lon] : [lapData.lon];
    const proj = computeProjection(allLats, allLons, MINI_W, MINI_H, MINI_PAD);
    if (!proj) return { projected: null, polyline: null, compProjected: null };

    const pts = applyProjection(lapData.lat, lapData.lon, proj);
    if (pts.x.length < 2) return { projected: null, polyline: null, compProjected: null };

    // Downsample for performance — keep every Nth point
    const step = Math.max(1, Math.floor(pts.x.length / 200));
    const coords: string[] = [];
    for (let i = 0; i < pts.x.length; i += step) {
      coords.push(`${pts.x[i].toFixed(1)},${pts.y[i].toFixed(1)}`);
    }
    // Always include last point to close the shape visually
    const last = pts.x.length - 1;
    coords.push(`${pts.x[last].toFixed(1)},${pts.y[last].toFixed(1)}`);

    // Project comp lap for ghost dot interpolation
    let compProj: { x: number[]; y: number[] } | null = null;
    if (compLapData) {
      compProj = applyProjection(compLapData.lat, compLapData.lon, proj);
    }

    return { projected: pts, polyline: 'M' + coords.join('L'), compProjected: compProj };
  }, [lapData, compLapData]);

  const isComparing = compLapData !== null;

  // Interpolate cursor position on the projected track
  const cursorPos = useMemo(() => {
    if (cursorDistance === null || !lapData || !projected) return null;
    return interpolateCursorPosition(cursorDistance, lapData, projected);
  }, [cursorDistance, lapData, projected]);

  // Ghost dot for comparison lap
  const ghostPos = useMemo(() => {
    if (cursorDistance === null || !lapData || !compLapData || !compProjected) return null;
    const ghostDist = computeGhostDistance(cursorDistance, lapData, compLapData);
    if (ghostDist === null) return null;
    return interpolateCursorPosition(ghostDist, compLapData, compProjected);
  }, [cursorDistance, lapData, compLapData, compProjected]);

  // Don't render anything on desktop or when we have no data
  // DEBUG: temporarily show diagnostic badge on mobile even without polyline
  const hasData = Boolean(polyline);
  if (!isMobile) return null;

  // CSS transition: instant appear (0ms delay), delayed disappear (600ms delay).
  // The transition-delay on hide gives a "linger" effect purely in CSS.
  const transition = shouldShow
    ? `opacity ${TRANSITION_MS}ms ease-out, transform ${TRANSITION_MS}ms ease-out`
    : `opacity ${TRANSITION_MS}ms ease-out ${FADE_OUT_DELAY_MS}ms, transform ${TRANSITION_MS}ms ease-out ${FADE_OUT_DELAY_MS}ms`;

  // Portal to document.body so position:fixed works correctly.
  // ViewRouter's motion.div keeps transform:translateY(0) after animation,
  // which creates a containing block and breaks position:fixed on descendants.
  return createPortal(
    <>
      {/* DEBUG: visible diagnostic badge — remove after confirming fix */}
      <div
        className="pointer-events-none fixed z-[9999] left-3 bottom-[calc(8rem+env(safe-area-inset-bottom))]"
        style={{ fontSize: 10, fontFamily: 'monospace', color: '#fff', background: 'rgba(0,0,0,0.8)', padding: '2px 6px', borderRadius: 4 }}
      >
        mob:{isMobile ? '✓' : '✗'} oov:{mapOutOfView ? '✓' : '✗'} cur:{cursorDistance !== null ? '✓' : '✗'} data:{hasData ? '✓' : '✗'}
      </div>
      {hasData && <div
      aria-hidden="true"
      className={`
        pointer-events-none fixed z-30 rounded-lg border border-white/10
        bg-[var(--bg-surface)]/70 shadow-2xl backdrop-blur-xl
        will-change-[transform,opacity]
        bottom-[calc(5rem+env(safe-area-inset-bottom))] left-3
      `}
      style={{
        width: MINI_W,
        height: MINI_H,
        opacity: shouldShow ? 1 : 0,
        transform: shouldShow ? 'scale(1)' : 'scale(0.95)',
        transition,
      }}
    >
      <svg
        viewBox={`0 0 ${MINI_W} ${MINI_H}`}
        width={MINI_W}
        height={MINI_H}
        className="block"
      >
        {/* Track outline */}
        <path
          d={polyline!}
          fill="none"
          stroke={colors.text.secondary}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Ghost dot (comparison lap) */}
        {ghostPos && (
          <circle
            cx={ghostPos.cx}
            cy={ghostPos.cy}
            r={3}
            fill={colors.comparison.compare}
            stroke="#fff"
            strokeWidth={1}
            opacity={0.7}
          >
            <animate
              attributeName="r"
              values="2;4;2"
              dur="1s"
              repeatCount="indefinite"
            />
          </circle>
        )}

        {/* Cursor dot — blue when comparing, green when single lap */}
        {cursorPos && (
          <circle
            cx={cursorPos.cx}
            cy={cursorPos.cy}
            r={4}
            fill={isComparing ? colors.comparison.reference : colors.motorsport.optimal}
            stroke="#fff"
            strokeWidth={1.5}
          >
            <animate
              attributeName="r"
              values="3;5;3"
              dur="1s"
              repeatCount="indefinite"
            />
          </circle>
        )}
      </svg>
    </div>}
    </>,
    document.body,
  );
}
