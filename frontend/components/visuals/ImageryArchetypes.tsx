"use client";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useImageryArchetypes } from "@/lib/branding/hooks";
import { ImageryArchetypeCard } from "./ImageryArchetypeCard";

const LABEL = "Archetype Cards";
const SUBLABEL =
  "Distinct visual style clusters the branding agent groups competitors' imagery into, based on recurring patterns across the images scraped from their sites.";

export function ImageryArchetypes() {
  const { data, isLoading, isError, error } = useImageryArchetypes();

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
    return <ZoneEmpty message="No imagery archetype analysis available yet." />;
  }

  return (
    <DashboardCard label={LABEL} sublabel={SUBLABEL}>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {data.archetypes.map((archetype) => (
          <ImageryArchetypeCard key={archetype.name} archetype={archetype} />
        ))}
      </div>
    </DashboardCard>
  );
}
