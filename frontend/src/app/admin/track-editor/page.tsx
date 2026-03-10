"use client";

import { AdminGate } from "@/components/admin/AdminGate";
import { TrackEditor } from "@/components/admin/TrackEditor";

export default function TrackEditorPage() {
  return (
    <AdminGate>
      <TrackEditor />
    </AdminGate>
  );
}
