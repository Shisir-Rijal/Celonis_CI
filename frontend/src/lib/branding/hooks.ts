import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type {
  BrandArchetypes,
  BrandingAlerts,
  ColorInsights,
  FixedBrandArchetypes,
  FontInsights,
  ImageryArchetypes,
  ImageryDimensionBreakdown,
  ImagerySimilarity,
  LogoDimensionBreakdown,
  LogoPlacement,
  VideoInsights,
  VisualTrends,
} from "./types";

const STALE_TIME = 1000 * 60 * 60; // 1 h — matches the visuals node's semiannual cadence

export function useBrandArchetypes() {
  return useQuery({
    queryKey: ["branding", "archetypes"],
    queryFn: () => apiFetch<BrandArchetypes>("/branding/archetypes"),
    staleTime: STALE_TIME,
  });
}

export function useFixedBrandArchetypes() {
  return useQuery({
    queryKey: ["branding", "fixed-archetypes"],
    queryFn: () => apiFetch<FixedBrandArchetypes>("/branding/fixed-archetypes"),
    staleTime: STALE_TIME,
  });
}

export function useColorInsights() {
  return useQuery({
    queryKey: ["branding", "color-insights"],
    queryFn: () => apiFetch<ColorInsights>("/branding/color-insights"),
    staleTime: STALE_TIME,
  });
}

export function useFontInsights() {
  return useQuery({
    queryKey: ["branding", "font-insights"],
    queryFn: () => apiFetch<FontInsights>("/branding/font-insights"),
    staleTime: STALE_TIME,
  });
}

export function useBrandingAlerts() {
  return useQuery({
    queryKey: ["branding", "alerts"],
    queryFn: () => apiFetch<BrandingAlerts>("/branding/alerts"),
    staleTime: STALE_TIME,
  });
}

export function useVisualTrends() {
  return useQuery({
    queryKey: ["branding", "visual-trends"],
    queryFn: () => apiFetch<VisualTrends>("/branding/visual-trends"),
    staleTime: STALE_TIME,
  });
}

export function useImageryArchetypes() {
  return useQuery({
    queryKey: ["branding", "imagery-archetypes"],
    queryFn: () => apiFetch<ImageryArchetypes>("/branding/imagery-archetypes"),
    staleTime: STALE_TIME,
  });
}

export function useImageryDimensions() {
  return useQuery({
    queryKey: ["branding", "imagery-dimensions"],
    queryFn: () => apiFetch<ImageryDimensionBreakdown>("/branding/imagery-dimensions"),
    staleTime: STALE_TIME,
  });
}

export function useImagerySimilarity() {
  return useQuery({
    queryKey: ["branding", "imagery-similarity"],
    queryFn: () => apiFetch<ImagerySimilarity>("/branding/imagery-similarity"),
    staleTime: STALE_TIME,
  });
}

export function useLogoDimensions() {
  return useQuery({
    queryKey: ["branding", "logo-dimensions"],
    queryFn: () => apiFetch<LogoDimensionBreakdown>("/branding/logo-dimensions"),
    staleTime: STALE_TIME,
  });
}

export function useLogoPlacement() {
  return useQuery({
    queryKey: ["branding", "logo-placement"],
    queryFn: () => apiFetch<LogoPlacement>("/branding/logo-placement"),
    staleTime: STALE_TIME,
  });
}

/**
 * No dedicated frontend component consumes this yet — exposed so the data
 * is reachable (e.g. for a future VideoComparison component) without
 * further backend changes.
 */
export function useVideoInsights() {
  return useQuery({
    queryKey: ["branding", "video-insights"],
    queryFn: () => apiFetch<VideoInsights>("/branding/video-insights"),
    staleTime: STALE_TIME,
  });
}
