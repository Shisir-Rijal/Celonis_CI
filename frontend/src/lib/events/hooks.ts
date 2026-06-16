import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { EventsResponse } from "./types";

const STALE_TIME = 1000 * 60 * 5;

export function useEvents() {
  return useQuery({
    queryKey: ["events"],
    queryFn: () => apiFetch<EventsResponse>("/events"),
    staleTime: STALE_TIME,
  });
}
