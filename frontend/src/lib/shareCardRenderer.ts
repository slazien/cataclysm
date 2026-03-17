import QRCode from 'qrcode';
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
  topSpeed: number | null;
  speedUnit: string;
  skillDimensions: {
    braking: number;
    trailBraking: number;
    throttle: number;
    line: number;
  } | null;
  viewUrl: string | null;
}

const CARD_W = 1080;
const CARD_H = 1620;
const ACCENT = '#6366f1';
const ACCENT_GLOW = 'rgba(99, 102, 241, 0.4)';

export function getShareScoreDisplay(score: number) {
  const clamped = Math.min(Math.max(score, 0), 100);
  return {
    fraction: clamped / 100,
    valueText: String(Math.round(clamped)),
    scaleText: '/ 100',
  };
}

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
  const size = 320;
  const scale = size / Math.max(rangeX, rangeY);
  const cx = CARD_W / 2;
  const cy = 280;

  ctx.save();
  ctx.globalAlpha = 0.22;
  ctx.strokeStyle = ACCENT;
  ctx.lineWidth = 7;
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
  const display = getShareScoreDisplay(score);
  const r = 110;
  const lineW = 16;
  const startAngle = -Math.PI / 2;
  const endAngle = startAngle + 2 * Math.PI * display.fraction;

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
  ctx.font = "bold 80px 'Barlow Semi Condensed', sans-serif";
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(display.valueText, cx, cy - 10);
  ctx.font = "28px 'Barlow Semi Condensed', sans-serif";
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.fillText(display.scaleText, cx, cy + 40);
}

function drawStatPill(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  value: string,
  label: string,
): void {
  const w = 210;
  const h = 105;
  ctx.fillStyle = 'rgba(255,255,255,0.06)';
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(x - w / 2, y, w, h, 16);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#fff';
  ctx.font = "bold 44px 'JetBrains Mono', monospace";
  ctx.textAlign = 'center';
  ctx.fillText(value, x, y + 44);
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.font = "24px 'Barlow Semi Condensed', sans-serif";
  ctx.fillText(label, x, y + 82);
}

function drawSkillRadar(
  ctx: CanvasRenderingContext2D,
  dims: { braking: number; trailBraking: number; throttle: number; line: number },
  cx: number,
  cy: number,
  radius: number,
): void {
  const axes = ['Braking', 'Trail Braking', 'Throttle', 'Line'];
  const values = [dims.braking, dims.trailBraking, dims.throttle, dims.line];
  const n = axes.length;
  const angleStep = (2 * Math.PI) / n;
  const startAngle = -Math.PI / 2;

  ctx.save();

  // Concentric grid rings
  for (const pct of [0.2, 0.4, 0.6, 0.8, 1.0]) {
    const r = radius * pct;
    ctx.beginPath();
    for (let i = 0; i <= n; i++) {
      const angle = startAngle + (i % n) * angleStep;
      const x = cx + r * Math.cos(angle);
      const y = cy + r * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // Axis lines
  for (let i = 0; i < n; i++) {
    const angle = startAngle + i * angleStep;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle));
    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // Data polygon with glow
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const angle = startAngle + i * angleStep;
    const r = (Math.min(values[i], 100) / 100) * radius;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = 'rgba(99, 102, 241, 0.25)';
  ctx.fill();
  ctx.shadowColor = ACCENT_GLOW;
  ctx.shadowBlur = 15;
  ctx.strokeStyle = ACCENT;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Axis labels
  ctx.font = "24px 'Barlow Semi Condensed', sans-serif";
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  for (let i = 0; i < n; i++) {
    const angle = startAngle + i * angleStep;
    const labelR = radius + 24;
    ctx.fillText(axes[i], cx + labelR * Math.cos(angle), cy + labelR * Math.sin(angle));
  }

  ctx.restore();
}

async function drawQRCode(
  ctx: CanvasRenderingContext2D,
  url: string,
  x: number,
  y: number,
  size: number,
): Promise<void> {
  const dataUrl = await QRCode.toDataURL(url, {
    width: size,
    margin: 1,
    color: { dark: '#ffffff', light: '#00000000' },
  });
  return new Promise<void>((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      ctx.drawImage(img, x - size / 2, y, size, size);
      resolve();
    };
    img.onerror = reject;
    img.src = dataUrl;
  });
}

export async function renderSessionCard(
  canvas: HTMLCanvasElement,
  data: ShareCardData,
): Promise<void> {
  canvas.width = CARD_W;
  canvas.height = CARD_H;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not get 2d canvas context');

  drawBackground(ctx);

  // Track name + date at top
  let y = 80;
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(255,255,255,0.7)';
  ctx.font = "48px 'Barlow Semi Condensed', sans-serif";
  ctx.fillText(data.trackName, CARD_W / 2, y);
  y += 48;
  ctx.fillStyle = 'rgba(255,255,255,0.4)';
  ctx.font = "34px 'Barlow Semi Condensed', sans-serif";
  ctx.fillText(data.sessionDate, CARD_W / 2, y);

  // Track outline glow (background decoration — behind content)
  if (data.gpsCoords && data.gpsCoords.lat.length > 10) {
    drawTrackGlow(ctx, data.gpsCoords);
  }

  // Identity label
  y = 420;
  ctx.fillStyle = '#fff';
  ctx.font = "bold 120px 'Barlow Semi Condensed', sans-serif";
  ctx.textAlign = 'center';
  ctx.fillText(data.identityLabel, CARD_W / 2, y);

  // Decorative line under label
  ctx.strokeStyle = 'rgba(255,255,255,0.15)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(CARD_W / 2 - 220, y + 24);
  ctx.lineTo(CARD_W / 2 + 220, y + 24);
  ctx.stroke();

  // Score ring
  if (data.sessionScore != null) {
    drawScoreRing(ctx, data.sessionScore, CARD_W / 2, 590);
  }

  // Best lap time
  y = 770;
  if (data.bestLapTime != null) {
    ctx.fillStyle = '#fff';
    ctx.font = "bold 80px 'JetBrains Mono', monospace";
    ctx.textAlign = 'center';
    ctx.fillText(formatLapTime(data.bestLapTime), CARD_W / 2, y);
    ctx.fillStyle = 'rgba(255,255,255,0.4)';
    ctx.font = "28px 'Barlow Semi Condensed', sans-serif";
    ctx.fillText('BEST LAP', CARD_W / 2, y + 44);
  }

  // 3 Stat pills
  y = 890;
  drawStatPill(ctx, CARD_W / 2 - 220, y, String(data.nLaps), 'LAPS');
  if (data.consistencyScore != null) {
    drawStatPill(ctx, CARD_W / 2, y, `${Math.round(data.consistencyScore * 100)}%`, 'CONSISTENCY');
  }
  if (data.topSpeed != null) {
    drawStatPill(ctx, CARD_W / 2 + 220, y, `${Math.round(data.topSpeed)} ${data.speedUnit}`, 'TOP SPEED');
  }

  // Skill radar chart
  if (data.skillDimensions) {
    drawSkillRadar(ctx, data.skillDimensions, CARD_W / 2, 1110, 110);
  }

  // QR code
  if (data.viewUrl) {
    await drawQRCode(ctx, data.viewUrl, CARD_W / 2, 1310, 140);
    ctx.fillStyle = 'rgba(255,255,255,0.4)';
    ctx.font = "24px 'Barlow Semi Condensed', sans-serif";
    ctx.textAlign = 'center';
    ctx.fillText('Scan to view full analysis', CARD_W / 2, 1470);
  }

  // Footer CTA
  y = 1560;
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  ctx.font = "30px 'Barlow Semi Condensed', sans-serif";
  ctx.textAlign = 'center';
  ctx.fillText('\u2500\u2500\u2500 cataclysm.app \u2500\u2500\u2500', CARD_W / 2, y);
}
