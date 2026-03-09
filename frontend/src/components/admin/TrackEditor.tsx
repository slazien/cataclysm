"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  getTrackList,
  getTrackEditorData,
  saveTrackCorners,
  type TrackGeometry,
  type TrackCorner,
} from "@/lib/admin-api";

// ─── Constants ────────────────────────────────────────────────────────────────

const CORNER_TYPES = ["sweeper", "hairpin", "kink", "esses"] as const;
const ELEVATIONS = ["flat", "uphill", "downhill", "crest"] as const;
const CAMBERS = ["flat", "positive", "negative"] as const;
const DIRECTIONS = ["left", "right"] as const;

const COLOR_LEFT = "#2dd4bf";
const COLOR_RIGHT = "#fb923c";
const COLOR_NEUTRAL = "#94a3b8";
const TRACK_STROKE = "#475569";

// ─── Utility helpers ──────────────────────────────────────────────────────────

function fractionToIndex(fraction: number, len: number): number {
  return Math.round(fraction * (len - 1));
}

function findNearestTrackPoint(
  sx: number,
  sy: number,
  geometry: TrackGeometry,
): { index: number; fraction: number } {
  let minDist = Infinity;
  let bestIdx = 0;
  for (let i = 0; i < geometry.x.length; i++) {
    const dx = geometry.x[i] - sx;
    const dy = geometry.y[i] - sy;
    const d = dx * dx + dy * dy;
    if (d < minDist) {
      minDist = d;
      bestIdx = i;
    }
  }
  return { index: bestIdx, fraction: bestIdx / (geometry.x.length - 1) };
}

function autoDetectDirection(
  curvature: number,
): "left" | "right" {
  return curvature >= 0 ? "left" : "right";
}

function autoDetectCornerType(curvature: number): string {
  const abs = Math.abs(curvature);
  if (abs > 0.02) return "hairpin";
  if (abs > 0.01) return "sweeper";
  return "kink";
}

function curvatureColor(curv: number): string {
  if (curv > 0.001) return COLOR_LEFT;
  if (curv < -0.001) return COLOR_RIGHT;
  return COLOR_NEUTRAL;
}

// ─── SVG Track Canvas ─────────────────────────────────────────────────────────

interface TrackCanvasProps {
  geometry: TrackGeometry;
  corners: TrackCorner[];
  selectedCornerIdx: number | null;
  addMode: boolean;
  onSelectCorner: (idx: number) => void;
  onDragCorner: (idx: number, fraction: number) => void;
  onAddCorner: (fraction: number, curvature: number) => void;
}

function TrackCanvas({
  geometry,
  corners,
  selectedCornerIdx,
  addMode,
  onSelectCorner,
  onDragCorner,
  onAddCorner,
}: TrackCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dragIdx, setDragIdx] = useState<number | null>(null);

  // Compute bounding box with padding
  const { viewBox, markerRadius } = useMemo(() => {
    let xMin = Infinity,
      xMax = -Infinity,
      yMin = Infinity,
      yMax = -Infinity;
    for (let i = 0; i < geometry.x.length; i++) {
      if (geometry.x[i] < xMin) xMin = geometry.x[i];
      if (geometry.x[i] > xMax) xMax = geometry.x[i];
      if (geometry.y[i] < yMin) yMin = geometry.y[i];
      if (geometry.y[i] > yMax) yMax = geometry.y[i];
    }
    const width = xMax - xMin;
    const height = yMax - yMin;
    const pad = Math.max(width, height) * 0.05;
    // Marker radius scales with track size
    const mr = Math.max(width, height) * 0.012;
    return {
      viewBox: `${xMin - pad} ${-(yMax + pad)} ${width + 2 * pad} ${height + 2 * pad}`,
      markerRadius: mr,
    };
  }, [geometry]);

  // Build polyline points string
  const trackPoints = useMemo(() => {
    const pts: string[] = [];
    for (let i = 0; i < geometry.x.length; i++) {
      pts.push(`${geometry.x[i]},${-geometry.y[i]}`);
    }
    return pts.join(" ");
  }, [geometry]);

  // Build curvature-colored segments
  const curvatureSegments = useMemo(() => {
    const segs: { points: string; color: string }[] = [];
    let currentColor = curvatureColor(geometry.curvature[0]);
    let currentPts = [`${geometry.x[0]},${-geometry.y[0]}`];

    for (let i = 1; i < geometry.x.length; i++) {
      const c = curvatureColor(geometry.curvature[i]);
      currentPts.push(`${geometry.x[i]},${-geometry.y[i]}`);
      if (c !== currentColor || i === geometry.x.length - 1) {
        segs.push({ points: currentPts.join(" "), color: currentColor });
        currentColor = c;
        // Overlap by one point for continuity
        currentPts = [`${geometry.x[i]},${-geometry.y[i]}`];
      }
    }
    return segs;
  }, [geometry]);

  // Convert screen coords to SVG coords
  const screenToSvg = useCallback(
    (e: React.MouseEvent): { x: number; y: number } => {
      const svg = svgRef.current;
      if (!svg) return { x: 0, y: 0 };
      const pt = svg.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      const ctm = svg.getScreenCTM();
      if (!ctm) return { x: 0, y: 0 };
      const svgPt = pt.matrixTransform(ctm.inverse());
      // Undo y-flip: SVG y = -track y
      return { x: svgPt.x, y: -svgPt.y };
    },
    [],
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent, idx: number) => {
      e.stopPropagation();
      if (addMode) return;
      setDragIdx(idx);
      onSelectCorner(idx);
    },
    [addMode, onSelectCorner],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (dragIdx === null) return;
      const { x, y } = screenToSvg(e);
      const nearest = findNearestTrackPoint(x, y, geometry);
      onDragCorner(dragIdx, nearest.fraction);
    },
    [dragIdx, screenToSvg, geometry, onDragCorner],
  );

  const handleMouseUp = useCallback(() => {
    setDragIdx(null);
  }, []);

  const handleCanvasClick = useCallback(
    (e: React.MouseEvent) => {
      if (!addMode) return;
      const { x, y } = screenToSvg(e);
      const nearest = findNearestTrackPoint(x, y, geometry);
      const curv = geometry.curvature[nearest.index];
      onAddCorner(nearest.fraction, curv);
    },
    [addMode, screenToSvg, geometry, onAddCorner],
  );

  return (
    <svg
      ref={svgRef}
      viewBox={viewBox}
      className={`h-full w-full ${addMode ? "cursor-crosshair" : "cursor-default"}`}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onClick={handleCanvasClick}
    >
      {/* Track outline base */}
      <polyline
        points={trackPoints}
        stroke={TRACK_STROKE}
        strokeWidth={markerRadius * 0.7}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Curvature-colored overlay */}
      {curvatureSegments.map((seg, i) => (
        <polyline
          key={i}
          points={seg.points}
          stroke={seg.color}
          strokeWidth={markerRadius * 0.35}
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.7}
        />
      ))}

      {/* Corner markers */}
      {corners.map((corner, idx) => {
        const ptIdx = fractionToIndex(corner.fraction, geometry.x.length);
        const cx = geometry.x[ptIdx];
        const cy = -geometry.y[ptIdx]; // flip y
        const isSelected = selectedCornerIdx === idx;
        const color = corner.direction === "left" ? COLOR_LEFT : COLOR_RIGHT;
        const r = isSelected ? markerRadius * 1.5 : markerRadius;

        return (
          <g key={corner.number} style={{ cursor: "grab" }}>
            {/* Glow for selected */}
            {isSelected && (
              <circle
                cx={cx}
                cy={cy}
                r={r * 1.6}
                fill="none"
                stroke="white"
                strokeWidth={markerRadius * 0.15}
                opacity={0.4}
              />
            )}
            <circle
              cx={cx}
              cy={cy}
              r={r}
              fill={color}
              stroke={isSelected ? "white" : "none"}
              strokeWidth={isSelected ? markerRadius * 0.2 : 0}
              opacity={0.9}
              onMouseDown={(e) => handleMouseDown(e, idx)}
            />
            {/* Label */}
            <text
              x={cx + markerRadius * 2}
              y={cy + markerRadius * 0.4}
              fill="white"
              fontSize={markerRadius * 1.8}
              fontWeight={isSelected ? 700 : 500}
              style={{ pointerEvents: "none", userSelect: "none" }}
            >
              T{corner.number}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Corner Edit Panel ────────────────────────────────────────────────────────

interface CornerPanelProps {
  corner: TrackCorner;
  onChange: (updated: TrackCorner) => void;
}

function CornerPanel({ corner, onChange }: CornerPanelProps) {
  const field = (
    label: string,
    value: string,
    setter: (v: string) => void,
    type: "text" | "select" | "textarea" = "text",
    options?: readonly string[],
  ) => (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
        {label}
      </label>
      {type === "select" && options ? (
        <select
          value={value}
          onChange={(e) => setter(e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : type === "textarea" ? (
        <textarea
          value={value}
          onChange={(e) => setter(e.target.value)}
          rows={3}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground resize-y focus:outline-none focus:ring-2 focus:ring-ring"
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => setter(e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-base font-semibold text-foreground">
        Turn {corner.number}
      </h3>

      {field("Name", corner.name, (v) =>
        onChange({ ...corner, name: v }),
      )}

      {field(
        "Direction",
        corner.direction,
        (v) => onChange({ ...corner, direction: v as "left" | "right" }),
        "select",
        DIRECTIONS,
      )}

      {field(
        "Type",
        corner.corner_type,
        (v) => onChange({ ...corner, corner_type: v }),
        "select",
        CORNER_TYPES,
      )}

      {field(
        "Elevation",
        corner.elevation_trend ?? "flat",
        (v) => onChange({ ...corner, elevation_trend: v }),
        "select",
        ELEVATIONS,
      )}

      {field(
        "Camber",
        corner.camber ?? "flat",
        (v) => onChange({ ...corner, camber: v }),
        "select",
        CAMBERS,
      )}

      {field(
        "Coaching Note",
        corner.coaching_note ?? "",
        (v) => onChange({ ...corner, coaching_note: v }),
        "textarea",
      )}

      <div className="mt-1 rounded bg-card p-2 text-xs text-muted-foreground">
        <span className="font-medium">Fraction:</span>{" "}
        {corner.fraction.toFixed(4)}
      </div>
    </div>
  );
}

// ─── Main TrackEditor Component ───────────────────────────────────────────────

export function TrackEditor() {
  const queryClient = useQueryClient();

  // ── Track list query
  const trackListQuery = useQuery({
    queryKey: ["admin", "tracks"],
    queryFn: getTrackList,
  });

  // ── Selected track
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  // ── Track data query
  const trackDataQuery = useQuery({
    queryKey: ["admin", "track-editor", selectedSlug],
    queryFn: () => getTrackEditorData(selectedSlug!),
    enabled: !!selectedSlug,
  });

  // ── Local corner state (editable copy)
  const [corners, setCorners] = useState<TrackCorner[]>([]);
  const [originalCorners, setOriginalCorners] = useState<TrackCorner[]>([]);
  const [selectedCornerIdx, setSelectedCornerIdx] = useState<number | null>(
    null,
  );
  const [addMode, setAddMode] = useState(false);
  const [lastSaveTime, setLastSaveTime] = useState<Date | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Sync corners from server data
  useEffect(() => {
    if (trackDataQuery.data) {
      const c = structuredClone(trackDataQuery.data.corners);
      setCorners(c);
      setOriginalCorners(structuredClone(c));
      setSelectedCornerIdx(null);
      setAddMode(false);
      setLastSaveTime(null);
    }
  }, [trackDataQuery.data]);

  // ── Unsaved changes count
  const unsavedCount = useMemo(() => {
    if (corners.length !== originalCorners.length) return corners.length;
    let count = 0;
    for (let i = 0; i < corners.length; i++) {
      if (JSON.stringify(corners[i]) !== JSON.stringify(originalCorners[i])) {
        count++;
      }
    }
    return count;
  }, [corners, originalCorners]);

  const hasUnsavedChanges =
    unsavedCount > 0 || corners.length !== originalCorners.length;

  // ── Save mutation
  const saveMutation = useMutation({
    mutationFn: (args: { slug: string; corners: TrackCorner[] }) =>
      saveTrackCorners(args.slug, args.corners),
    onSuccess: () => {
      setOriginalCorners(structuredClone(corners));
      setLastSaveTime(new Date());
      queryClient.invalidateQueries({
        queryKey: ["admin", "track-editor", selectedSlug],
      });
    },
  });

  // ── Handlers
  const handleSelectCorner = useCallback((idx: number) => {
    setSelectedCornerIdx(idx);
    setAddMode(false);
  }, []);

  const handleDragCorner = useCallback(
    (idx: number, fraction: number) => {
      setCorners((prev) => {
        const next = [...prev];
        next[idx] = { ...next[idx], fraction };
        return next;
      });
    },
    [],
  );

  const handleAddCorner = useCallback(
    (fraction: number, curvature: number) => {
      const maxNum = corners.reduce(
        (max, c) => Math.max(max, c.number),
        0,
      );
      const newCorner: TrackCorner = {
        number: maxNum + 1,
        name: `Turn ${maxNum + 1}`,
        fraction,
        direction: autoDetectDirection(curvature),
        corner_type: autoDetectCornerType(curvature),
        elevation_trend: "flat",
        camber: "flat",
        coaching_note: "",
      };
      setCorners((prev) => [...prev, newCorner]);
      setSelectedCornerIdx(corners.length); // select the new one
      setAddMode(false);
    },
    [corners],
  );

  const handleCornerChange = useCallback(
    (updated: TrackCorner) => {
      if (selectedCornerIdx === null) return;
      setCorners((prev) => {
        const next = [...prev];
        next[selectedCornerIdx] = updated;
        return next;
      });
    },
    [selectedCornerIdx],
  );

  const handleDeleteCorner = useCallback(() => {
    if (selectedCornerIdx === null) return;
    setDeleteDialogOpen(true);
  }, [selectedCornerIdx]);

  const confirmDelete = useCallback(() => {
    if (selectedCornerIdx === null) return;
    setCorners((prev) => prev.filter((_, i) => i !== selectedCornerIdx));
    setSelectedCornerIdx(null);
    setDeleteDialogOpen(false);
  }, [selectedCornerIdx]);

  const handleSave = useCallback(() => {
    if (!selectedSlug) return;
    // Renumber corners by fraction order before saving
    const sorted = [...corners].sort((a, b) => a.fraction - b.fraction);
    const renumbered = sorted.map((c, i) => ({ ...c, number: i + 1 }));
    setCorners(renumbered);
    saveMutation.mutate({ slug: selectedSlug, corners: renumbered });
  }, [selectedSlug, corners, saveMutation]);

  // ── Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "Delete" && selectedCornerIdx !== null) {
        e.preventDefault();
        setDeleteDialogOpen(true);
      }
      if (e.key === "Escape") {
        setAddMode(false);
        setSelectedCornerIdx(null);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectedCornerIdx]);

  // ── Derived data
  const geometry = trackDataQuery.data?.geometry;
  const trackLength = trackDataQuery.data?.track_length_m;

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      {/* ── Top bar ──────────────────────────────────────────────────── */}
      <header className="flex items-center gap-4 border-b border-border bg-card px-4 py-2">
        <h1 className="text-lg font-semibold tracking-tight">
          Track Map Editor
        </h1>

        {/* Track selector */}
        <select
          value={selectedSlug ?? ""}
          onChange={(e) => {
            if (
              hasUnsavedChanges &&
              !window.confirm("You have unsaved changes. Discard and switch tracks?")
            )
              return;
            setSelectedSlug(e.target.value || null);
          }}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">Select track...</option>
          {trackListQuery.data?.tracks.map((slug) => (
            <option key={slug} value={slug}>
              {slug}
            </option>
          ))}
        </select>

        {trackLength != null && (
          <span className="text-xs text-muted-foreground">
            {(trackLength / 1000).toFixed(2)} km
          </span>
        )}

        <div className="flex-1" />

        {/* Toolbar */}
        <Button
          variant={addMode ? "default" : "outline"}
          size="sm"
          disabled={!geometry}
          onClick={() => setAddMode(!addMode)}
        >
          {addMode ? "Click track to place..." : "Add Turn"}
        </Button>
        <Button
          variant="destructive"
          size="sm"
          disabled={selectedCornerIdx === null}
          onClick={handleDeleteCorner}
        >
          Delete Turn
        </Button>
        <Button
          size="sm"
          disabled={!hasUnsavedChanges || saveMutation.isPending}
          onClick={handleSave}
        >
          {saveMutation.isPending ? "Saving..." : "Save"}
        </Button>
      </header>

      {/* ── Main area: canvas + panel ────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Canvas area */}
        <div className="flex-1 relative bg-[#0f172a]">
          {!selectedSlug && (
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
              Select a track to begin editing
            </div>
          )}
          {selectedSlug && trackDataQuery.isPending && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="animate-pulse text-muted-foreground">
                Loading track data...
              </div>
            </div>
          )}
          {selectedSlug && trackDataQuery.isError && (
            <div className="absolute inset-0 flex items-center justify-center text-destructive">
              Failed to load track data:{" "}
              {(trackDataQuery.error as Error).message}
            </div>
          )}
          {geometry && (
            <TrackCanvas
              geometry={geometry}
              corners={corners}
              selectedCornerIdx={selectedCornerIdx}
              addMode={addMode}
              onSelectCorner={handleSelectCorner}
              onDragCorner={handleDragCorner}
              onAddCorner={handleAddCorner}
            />
          )}
        </div>

        {/* Side panel */}
        <aside className="w-72 shrink-0 overflow-y-auto border-l border-border bg-card p-4">
          {selectedCornerIdx !== null && corners[selectedCornerIdx] ? (
            <CornerPanel
              corner={corners[selectedCornerIdx]}
              onChange={handleCornerChange}
            />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
              <p>No corner selected</p>
              <p className="text-xs">
                Click a corner marker on the map, or use "Add Turn" to create
                one.
              </p>
            </div>
          )}
        </aside>
      </div>

      {/* ── Status bar ───────────────────────────────────────────────── */}
      <footer className="flex items-center gap-4 border-t border-border bg-card px-4 py-1.5 text-xs text-muted-foreground">
        <span>
          {corners.length} corner{corners.length !== 1 ? "s" : ""}
        </span>
        {hasUnsavedChanges && (
          <span className="text-amber-400">
            {unsavedCount > 0
              ? `${unsavedCount} unsaved change${unsavedCount !== 1 ? "s" : ""}`
              : `${Math.abs(corners.length - originalCorners.length)} corner${Math.abs(corners.length - originalCorners.length) !== 1 ? "s" : ""} added/removed`}
          </span>
        )}
        {lastSaveTime && (
          <span className="text-emerald-400">
            Last saved: {lastSaveTime.toLocaleTimeString()}
          </span>
        )}
        {saveMutation.isError && (
          <span className="text-destructive">
            Save failed: {(saveMutation.error as Error).message}
          </span>
        )}
        {saveMutation.isSuccess && !hasUnsavedChanges && (
          <span className="text-emerald-400">All changes saved</span>
        )}
      </footer>

      {/* ── Delete confirmation dialog ───────────────────────────────── */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Turn</DialogTitle>
            <DialogDescription>
              {selectedCornerIdx !== null && corners[selectedCornerIdx]
                ? `Delete "${corners[selectedCornerIdx].name}" (T${corners[selectedCornerIdx].number})? This cannot be undone until you reload.`
                : "Delete this turn?"}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
