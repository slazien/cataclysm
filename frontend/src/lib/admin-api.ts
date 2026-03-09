import { fetchApi } from "./api";

export interface TrackGeometry {
  x: number[];
  y: number[];
  curvature: number[];
}

export interface TrackCorner {
  number: number;
  name: string;
  fraction: number;
  direction: "left" | "right";
  corner_type: string;
  elevation_trend?: string;
  camber?: string;
  coaching_note?: string;
}

export interface TrackEditorData {
  track_slug: string;
  track_length_m: number;
  geometry: TrackGeometry;
  corners: TrackCorner[];
}

export async function getTrackList(): Promise<{ tracks: string[] }> {
  return fetchApi("/api/admin/tracks");
}

export async function getTrackEditorData(
  slug: string,
): Promise<TrackEditorData> {
  return fetchApi(`/api/admin/tracks/${slug}/editor`);
}

export async function saveTrackCorners(
  slug: string,
  corners: TrackCorner[],
): Promise<{ saved: boolean; corner_count: number }> {
  return fetchApi(`/api/admin/tracks/${slug}/corners`, {
    method: "PUT",
    body: JSON.stringify({ corners }),
  });
}
