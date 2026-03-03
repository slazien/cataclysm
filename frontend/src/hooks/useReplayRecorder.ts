'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface ReplayRecorderState {
  /** Whether MediaRecorder is actively recording. */
  isRecording: boolean;
  /** Blob URL for downloading the completed recording (null until available). */
  downloadUrl: string | null;
  /** Whether the browser supports MediaRecorder + canvas capture. */
  isSupported: boolean;
  /** File extension for the recorded format (e.g. "webm" or "mp4"). */
  fileExtension: string;
}

export interface ReplayRecorderActions {
  /** Begin recording from the given canvas element at 30fps. */
  startRecording: (canvas: HTMLCanvasElement) => void;
  /** Stop the current recording and produce the download blob. */
  stopRecording: () => void;
  /** Clear the download URL and revoke the blob. */
  clearRecording: () => void;
}

/** Preferred MIME types in order of browser support likelihood. */
const MIME_CANDIDATES = [
  'video/webm;codecs=vp9',
  'video/webm;codecs=vp8',
  'video/webm',
  'video/mp4',
];

function getSupportedMimeType(): string | null {
  if (typeof MediaRecorder === 'undefined') return null;
  for (const mime of MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported(mime)) return mime;
  }
  return null;
}

function getFileExtension(mimeType: string): string {
  if (mimeType.startsWith('video/mp4')) return 'mp4';
  return 'webm';
}

/**
 * Hook for recording a canvas element stream as a downloadable video file.
 *
 * Uses the MediaRecorder API with `canvas.captureStream(30)` to capture
 * 30fps video. Prefers WebM (vp9/vp8) with MP4 fallback.
 *
 * Handles cleanup of blob URLs on unmount.
 */
export function useReplayRecorder(): ReplayRecorderState & ReplayRecorderActions {
  const [isRecording, setIsRecording] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef<string | null>(null);
  const blobUrlRef = useRef<string | null>(null);

  // Detect supported MIME type once
  const supportedMime =
    typeof window !== 'undefined' ? getSupportedMimeType() : null;

  const isSupported =
    typeof window !== 'undefined' &&
    typeof MediaRecorder !== 'undefined' &&
    typeof HTMLCanvasElement !== 'undefined' &&
    'captureStream' in HTMLCanvasElement.prototype &&
    supportedMime !== null;

  const fileExtension = supportedMime ? getFileExtension(supportedMime) : 'webm';

  // Revoke previous blob URL
  const revokeBlobUrl = useCallback(() => {
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
      blobUrlRef.current = null;
    }
  }, []);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
      revokeBlobUrl();
    };
  }, [revokeBlobUrl]);

  const startRecording = useCallback(
    (canvas: HTMLCanvasElement) => {
      if (!isSupported || !supportedMime) return;

      // Clear any previous recording
      revokeBlobUrl();
      setDownloadUrl(null);
      chunksRef.current = [];
      mimeTypeRef.current = supportedMime;

      const stream = canvas.captureStream(30);
      const recorder = new MediaRecorder(stream, {
        mimeType: supportedMime,
        videoBitsPerSecond: 2_500_000, // 2.5 Mbps for good quality
      });

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: supportedMime });
        const url = URL.createObjectURL(blob);
        blobUrlRef.current = url;
        setDownloadUrl(url);
        setIsRecording(false);
      };

      recorder.onerror = () => {
        setIsRecording(false);
        recorderRef.current = null;
      };

      recorderRef.current = recorder;
      recorder.start(100); // Collect data every 100ms for smoother output
      setIsRecording(true);
    },
    [isSupported, supportedMime, revokeBlobUrl],
  );

  const stopRecording = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    }
    recorderRef.current = null;
  }, []);

  const clearRecording = useCallback(() => {
    revokeBlobUrl();
    setDownloadUrl(null);
  }, [revokeBlobUrl]);

  return {
    isRecording,
    downloadUrl,
    isSupported,
    fileExtension,
    startRecording,
    stopRecording,
    clearRecording,
  };
}
