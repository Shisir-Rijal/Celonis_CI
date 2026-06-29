"use client";

import { clsx } from "clsx";

import { THEMES, REGIONS } from "@/lib/sov/themes";
import type {
  SovFilters as SovFiltersState,
  SovPeriod,
  SovRegion,
} from "@/lib/sov/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type Props = {
  filters: SovFiltersState;
  onChange: (next: SovFiltersState) => void;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PERIOD_OPTIONS: Array<{ value: SovPeriod; label: string }> = [
  { value: "1m", label: "Past month" },
  { value: "3m", label: "Past 3 months" },
  { value: "6m", label: "Past 6 months" },
  { value: "ytd", label: "Year to date" },
  { value: "all", label: "All time" },
];

const SELECT_CLS =
  "text-xs border border-white/10 rounded-sm px-3 py-1.5 bg-neutral-grey-30 text-primary-white " +
  "focus:outline-none focus:ring-1 focus:ring-secondary-green/50 cursor-pointer w-full";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SovFilters({ filters, onChange }: Props) {
  function toggleTheme(theme: string) {
    const set = new Set(filters.themes);
    if (set.has(theme)) set.delete(theme);
    else set.add(theme);
    onChange({ ...filters, themes: Array.from(set) });
  }

  function toggleRegion(region: SovRegion) {
    const set = new Set(filters.regions);
    if (set.has(region)) set.delete(region);
    else set.add(region);
    onChange({ ...filters, regions: Array.from(set) });
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 rounded-sm border border-neutral-grey-30 bg-primary-black/40 px-5 py-4">
      {/* Period */}
      <FilterBlock label="Period">
        <select
          className={SELECT_CLS}
          value={filters.period}
          onChange={(e) => onChange({ ...filters, period: e.target.value as SovPeriod })}
        >
          {PERIOD_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </FilterBlock>

      {/* Themes */}
      <FilterBlock label="Themes">
        <div className="flex flex-wrap gap-2">
          {THEMES.map((theme) => (
            <Chip
              key={theme}
              label={theme}
              active={filters.themes.includes(theme)}
              onClick={() => toggleTheme(theme)}
            />
          ))}
        </div>
      </FilterBlock>

      {/* Regions */}
      <FilterBlock label="Regions">
        <div className="flex flex-wrap gap-2">
          {REGIONS.map((region) => (
            <Chip
              key={region}
              label={region}
              active={filters.regions.includes(region)}
              onClick={() => toggleRegion(region)}
            />
          ))}
        </div>
      </FilterBlock>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal building blocks
// ---------------------------------------------------------------------------

function FilterBlock({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[11px] text-neutral-grey-20 uppercase tracking-[0.12em] font-medium">
        {label}
      </span>
      {children}
    </div>
  );
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "text-xs px-3 py-1 rounded-sm border transition-colors cursor-pointer",
        active
          ? "border-secondary-green text-secondary-green bg-secondary-green/10"
          : "border-white/10 text-neutral-grey-10 hover:border-white/30 hover:text-primary-white",
      )}
    >
      {label}
    </button>
  );
}
