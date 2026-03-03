import { formatLapTime } from './formatters';

export interface ShareCardData {
  trackName: string;
  sessionDate: string;
  bestLapTime: number | null;
  sessionScore: number | null;
  nLaps: number;
  consistencyScore: number | null;
  identityLabel: string;
  gpsCoords?: { lat: number[]; lon: number[] };
}

const CARD_W = 1080;
const CARD_H = 1920;
const ACCENT = '#6366f1';
const ACCENT_GLOW = 'rgba(99, 102, 241, 0.4)';

function drawBackground(ctx: CanvasRenderingContext2D): void {
  const grad = ctx.createLinearGradient(0, 0, 0, CARD_H);
  grad.addColorStop(0, '#0a0a1a');
  grad.addColorStop(0.5, '#111128');
  grad.addColorStop(1, '#1a1a2e');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, CARD_W, CARD_H);

  // Subtle grain texture
  ctx.globalAlpha = 0.03;
  for (let i = 0; i < 8000; i++) {
    const x = Math.random() * CARD_W;
    const y = Math.random() * CARD_H;
    ctx.fillStyle = Math.random() > 0.5 ? '#fff' : '#000';
    ctx.fillRect(x, y, 1, 1);
  }
  ctx.globalAlpha = 1;
}

function drawTrackGlow(
  ctx: CanvasRenderingContext2D,
  coords: { lat: number[]; lon: number[] },
): void {
  const { lat, lon } = coords;
  if (lat.length < 10) return;

  const minLat = Math.min(...lat),
    maxLat = Math.max(...lat);
  const minLon = Math.min(...lon),
    maxLon = Math.max(...lon);
  const rangeX = maxLon - minLon || 1e-6;
  const rangeY = maxLat - minLat || 1e-6;
  const size = 500;
  const scale = size / Math.max(rangeX, rangeY);
  const cx = CARD_W / 2;
  const cy = 650;

  ctx.save();
  ctx.globalAlpha = 0.12;
  ctx.strokeStyle = ACCENT;
  ctx.lineWidth = 6;
  ctx.shadowColor = ACCENT_GLOW;
  ctx.shadowBlur = 40;
  ctx.beginPath();
  for (let i = 0; i < lat.length; i++) {
    const x = cx + (lon[i] - (minLon + maxLon) / 2) * scale;
    const y = cy - (lat[i] - (minLat + maxLat) / 2) * scale;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.globalAlpha = 1;
  ctx.restore();
}

function drawScoreRing(
  ctx: CanvasRenderingContext2D,
  score: number,
  cx: number,
  cy: number,
): void {
  const r = 100;
  const lineW = 14;
  const startAngle = -Math.PI / 2;
  const endAngle = startAngle + (2 * Math.PI * Math.min(score, 10)) / 10;

  // Background ring
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, 2 * Math.PI);
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.lineWidth = lineW;
  ctx.stroke();

  // Score arc with glow
  ctx.save();
  ctx.shadowColor = ACCENT_GLOW;
  ctx.shadowBlur = 20;
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, endAngle);
  ctx.strokeStyle = ACCENT;
  ctx.lineWidth = lineW;
  ctx.lineCap = 'round';
  ctx.stroke();
  ctx.restore();

  // Score text
  ctx.fillStyle = '#fff';
  ctx.font = "bold 64px 'Barlow Semi Condensed', sans-serif";
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(score.toFixed(1), cx, cy - 8);
  ctx.font = "24px 'Barlow Semi Condensed', sans-serif";
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.fillText('/ 10', cx, cy + 32);
}

function drawStatPill(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  value: string,
  label: string,
): void {
  const w = 180;
  const h = 90;
  ctx.fillStyle = 'rgba(255,255,255,0.06)';
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(x - w / 2, y, w, h, 16);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#fff';
  ctx.font = "bold 32px 'JetBrains Mono', monospace";
  ctx.textAlign = 'center';
  ctx.fillText(value, x, y + 36);
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.font = "18px 'Barlow Semi Condensed', sans-serif";
  ctx.fillText(label, x, y + 68);
}

export function renderSessionCard(
  canvas: HTMLCanvasElement,
  data: ShareCardData,
): void {
  canvas.width = CARD_W;
  canvas.height = CARD_H;
  const ctx = canvas.getContext('2d')!;

  drawBackground(ctx);

  // Track name + date at top
  let y = 100;
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(255,255,255,0.7)';
  ctx.font = "28px 'Barlow Semi Condensed', sans-serif";
  ctx.fillText(data.trackName, CARD_W / 2, y);
  y += 40;
  ctx.fillStyle = 'rgba(255,255,255,0.4)';
  ctx.font = "22px 'Barlow Semi Condensed', sans-serif";
  ctx.fillText(data.sessionDate, CARD_W / 2, y);

  // Track outline glow
  if (data.gpsCoords && data.gpsCoords.lat.length > 10) {
    drawTrackGlow(ctx, data.gpsCoords);
  }

  // Identity label
  y = 920;
  ctx.fillStyle = '#fff';
  ctx.font = "bold 96px 'Barlow Semi Condensed', sans-serif";
  ctx.textAlign = 'center';
  ctx.fillText(data.identityLabel, CARD_W / 2, y);

  // Decorative line under label
  ctx.strokeStyle = 'rgba(255,255,255,0.15)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(CARD_W / 2 - 200, y + 20);
  ctx.lineTo(CARD_W / 2 + 200, y + 20);
  ctx.stroke();

  // Score ring
  if (data.sessionScore != null) {
    drawScoreRing(ctx, data.sessionScore, CARD_W / 2, 1100);
  }

  // Best lap time
  y = 1310;
  if (data.bestLapTime != null) {
    ctx.fillStyle = '#fff';
    ctx.font = "bold 56px 'JetBrains Mono', monospace";
    ctx.textAlign = 'center';
    ctx.fillText(formatLapTime(data.bestLapTime), CARD_W / 2, y);
    ctx.fillStyle = 'rgba(255,255,255,0.4)';
    ctx.font = "22px 'Barlow Semi Condensed', sans-serif";
    ctx.fillText('BEST LAP', CARD_W / 2, y + 36);
  }

  // Stat pills
  y = 1440;
  drawStatPill(ctx, CARD_W / 2 - 120, y, String(data.nLaps), 'LAPS');
  if (data.consistencyScore != null) {
    drawStatPill(
      ctx,
      CARD_W / 2 + 120,
      y,
      `${Math.round(data.consistencyScore * 100)}%`,
      'CONSISTENCY',
    );
  }

  // Footer CTA
  y = 1820;
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  ctx.font = "22px 'Barlow Semi Condensed', sans-serif";
  ctx.textAlign = 'center';
  ctx.fillText('\u2500\u2500\u2500 cataclysm.app \u2500\u2500\u2500', CARD_W / 2, y);
}
