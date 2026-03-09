"use client";

import { useSession } from "next-auth/react";
import { TrackEditor } from "@/components/admin/TrackEditor";

const ADMIN_EMAIL = "p.zientala.1995@gmail.com";

export default function TrackEditorPage() {
  const { data: session, status } = useSession();

  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-foreground">
        <div className="animate-pulse text-lg">Loading...</div>
      </div>
    );
  }

  if (!session?.user?.email || session.user.email !== ADMIN_EMAIL) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-foreground">
        <div className="rounded-lg border border-destructive/30 bg-card p-8 text-center">
          <h1 className="text-xl font-semibold text-destructive">
            Access Denied
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            This page is restricted to administrators.
          </p>
        </div>
      </div>
    );
  }

  return <TrackEditor />;
}
