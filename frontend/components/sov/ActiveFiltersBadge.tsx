"use client";

import { DEFAULT_SOV_FILTERS, type SovFilters } from "@/lib/sov/types";

const PERIOD_LABELS: Record<SovFilters["period"], string> = {
  "1m": "Past month",
  "3m": "Past 3 months",
  "6m": "Past 6 months",
  ytd: "Year to date",
  all: "All time",
};

type Props = {
  filters: SovFilters;
};

/**
 * Compact read-only pills that summarize which filters deviate from default.
 * Renders nothing when all filters are at their defaults.
 */
export default function ActiveFiltersBadge({ filters }: Props) {
  const pills: string[] = [];

  if (filters.period !== DEFAULT_SOV_FILTERS.period) {
    pills.push(PERIOD_LABELS[filters.period]);
  }
  for (const theme of filters.themes) pills.push(theme);
  for (const region of filters.regions) pills.push(region);

  if (pills.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5 max-w-md">
      {pills.map((pill) => (
        <span
          key={pill}
          className="text-[10px] px-2 py-0.5 rounded-sm bg-secondary-green/10 text-secondary-green border border-secondary-green/30"
        >
          {pill}
        </span>
      ))}
    </div>
  );
}
