"use client";

import { useState } from "react";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useFontInsights } from "@/lib/branding/hooks";
import { FontDiversityRow } from "./FontDiversityRow";

export function FontDiversity() {
  const { data, isLoading, isError, error } = useFontInsights();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggleCompany(company: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(company)) next.delete(company);
      else next.add(company);
      return next;
    });
  }

  if (isLoading) return <ZoneSkeleton height={220} />;
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.usage.length === 0) {
    return <ZoneEmpty message="No font usage analysis available yet." />;
  }

  const maxCount = Math.max(1, ...data.usage.map((u) => u.distinctFontCount));

  return (
    <DashboardCard
      label="Font Diversity"
      sublabel="How many distinct typefaces each competitor uses — script/language variants of the same family count once. Click a competitor to see which fonts."
    >
      <div className="flex flex-col gap-3">
        {data.usage.map((entry) => (
          <FontDiversityRow
            key={entry.company}
            entry={entry}
            max={maxCount}
            expanded={expanded.has(entry.company)}
            onToggle={() => toggleCompany(entry.company)}
          />
        ))}
      </div>
    </DashboardCard>
  );
}
