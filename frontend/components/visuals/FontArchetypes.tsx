"use client";

import { useMemo } from "react";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useFontInsights } from "@/lib/branding/hooks";
import { useGoogleFonts } from "@/lib/visuals/useGoogleFonts";
import { FontArchetypeCard } from "./FontArchetypeCard";

const LABEL = "Font Archetypes";
const SUBLABEL =
  "Typeface style + personality clusters the branding agent groups competitors into — what feeling each cluster's fonts are chosen to convey.";

export function FontArchetypes() {
  const { data, isLoading, isError, error } = useFontInsights();

  const sampleFontNames = useMemo(
    () => data?.archetypes.map((a) => a.sampleFontName) ?? [],
    [data]
  );
  useGoogleFonts(sampleFontNames);

  if (isLoading) {
    return (
      <DashboardCard label={LABEL} sublabel={SUBLABEL}>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <ZoneSkeleton key={i} height={280} />
          ))}
        </div>
      </DashboardCard>
    );
  }
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.archetypes.length === 0) {
    return <ZoneEmpty message="No font archetype analysis available yet." />;
  }

  return (
    <DashboardCard label={LABEL} sublabel={SUBLABEL}>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {data.archetypes.map((archetype) => (
          <FontArchetypeCard key={archetype.name} archetype={archetype} />
        ))}
      </div>
    </DashboardCard>
  );
}
