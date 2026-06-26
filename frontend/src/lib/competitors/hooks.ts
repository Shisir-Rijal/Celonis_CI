import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export function useCompetitorColors() {
  return useQuery({
    queryKey: ["competitor-colors"],
    queryFn: () => apiFetch<Record<string, string>>("/competitors/colors"),
    staleTime: 1000 * 60 * 60, // 1 h — colors change only when visuals are re-scraped
  });
}