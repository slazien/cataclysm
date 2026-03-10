"use client";

import { type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "@/lib/api";

function isAuthError(error: unknown): boolean {
  return error instanceof Error && (error.message.includes("401") || error.message.includes("403"));
}

async function getAdminMe(): Promise<{ email: string; name: string }> {
  return fetchApi("/api/admin/me");
}

export function AdminGate({ children }: { children: ReactNode }) {
  const adminQuery = useQuery({
    queryKey: ["admin", "me"],
    queryFn: getAdminMe,
    retry: false,
  });

  if (adminQuery.isPending) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-100">
        <div className="animate-pulse text-lg">Loading...</div>
      </div>
    );
  }

  if (isAuthError(adminQuery.error)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <div className="max-w-md rounded-xl border border-rose-700/40 bg-slate-900/80 p-6 text-center">
          <h1 className="text-xl font-semibold text-rose-300">Access denied</h1>
          <p className="mt-2 text-sm text-slate-300">
            This page is restricted to configured administrator accounts.
          </p>
        </div>
      </div>
    );
  }

  if (adminQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <div className="max-w-md rounded-xl border border-rose-700/40 bg-slate-900/80 p-6 text-center">
          <h1 className="text-xl font-semibold text-rose-300">Admin check failed</h1>
          <p className="mt-2 text-sm text-slate-300">{(adminQuery.error as Error).message}</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
