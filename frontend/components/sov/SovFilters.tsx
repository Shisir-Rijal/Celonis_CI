"use client";

import { clsx } from "clsx";

import { THEMES, REGIONS } from "@/lib/sov/themes";
import type {
  SovFilters as SovFiltersState,
  SovPeriod,
  SovRegion,
  SovSourceFilter,
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

const SOURCE_OPTIONS: Array<{ value: SovSourceFilter; label: string }> = [
  { value: "news", label: "News" },
  { value: "seo", label: "SEO" },
  { value: "both", label: "Both" },
];

// Shared select style, matching EventsOverview pattern
const SELECT_CLS =
  "text-xs border border-white/10 rounded-sm px-3 py-1.5 bg-neutral-grey-30 text-primary-white " +
  "focus:outline-none focus:ring-1 focus:ring-secondary-green/50 cursor-pointer";

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
    <div className="flex flex-col gap-4 rounded-sm border border-neutral-grey-30 bg-primary-black/40 px-5 py-4">
      {/* Top row: Period + Source */}
      <div className="flex flex-wrap items-center gap-3">
        <FilterLabel>Period</FilterLabel>
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

        <span className="mx-2 h-4 w-px bg-neutral-grey-30" />

        <FilterLabel>Source</FilterLabel>
        <SegmentedToggle
          options={SOURCE_OPTIONS}
          value={filters.source}
          onChange={(v) => onChange({ ...filters, source: v })}
        />
      </div>

      {/* Themes row */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterLabel className="mr-1">Themes</FilterLabel>
        {THEMES.map((theme) => (
          <Chip
            key={theme}
            label={theme}
            active={filters.themes.includes(theme)}
            onClick={() => toggleTheme(theme)}
          />
        ))}
      </div>

      {/* Regions row */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterLabel className="mr-1">Regions</FilterLabel>
        {REGIONS.map((region) => (
          <Chip
            key={region}
            label={region}
            active={filters.regions.includes(region)}
            onClick={() => toggleRegion(region)}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal building blocks
// ---------------------------------------------------------------------------

function FilterLabel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "text-[11px] text-neutral-grey-20 uppercase tracking-[0.12em] font-medium",
        className,
      )}
    >
      {children}
    </span>
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

function SegmentedToggle<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-sm border border-white/10 overflow-hidden">
      {options.map((o, i) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={clsx(
            "text-xs px-3 py-1.5 transition-colors cursor-pointer",
            i > 0 && "border-l border-white/10",
            value === o.value
              ? "bg-secondary-green/15 text-secondary-green"
              : "text-neutral-grey-10 hover:text-primary-white hover:bg-white/5",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
