"use client";

import { useCallback, useRef, useState } from "react";
import { useUploadSessions } from "@/hooks/useSession";
import Spinner from "./Spinner";

export default function FileUpload() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const upload = useUploadSessions();

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const csvFiles = Array.from(files).filter(
        (f) => f.name.endsWith(".csv") || f.type === "text/csv",
      );
      if (csvFiles.length > 0) {
        upload.mutate(csvFiles);
      }
    },
    [upload],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  return (
    <div>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileRef.current?.click()}
        className={`
          flex cursor-pointer flex-col items-center justify-center
          rounded-lg border-2 border-dashed p-4 text-center
          transition-colors duration-150
          ${
            isDragOver
              ? "border-[var(--accent-blue)] bg-[var(--accent-blue)]/10"
              : "border-[var(--border-color)] hover:border-[var(--text-muted)]"
          }
        `}
      >
        {upload.isPending ? (
          <div className="flex items-center gap-2">
            <Spinner size="sm" />
            <span className="text-sm text-[var(--text-secondary)]">
              Uploading...
            </span>
          </div>
        ) : (
          <>
            <svg
              className="mb-1 h-6 w-6 text-[var(--text-muted)]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            <span className="text-xs text-[var(--text-secondary)]">
              Drop CSV files or click to browse
            </span>
          </>
        )}
      </div>
      <input
        ref={fileRef}
        type="file"
        accept=".csv"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {upload.isError && (
        <p className="mt-1 text-xs text-[var(--accent-red)]">
          {upload.error.message}
        </p>
      )}
      {upload.isSuccess && (
        <p className="mt-1 text-xs text-[var(--accent-green)]">
          Uploaded {upload.data.session_ids.length} session(s)
        </p>
      )}
    </div>
  );
}
