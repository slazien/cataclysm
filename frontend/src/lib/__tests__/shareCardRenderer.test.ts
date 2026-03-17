import { describe, expect, it, vi, beforeEach } from 'vitest';

import { getShareScoreDisplay, renderSessionCard } from '../shareCardRenderer';
import type { ShareCardData } from '../shareCardRenderer';

// ---------------------------------------------------------------------------
// Mock QRCode module
// ---------------------------------------------------------------------------
vi.mock('qrcode', () => ({
  default: {
    toDataURL: vi.fn().mockResolvedValue('data:image/png;base64,MOCK'),
  },
}));

// ---------------------------------------------------------------------------
// Canvas context mock factory
// ---------------------------------------------------------------------------
function createMockCtx(): CanvasRenderingContext2D {
  const ctx = {
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
    globalAlpha: 1,
    shadowColor: '',
    shadowBlur: 0,
    font: '',
    textAlign: '',
    textBaseline: '',
    lineCap: '',
    fillRect: vi.fn(),
    strokeRect: vi.fn(),
    fillText: vi.fn(),
    strokeText: vi.fn(),
    beginPath: vi.fn(),
    closePath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    arc: vi.fn(),
    stroke: vi.fn(),
    fill: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    createLinearGradient: vi.fn().mockReturnValue({
      addColorStop: vi.fn(),
    }),
    roundRect: vi.fn(),
    drawImage: vi.fn(),
  } as unknown as CanvasRenderingContext2D;
  return ctx;
}

// ---------------------------------------------------------------------------
// Mock Image constructor for drawQRCode
// ---------------------------------------------------------------------------
class MockImage {
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  _src = '';
  set src(val: string) {
    this._src = val;
    // Simulate async image load
    setTimeout(() => {
      if (this.onload) this.onload();
    }, 0);
  }
  get src() {
    return this._src;
  }
}
vi.stubGlobal('Image', MockImage);

// ---------------------------------------------------------------------------
// getShareScoreDisplay
// ---------------------------------------------------------------------------

describe('getShareScoreDisplay', () => {
  it('formats share scores on a 0-100 scale', () => {
    const display = getShareScoreDisplay(87.6);
    expect(display.fraction).toBeCloseTo(0.876, 6);
    expect(display.valueText).toBe('88');
    expect(display.scaleText).toBe('/ 100');
  });

  it('clamps out-of-range scores without changing the scale label', () => {
    expect(getShareScoreDisplay(140)).toEqual({
      fraction: 1,
      valueText: '100',
      scaleText: '/ 100',
    });
  });

  it('clamps negative scores to 0', () => {
    const display = getShareScoreDisplay(-10);
    expect(display.fraction).toBe(0);
    expect(display.valueText).toBe('0');
    expect(display.scaleText).toBe('/ 100');
  });

  it('handles zero score', () => {
    const display = getShareScoreDisplay(0);
    expect(display.fraction).toBe(0);
    expect(display.valueText).toBe('0');
  });

  it('handles exact 100', () => {
    const display = getShareScoreDisplay(100);
    expect(display.fraction).toBe(1);
    expect(display.valueText).toBe('100');
  });

  it('rounds the value text to nearest integer', () => {
    const display = getShareScoreDisplay(50.4);
    expect(display.valueText).toBe('50');
    const display2 = getShareScoreDisplay(50.5);
    expect(display2.valueText).toBe('51');
  });

  it('computes fraction correctly for typical score', () => {
    const display = getShareScoreDisplay(75);
    expect(display.fraction).toBeCloseTo(0.75, 6);
  });
});

// ---------------------------------------------------------------------------
// renderSessionCard
// ---------------------------------------------------------------------------

describe('renderSessionCard', () => {
  let mockCtx: CanvasRenderingContext2D;
  let canvas: HTMLCanvasElement;

  const baseData: ShareCardData = {
    trackName: 'Barber Motorsports Park',
    sessionDate: '2026-03-01',
    bestLapTime: 92.456,
    sessionScore: 85,
    nLaps: 15,
    consistencyScore: 0.92,
    identityLabel: 'BRAKE BOSS',
    topSpeed: 142,
    speedUnit: 'mph',
    skillDimensions: {
      braking: 90,
      trailBraking: 75,
      throttle: 80,
      line: 70,
    },
    viewUrl: 'https://cataclysm.app/view/abc123',
  };

  beforeEach(() => {
    mockCtx = createMockCtx();
    canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn().mockReturnValue(mockCtx),
    } as unknown as HTMLCanvasElement;
  });

  it('sets canvas dimensions to 1080x1620', async () => {
    await renderSessionCard(canvas, baseData);
    expect(canvas.width).toBe(1080);
    expect(canvas.height).toBe(1620);
  });

  it('calls getContext with 2d', async () => {
    await renderSessionCard(canvas, baseData);
    expect(canvas.getContext).toHaveBeenCalledWith('2d');
  });

  it('throws when canvas context is null', async () => {
    const badCanvas = {
      width: 0,
      height: 0,
      getContext: vi.fn().mockReturnValue(null),
    } as unknown as HTMLCanvasElement;
    await expect(renderSessionCard(badCanvas, baseData)).rejects.toThrow(
      'Could not get 2d canvas context',
    );
  });

  it('draws background gradient', async () => {
    await renderSessionCard(canvas, baseData);
    expect(mockCtx.createLinearGradient).toHaveBeenCalled();
    // fillRect is called many times (background + grain texture pixels)
    expect(mockCtx.fillRect).toHaveBeenCalled();
  });

  it('draws track name and date at top', async () => {
    await renderSessionCard(canvas, baseData);
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'Barber Motorsports Park',
      expect.any(Number),
      expect.any(Number),
    );
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      '2026-03-01',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('draws identity label', async () => {
    await renderSessionCard(canvas, baseData);
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'BRAKE BOSS',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('draws score ring when sessionScore is present', async () => {
    await renderSessionCard(canvas, baseData);
    // arc is called for the background ring and score arc
    expect(mockCtx.arc).toHaveBeenCalled();
    // Score value text is drawn
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      '85',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('draws best lap time when present', async () => {
    await renderSessionCard(canvas, baseData);
    // formatLapTime(92.456) = "1:32.456"
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      '1:32.456',
      expect.any(Number),
      expect.any(Number),
    );
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'BEST LAP',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('draws stat pills for laps, consistency, and top speed', async () => {
    await renderSessionCard(canvas, baseData);
    // Laps pill
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      '15',
      expect.any(Number),
      expect.any(Number),
    );
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'LAPS',
      expect.any(Number),
      expect.any(Number),
    );
    // Consistency pill: Math.round(0.92 * 100) = 92
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      '92%',
      expect.any(Number),
      expect.any(Number),
    );
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'CONSISTENCY',
      expect.any(Number),
      expect.any(Number),
    );
    // Top speed pill
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      '142 mph',
      expect.any(Number),
      expect.any(Number),
    );
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'TOP SPEED',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('draws skill radar when skillDimensions is present', async () => {
    await renderSessionCard(canvas, baseData);
    // The radar draws axis labels
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'Braking',
      expect.any(Number),
      expect.any(Number),
    );
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'Trail Braking',
      expect.any(Number),
      expect.any(Number),
    );
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'Throttle',
      expect.any(Number),
      expect.any(Number),
    );
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'Line',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('draws QR code when viewUrl is present', async () => {
    await renderSessionCard(canvas, baseData);
    // drawImage is called for the QR code image
    expect(mockCtx.drawImage).toHaveBeenCalled();
    // CTA text under QR code
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      'Scan to view full analysis',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('draws footer CTA', async () => {
    await renderSessionCard(canvas, baseData);
    expect(mockCtx.fillText).toHaveBeenCalledWith(
      expect.stringContaining('cataclysm.app'),
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('skips score ring when sessionScore is null', async () => {
    const data = { ...baseData, sessionScore: null };
    mockCtx.arc = vi.fn(); // reset to track calls from this specific render
    await renderSessionCard(canvas, data);
    // arc should not be called for score ring (only for radar if present)
    // Actually the radar uses beginPath/lineTo not arc, so arc count tells us score ring
    // With no score, arc should not be called
    expect(mockCtx.arc).not.toHaveBeenCalled();
  });

  it('skips best lap time when null', async () => {
    const data = { ...baseData, bestLapTime: null };
    await renderSessionCard(canvas, data);
    expect(mockCtx.fillText).not.toHaveBeenCalledWith(
      'BEST LAP',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('skips consistency pill when null', async () => {
    const data = { ...baseData, consistencyScore: null };
    await renderSessionCard(canvas, data);
    expect(mockCtx.fillText).not.toHaveBeenCalledWith(
      'CONSISTENCY',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('skips top speed pill when null', async () => {
    const data = { ...baseData, topSpeed: null };
    await renderSessionCard(canvas, data);
    expect(mockCtx.fillText).not.toHaveBeenCalledWith(
      'TOP SPEED',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('skips skill radar when skillDimensions is null', async () => {
    const data = { ...baseData, skillDimensions: null };
    await renderSessionCard(canvas, data);
    expect(mockCtx.fillText).not.toHaveBeenCalledWith(
      'Braking',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('skips QR code when viewUrl is null', async () => {
    const data = { ...baseData, viewUrl: null };
    mockCtx.drawImage = vi.fn();
    await renderSessionCard(canvas, data);
    expect(mockCtx.drawImage).not.toHaveBeenCalled();
    expect(mockCtx.fillText).not.toHaveBeenCalledWith(
      'Scan to view full analysis',
      expect.any(Number),
      expect.any(Number),
    );
  });

  it('draws track glow when gpsCoords has >10 points', async () => {
    const lat = Array.from({ length: 50 }, (_, i) => 33.5 + i * 0.001);
    const lon = Array.from({ length: 50 }, (_, i) => -86.6 + i * 0.001);
    const data = { ...baseData, gpsCoords: { lat, lon } };
    mockCtx.stroke = vi.fn();
    await renderSessionCard(canvas, data);
    // Track glow calls stroke for the track outline
    expect(mockCtx.stroke).toHaveBeenCalled();
    expect(mockCtx.moveTo).toHaveBeenCalled();
    expect(mockCtx.lineTo).toHaveBeenCalled();
  });

  it('skips track glow when gpsCoords has <10 points', async () => {
    const lat = [33.5, 33.6, 33.7];
    const lon = [-86.6, -86.5, -86.4];
    const data = { ...baseData, gpsCoords: { lat, lon } };
    // The drawTrackGlow function early returns if lat.length < 10
    // It should still complete without error
    await renderSessionCard(canvas, data);
  });

  it('skips track glow when gpsCoords is undefined', async () => {
    const data = { ...baseData, gpsCoords: undefined };
    await renderSessionCard(canvas, data);
    // Should complete without error
  });

  it('renders minimal data card without errors', async () => {
    const minimalData: ShareCardData = {
      trackName: 'Test Track',
      sessionDate: '2026-01-01',
      bestLapTime: null,
      sessionScore: null,
      nLaps: 5,
      consistencyScore: null,
      identityLabel: 'TRACK WARRIOR',
      topSpeed: null,
      speedUnit: 'mph',
      skillDimensions: null,
      viewUrl: null,
    };
    await renderSessionCard(canvas, minimalData);
    expect(canvas.width).toBe(1080);
    expect(canvas.height).toBe(1620);
  });
});
