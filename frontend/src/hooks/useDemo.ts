import { useQuery } from "@tanstack/react-query";
import { getDemoSession } from "@/lib/api";

export const DEMO_SESSION_ID = "barber_motorsports_p_20260222_b101ba9c";

export function isDemoSession(sessionId: string | null | undefined): boolean {
  return sessionId === DEMO_SESSION_ID;
}

export function useDemoSession() {
  const { data } = useQuery({
    queryKey: ["demo-session"],
    queryFn: getDemoSession,
    staleTime: 5 * 60 * 1000, // 5 min
    retry: 1,
  });
  return {
    demoSessionId: data?.session_id ?? null,
    isAvailable: data?.available ?? false,
  };
}
