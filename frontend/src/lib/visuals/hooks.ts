import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { VisualsResponse } from "./types";

const STALE_TIME = 1000 * 60 * 60; // 1 h — visuals only change when re-scraped (semiannual tier)

export function useVisuals() {
  return useQuery({
    queryKey: ["visuals"],
    queryFn: () => apiFetch<VisualsResponse>("/visuals"),
    staleTime: STALE_TIME,
  });
}
