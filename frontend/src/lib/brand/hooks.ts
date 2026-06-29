/**
 * TanStack Query hooks for the Brand Intelligence API.
 *
 * Each hook wraps `apiFetch` (which auto-attaches the JWT) and returns a
 * typed query result. All hooks are keyed by `[scope, company]` so that
 * switching companies invalidates correctly.
 */

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type {
  DeepDiveResponse,
  GeoIntelligenceResponse,
  ShareOfVoiceResponse,
  StrategicMapsResponse,
} from "@/lib/brand/types";

const STALE_TIME = 1000 * 60 * 5; // 5 minutes

export function useGeoIntelligence(company: string, llm?: string | null) {
  return useQuery({
    queryKey: ["geo-intelligence", company, llm ?? null],
    queryFn: () => {
      const params = llm ? `?llm=${encodeURIComponent(llm)}` : "";
      return apiFetch<GeoIntelligenceResponse>(
        `/brand/geo-intelligence/${encodeURIComponent(company)}${params}`
      );
    },
    staleTime: STALE_TIME,
    enabled: Boolean(company),
  });
}

export function useGeoShareOfVoice(company: string, llm?: string | null) {
  return useQuery({
    queryKey: ["geo-share-of-voice", company, llm ?? null],
    queryFn: () => {
      const params = llm ? `?llm=${encodeURIComponent(llm)}` : "";
      return apiFetch<ShareOfVoiceResponse>(
        `/brand/geo-intelligence/${encodeURIComponent(company)}/share-of-voice${params}`
      );
    },
    staleTime: STALE_TIME,
    enabled: Boolean(company),
  });
}

export function useGeoStrategicMaps(company: string, llm?: string | null) {
  return useQuery({
    queryKey: ["geo-strategic-maps", company, llm ?? null],
    queryFn: () => {
      const params = llm ? `?llm=${encodeURIComponent(llm)}` : "";
      return apiFetch<StrategicMapsResponse>(
        `/brand/geo-intelligence/${encodeURIComponent(company)}/strategic-maps${params}`
      );
    },
    staleTime: STALE_TIME,
    enabled: Boolean(company),
  });
}

export function useGeoDeepDive(company: string, llm?: string | null) {
  return useQuery({
    queryKey: ["geo-deep-dive", company, llm ?? null],
    queryFn: () => {
      const params = llm ? `?llm=${encodeURIComponent(llm)}` : "";
      return apiFetch<DeepDiveResponse>(
        `/brand/geo-intelligence/${encodeURIComponent(company)}/deep-dive${params}`
      );
    },
    staleTime: STALE_TIME,
    enabled: Boolean(company),
  });
}
