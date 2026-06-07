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

export function useGeoIntelligence(company: string) {
  return useQuery({
    queryKey: ["geo-intelligence", company],
    queryFn: () =>
      apiFetch<GeoIntelligenceResponse>(
        `/brand/geo-intelligence/${encodeURIComponent(company)}`
      ),
    staleTime: STALE_TIME,
    enabled: Boolean(company),
  });
}

export function useGeoShareOfVoice(company: string) {
  return useQuery({
    queryKey: ["geo-share-of-voice", company],
    queryFn: () =>
      apiFetch<ShareOfVoiceResponse>(
        `/brand/geo-intelligence/${encodeURIComponent(company)}/share-of-voice`
      ),
    staleTime: STALE_TIME,
    enabled: Boolean(company),
  });
}

export function useGeoStrategicMaps(company: string) {
  return useQuery({
    queryKey: ["geo-strategic-maps", company],
    queryFn: () =>
      apiFetch<StrategicMapsResponse>(
        `/brand/geo-intelligence/${encodeURIComponent(company)}/strategic-maps`
      ),
    staleTime: STALE_TIME,
    enabled: Boolean(company),
  });
}

export function useGeoDeepDive(company: string) {
  return useQuery({
    queryKey: ["geo-deep-dive", company],
    queryFn: () =>
      apiFetch<DeepDiveResponse>(
        `/brand/geo-intelligence/${encodeURIComponent(company)}/deep-dive`
      ),
    staleTime: STALE_TIME,
    enabled: Boolean(company),
  });
}
