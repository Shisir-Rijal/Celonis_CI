"use client";

import { useMemo } from "react";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useFontInsights } from "@/lib/branding/hooks";
import { useGoogleFonts } from "@/lib/visuals/useGoogleFonts";
import type { SimilarFontGroup } from "@/lib/branding/types";
import { SimilarGroups } from "./SimilarGroups";

export function FontComparison() {
  const { data, isLoading, isError, error } = useFontInsights();

  const sampleFontNames = useMemo(
    () => data?.similarFonts.map((g) => g.sampleFontName) ?? [],
    [data]
  );
  useGoogleFonts(sampleFontNames);

  if (isLoading) return <ZoneSkeleton height={220} />;
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.similarFonts.length === 0) {
    return <ZoneEmpty message="No font analysis available yet." />;
  }

  return (
    <DashboardCard label="Similar Fonts" sublabel="Competitors converging on the same typeface style">
      <SimilarGroups<SimilarFontGroup>
        groups={data.similarFonts}
        emptyMessage="No close font overlaps detected."
        label={(group) => group.sharedFontFamily}
        renderPreview={(group) => (
          <span
            style={{ fontFamily: `"${group.sampleFontName}", sans-serif` }}
            className="text-base text-primary-white leading-none px-2 py-1 rounded-sm bg-white/5 border border-white/10"
          >
            Aa
          </span>
        )}
      />
    </DashboardCard>
  );
}
