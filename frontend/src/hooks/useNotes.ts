"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listNotes, createNote, updateNote, deleteNote } from "@/lib/api";
import type { Note, NoteCreate, NoteUpdate } from "@/lib/types";

// --- Query hooks ---

export function useSessionNotes(sessionId: string | null) {
  return useQuery({
    queryKey: ["notes", "session", sessionId],
    queryFn: () => listNotes({ session_id: sessionId! }),
    enabled: !!sessionId,
  });
}

export function useGlobalNotes() {
  return useQuery({
    queryKey: ["notes", "global"],
    queryFn: () => listNotes({ global_only: true }),
  });
}

// --- Mutation hooks ---

export function useCreateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: NoteCreate) => createNote(body),
    onSuccess: (_data, variables) => {
      if (variables.session_id) {
        queryClient.invalidateQueries({
          queryKey: ["notes", "session", variables.session_id],
        });
      } else {
        queryClient.invalidateQueries({ queryKey: ["notes", "global"] });
      }
    },
  });
}

export function useUpdateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      noteId,
      body,
    }: {
      noteId: string;
      body: NoteUpdate;
      sessionId?: string | null;
    }) => updateNote(noteId, body),
    onSuccess: (_data, variables) => {
      // Invalidate both session and global since we may not know which one
      if (variables.sessionId) {
        queryClient.invalidateQueries({
          queryKey: ["notes", "session", variables.sessionId],
        });
      }
      queryClient.invalidateQueries({ queryKey: ["notes", "global"] });
    },
  });
}

export function useDeleteNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      noteId,
    }: {
      noteId: string;
      sessionId?: string | null;
    }) => deleteNote(noteId),
    onSuccess: (_data, variables) => {
      if (variables.sessionId) {
        queryClient.invalidateQueries({
          queryKey: ["notes", "session", variables.sessionId],
        });
      }
      queryClient.invalidateQueries({ queryKey: ["notes", "global"] });
    },
  });
}

// --- Autosave hook ---

export function useAutoSaveNote(
  noteId: string | null,
  sessionId: string | null | undefined,
) {
  const [saveStatus, setSaveStatus] = useState<
    "saved" | "saving" | "unsaved"
  >("saved");
  const updateMutation = useUpdateNote();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef<NoteUpdate | null>(null);
  // Keep a stable ref to mutate so debounce callbacks never go stale
  const mutateRef = useRef(updateMutation.mutate);
  mutateRef.current = updateMutation.mutate;

  const flush = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (pendingRef.current && noteId) {
      const body = pendingRef.current;
      pendingRef.current = null;
      setSaveStatus("saving");
      mutateRef.current(
        { noteId, body, sessionId },
        {
          onSuccess: () => setSaveStatus("saved"),
          onError: () => setSaveStatus("unsaved"),
        },
      );
    }
  }, [noteId, sessionId]);

  const debouncedSave = useCallback(
    (body: NoteUpdate) => {
      pendingRef.current = body;
      setSaveStatus("saving");
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        flush();
      }, 1000);
    },
    [flush],
  );

  // Flush on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (pendingRef.current && noteId) {
        mutateRef.current({
          noteId,
          body: pendingRef.current,
          sessionId,
        });
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [noteId]);

  return { saveStatus, debouncedSave, flush };
}
