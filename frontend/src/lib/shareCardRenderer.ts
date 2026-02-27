import { formatLapTime } from './formatters';

export interface ShareCardData {
  trackName: string;
  sessionDate: string;
  bestLapTime: number;
  sessionScore: number | null;
  improvementDelta: number | null; // seconds faster than previous session
  topInsight: string | null;
  gpsCoords: Array<{ lat: number; lon: number }> | null;
}

const CARD_W = 1080;
const CARD_H = 1920;

function drawBackground(ctx: CanvasRenderingContext2D) {
  const grad = ctx.createLinearGradient(0, 0, 0, CARD_H);
  grad.addColorStop(0, '#0f0f23');
  grad.addColorStop(0.5, '#1a1a2e');
  grad.addColorStop(1, '#16213e');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, CARD_W, CARD_H);
}

function drawTrackOutline(
  ctx: CanvasRenderingContext2D,
  coords: Array<{ lat: number; lon: number }>,
) {
  if (coords.length < 10) return;

  // Project GPS to screen coords
  const lats = coords.map((c) => c.lat);
  const lons = coords.map((c) => c.lon);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);

  const mapPadding = 120;
  const mapWidth = CARD_W - mapPadding * 2;
  const mapHeight = 600;
  const mapY = 300;

  const latRange = maxLat - minLat || 1e-6;
  const lonRange = maxLon - minLon || 1e-6;
  const scale = Math.min(mapWidth / lonRange, mapHeight / latRange);

  ctx.beginPath();
  ctx.strokeStyle = 'rgba(99, 102, 241, 0.6)';
  ctx.lineWidth = 3;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  coords.forEach((c, i) => {
    const x = mapPadding + (c.lon - minLon) * scale + (mapWidth - lonRange * scale) / 2;
    const y = mapY + mapHeight - ((c.lat - minLat) * scale + (mapHeight - latRange * scale) / 2);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawScoreRing(
  ctx: CanvasRenderingContext2D,
  score: number,
  cx: number,
  cy: number,
  r: number,
) {
  // Background ring
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(255,255,255,0.1)';
  ctx.lineWidth = 6;
  ctx.stroke();

  // Score arc
  const endAngle = -Math.PI / 2 + (score / 100) * Math.PI * 2;
  ctx.beginPath();
  ctx.arc(cx, cy, r, -Math.PI / 2, endAngle);
  ctx.strokeStyle = '#6366f1';
  ctx.lineWidth = 6;
  ctx.stroke();

  // Score text
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 28px Inter, system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(Math.round(score).toString(), cx, cy);
}

export function renderSessionCard(
  canvas: HTMLCanvasElement,
  data: ShareCardData,
): void {
  canvas.width = CARD_W;
  canvas.height = CARD_H;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // Background
  drawBackground(ctx);

  // Header
  ctx.fillStyle = '#6366f1';
  ctx.font = 'bold 36px Inter, system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('CATACLYSM', CARD_W / 2, 80);

  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  ctx.font = '16px Inter, system-ui, sans-serif';
  ctx.fillText('AI Motorsport Coaching', CARD_W / 2, 115);

  // Divider
  ctx.strokeStyle = 'rgba(99, 102, 241, 0.3)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(100, 150);
  ctx.lineTo(CARD_W - 100, 150);
  ctx.stroke();

  // Track outline
  if (data.gpsCoords && data.gpsCoords.length > 10) {
    drawTrackOutline(ctx, data.gpsCoords);
  }

  // Best lap time
  const lapY = data.gpsCoords ? 1050 : 700;
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 72px Inter, system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(formatLapTime(data.bestLapTime), CARD_W / 2, lapY);

  ctx.fillStyle = '#22c55e';
  ctx.font = '20px Inter, system-ui, sans-serif';
  ctx.fillText('BEST LAP', CARD_W / 2, lapY + 40);

  // Score + improvement row
  const rowY = lapY + 100;
  if (data.sessionScore !== null) {
    drawScoreRing(ctx, data.sessionScore, CARD_W / 2 - 100, rowY, 30);
  }
  if (data.improvementDelta !== null) {
    const sign = data.improvementDelta > 0 ? '+' : '';
    ctx.fillStyle = data.improvementDelta < 0 ? '#22c55e' : '#f97316';
    ctx.font = 'bold 24px Inter, system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${sign}${data.improvementDelta.toFixed(2)}s`, CARD_W / 2 + 100, rowY + 8);
  }

  // AI Insight
  if (data.topInsight) {
    const insightY = rowY + 100;
    ctx.fillStyle = 'rgba(99, 102, 241, 0.15)';
    const insightPad = 40;
    ctx.beginPath();
    ctx.roundRect(insightPad, insightY - 30, CARD_W - insightPad * 2, 100, 12);
    ctx.fill();

    ctx.fillStyle = 'rgba(255,255,255,0.8)';
    ctx.font = '18px Inter, system-ui, sans-serif';
    ctx.textAlign = 'center';
    // Truncate long text
    const text =
      data.topInsight.length > 100
        ? data.topInsight.substring(0, 97) + '...'
        : data.topInsight;
    ctx.fillText(text, CARD_W / 2, insightY + 10);
  }

  // Footer divider
  ctx.strokeStyle = 'rgba(99, 102, 241, 0.3)';
  ctx.beginPath();
  ctx.moveTo(100, CARD_H - 180);
  ctx.lineTo(CARD_W - 100, CARD_H - 180);
  ctx.stroke();

  // Footer
  ctx.fillStyle = 'rgba(255,255,255,0.6)';
  ctx.font = '18px Inter, system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(
    `${data.trackName} | ${data.sessionDate}`,
    CARD_W / 2,
    CARD_H - 130,
  );

  ctx.fillStyle = 'rgba(99, 102, 241, 0.6)';
  ctx.font = '14px Inter, system-ui, sans-serif';
  ctx.fillText('Analyzed by Cataclysm', CARD_W / 2, CARD_H - 90);
}
