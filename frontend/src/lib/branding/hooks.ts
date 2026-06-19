import { useQuery } from "@tanstack/react-query";

import { DUMMY_COLOR_INSIGHTS } from "./dummyColorInsights";
import { DUMMY_FONT_INSIGHTS } from "./dummyFontInsights";
import { DUMMY_IMAGERY_ARCHETYPES } from "./dummyImageryArchetypes";
import { DUMMY_IMAGERY_DIMENSIONS } from "./dummyImageryDimensions";
import { DUMMY_IMAGERY_SIMILARITY } from "./dummyImagerySimilarity";
import { DUMMY_LOGO_DIMENSIONS } from "./dummyLogoDimensions";
import { DUMMY_LOGO_PLACEMENT } from "./dummyLogoPlacement";
import { DUMMY_VISUAL_TRENDS } from "./dummyVisualTrends";
import type {
  ColorInsights,
  FontInsights,
  ImageryArchetypes,
  ImageryDimensionBreakdown,
  ImagerySimilarity,
  LogoDimensionBreakdown,
  LogoPlacement,
  VisualTrends,
} from "./types";

const STALE_TIME = 1000 * 60 * 60; // 1 h — matches the visuals node's semiannual cadence

/**
 * Once the branding agent + `/branding/color-insights` endpoint exist, replace
 * the queryFn below with `() => apiFetch<ColorInsights>("/branding/color-insights")`.
 * Nothing else in this file or any consuming component needs to change.
 */
export function useColorInsights() {
  return useQuery({
    queryKey: ["branding", "color-insights"],
    queryFn: () => Promise.resolve<ColorInsights>(DUMMY_COLOR_INSIGHTS),
    staleTime: STALE_TIME,
  });
}

/**
 * Same pattern as `useColorInsights` — swap the queryFn for a real
 * `apiFetch<FontInsights>("/branding/font-insights")` once that endpoint exists.
 */
export function useFontInsights() {
  return useQuery({
    queryKey: ["branding", "font-insights"],
    queryFn: () => Promise.resolve<FontInsights>(DUMMY_FONT_INSIGHTS),
    staleTime: STALE_TIME,
  });
}

/**
 * Same pattern again — swap the queryFn for a real
 * `apiFetch<VisualTrends>("/branding/visual-trends")` once that endpoint exists.
 */
export function useVisualTrends() {
  return useQuery({
    queryKey: ["branding", "visual-trends"],
    queryFn: () => Promise.resolve<VisualTrends>(DUMMY_VISUAL_TRENDS),
    staleTime: STALE_TIME,
  });
}

/**
 * Same pattern again — swap the queryFn for a real
 * `apiFetch<ImageryArchetypes>("/branding/imagery-archetypes")` once that endpoint exists.
 */
export function useImageryArchetypes() {
  return useQuery({
    queryKey: ["branding", "imagery-archetypes"],
    queryFn: () => Promise.resolve<ImageryArchetypes>(DUMMY_IMAGERY_ARCHETYPES),
    staleTime: STALE_TIME,
  });
}

/**
 * Same pattern again — swap the queryFn for a real
 * `apiFetch<ImageryDimensionBreakdown>("/branding/imagery-dimensions")` once that endpoint exists.
 */
export function useImageryDimensions() {
  return useQuery({
    queryKey: ["branding", "imagery-dimensions"],
    queryFn: () => Promise.resolve<ImageryDimensionBreakdown>(DUMMY_IMAGERY_DIMENSIONS),
    staleTime: STALE_TIME,
  });
}

/**
 * Same pattern again — swap the queryFn for a real
 * `apiFetch<ImagerySimilarity>("/branding/imagery-similarity")` once that endpoint exists.
 */
export function useImagerySimilarity() {
  return useQuery({
    queryKey: ["branding", "imagery-similarity"],
    queryFn: () => Promise.resolve<ImagerySimilarity>(DUMMY_IMAGERY_SIMILARITY),
    staleTime: STALE_TIME,
  });
}

/**
 * Same pattern again — swap the queryFn for a real
 * `apiFetch<LogoDimensionBreakdown>("/branding/logo-dimensions")` once that endpoint exists.
 */
export function useLogoDimensions() {
  return useQuery({
    queryKey: ["branding", "logo-dimensions"],
    queryFn: () => Promise.resolve<LogoDimensionBreakdown>(DUMMY_LOGO_DIMENSIONS),
    staleTime: STALE_TIME,
  });
}

/**
 * Same pattern again — swap the queryFn for a real
 * `apiFetch<LogoPlacement>("/branding/logo-placement")` once that endpoint exists.
 */
export function useLogoPlacement() {
  return useQuery({
    queryKey: ["branding", "logo-placement"],
    queryFn: () => Promise.resolve<LogoPlacement>(DUMMY_LOGO_PLACEMENT),
    staleTime: STALE_TIME,
  });
}
