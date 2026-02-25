'use client';

import { useCallback, useRef, useState } from 'react';

export interface ChartMargins {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface ChartDimensions {
  width: number;
  height: number;
  innerWidth: number;
  innerHeight: number;
  margins: ChartMargins;
  dpr: number;
}

const DEFAULT_MARGINS: ChartMargins = { top: 20, right: 20, bottom: 40, left: 60 };

/**
 * Hook that manages a dual-canvas chart setup:
 * - dataCanvas: static data layer (speed traces, fills, etc.)
 * - overlayCanvas: interactive overlay (cursor line, tooltips, highlights)
 *
 * Uses a callback ref for the container so the ResizeObserver is set up
 * whenever the container element mounts — even if conditional rendering
 * delays the mount (e.g. components with early-return guards).
 */
export function useCanvasChart(margins: ChartMargins = DEFAULT_MARGINS) {
  const dataCanvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const observerRef = useRef<ResizeObserver | null>(null);

  const [dimensions, setDimensions] = useState<ChartDimensions>({
    width: 0,
    height: 0,
    innerWidth: 0,
    innerHeight: 0,
    margins,
    dpr: typeof window !== 'undefined' ? window.devicePixelRatio : 1,
  });

  // Resize handler: updates canvas sizes and dimensions state
  const handleResize = useCallback(
    (entries: ResizeObserverEntry[]) => {
      const entry = entries[0];
      if (!entry) return;

      const { width, height } = entry.contentRect;
      const dpr = window.devicePixelRatio || 1;
      const innerWidth = Math.max(0, width - margins.left - margins.right);
      const innerHeight = Math.max(0, height - margins.top - margins.bottom);

      // Scale both canvases for HiDPI
      for (const canvasRef of [dataCanvasRef, overlayCanvasRef]) {
        const canvas = canvasRef.current;
        if (!canvas) continue;

        canvas.width = width * dpr;
        canvas.height = height * dpr;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
      }

      setDimensions({ width, height, innerWidth, innerHeight, margins, dpr });
    },
    [margins],
  );

  // Callback ref for the container element.
  // Sets up / tears down the ResizeObserver whenever the element mounts or unmounts.
  const containerRef = useCallback(
    (el: HTMLDivElement | null) => {
      // Tear down previous observer
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }

      if (!el) return;

      const observer = new ResizeObserver(handleResize);
      observer.observe(el);
      observerRef.current = observer;

      // Perform an initial measurement imperatively since ResizeObserver
      // may not fire synchronously on mount, leaving the canvas at 0x0.
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        handleResize([{ contentRect: rect } as ResizeObserverEntry]);
      }
    },
    [handleResize],
  );

  // Context getters
  const getDataCtx = useCallback(() => {
    return dataCanvasRef.current?.getContext('2d') ?? null;
  }, []);

  const getOverlayCtx = useCallback(() => {
    return overlayCanvasRef.current?.getContext('2d') ?? null;
  }, []);

  return {
    containerRef,
    dataCanvasRef,
    overlayCanvasRef,
    dimensions,
    getDataCtx,
    getOverlayCtx,
  };
}
