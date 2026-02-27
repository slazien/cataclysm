'use client';

import { useEffect, useRef } from 'react';
import { colors, fonts } from '@/lib/design-tokens';

interface GForceDisplayProps {
  lateralG: number;
  longitudinalG: number;
  /** Previous positions for the short trail (most recent last). */
  trail: Array<{ lat: number; lon: number }>;
}

const CANVAS_SIZE = 200;
const MAX_G = 2.0;

/**
 * 2D g-force scatter plot rendered on canvas.
 *
 * - Circular boundary representing MAX_G
 * - Cross-hair gridlines through center
 * - Quadrant labels: Brake (top) / Accel (bottom) / Left / Right
 * - Current dot with a short fading trail of recent positions
 */
export function GForceDisplay({ lateralG, longitudinalG, trail }: GForceDisplayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const rect = container.getBoundingClientRect();
    const size = Math.min(rect.width, rect.height) || CANVAS_SIZE;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const cx = size / 2;
    const cy = size / 2;
    const r = (size - 40) / 2;

    ctx.clearRect(0, 0, size, size);

    // Circular boundary
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = colors.text.muted;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.3;
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Inner rings at 0.5g, 1.0g, 1.5g
    for (const gVal of [0.5, 1.0, 1.5]) {
      const ringR = (gVal / MAX_G) * r;
      ctx.beginPath();
      ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
      ctx.strokeStyle = colors.text.muted;
      ctx.lineWidth = 0.5;
      ctx.globalAlpha = 0.15;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Cross-hairs
    ctx.beginPath();
    ctx.moveTo(cx - r, cy);
    ctx.lineTo(cx + r, cy);
    ctx.moveTo(cx, cy - r);
    ctx.lineTo(cx, cy + r);
    ctx.strokeStyle = colors.text.muted;
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.25;
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Quadrant labels
    ctx.font = `10px ${fonts.sans}`;
    ctx.textAlign = 'center';
    ctx.fillStyle = colors.text.muted;
    ctx.globalAlpha = 0.6;
    ctx.fillText('Brake', cx, cy - r - 6);
    ctx.fillText('Accel', cx, cy + r + 14);
    ctx.fillText('L', cx - r - 10, cy + 4);
    ctx.fillText('R', cx + r + 10, cy + 4);
    ctx.globalAlpha = 1;

    // Trail
    const gToPixel = (g: number) => (g / MAX_G) * r;
    const trailLen = trail.length;
    for (let i = 0; i < trailLen; i++) {
      const alpha = ((i + 1) / trailLen) * 0.5;
      const px = cx + gToPixel(trail[i].lat); // lateral -> X
      const py = cy - gToPixel(trail[i].lon); // longitudinal -> Y (brake = up = negative Y)
      ctx.beginPath();
      ctx.arc(px, py, 2, 0, Math.PI * 2);
      ctx.fillStyle = colors.motorsport.optimal;
      ctx.globalAlpha = alpha;
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Current dot
    const dotX = cx + gToPixel(lateralG);
    const dotY = cy - gToPixel(longitudinalG);

    // Glow
    const gradient = ctx.createRadialGradient(dotX, dotY, 0, dotX, dotY, 10);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.5)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');
    ctx.beginPath();
    ctx.arc(dotX, dotY, 10, 0, Math.PI * 2);
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(dotX, dotY, 4, 0, Math.PI * 2);
    ctx.fillStyle = colors.motorsport.optimal;
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }, [lateralG, longitudinalG, trail]);

  return (
    <div ref={containerRef} className="flex items-center justify-center">
      <canvas ref={canvasRef} style={{ width: CANVAS_SIZE, height: CANVAS_SIZE }} />
    </div>
  );
}
