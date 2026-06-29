import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { SovListResponse } from "./types";

const STALE_TIME = 1000 * 60 * 5;

/**
 * Fetch all persisted SoV mentions in one shot.
 *
 * Mirrors the /events pattern: backend ships the full list, frontend
 * aggregates and filters client-side. Cached for 5 min via React Query.
 */
export function useSov() {
  return useQuery({
    queryKey: ["sov"],
    queryFn: () => apiFetch<SovListResponse>("/sov"),
    staleTime: STALE_TIME,
  });
}
