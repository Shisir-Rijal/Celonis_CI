"use client";

import { useMemo, useState } from "react";

import PageToolbar from "@components/geo/PageToolbar";
import SectionHeader from "@components/geo/SectionHeader";
import SovFilters from "@components/sov/SovFilters";
import SovKpis from "@components/sov/SovKpis";
import SovShareDonut from "@components/sov/SovShareDonut";
import SovTrendChart from "@components/sov/SovTrendChart";
import SovThemeBreakdown from "@components/sov/SovThemeBreakdown";
import SovRegionChart from "@components/sov/SovRegionChart";
import SovTrendingAlerts from "@components/sov/SovTrendingAlerts";
import SovMentionList from "@components/sov/SovMentionList";
import { applyFilters, hasActiveFilter } from "@/lib/sov/analysis";
import { useSov } from "@/lib/sov/hooks";
import { useCompetitorColors } from "@/lib/competitors/hooks";
import { DEFAULT_SOV_FILTERS, type SovFilters as SovFiltersState } from "@/lib/sov/types";

function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const minutes = Math.floor((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  return `${days} d ago`;
}

export default function SovPage() {
  const { data, isLoading, error } = useSov();
  const { data: brandColors = {} } = useCompetitorColors();

  const [filters, setFilters] = useState<SovFiltersState>(DEFAULT_SOV_FILTERS);

  const filteredMentions = useMemo(
    () => applyFilters(data?.mentions ?? [], filters),
    [data, filters],
  );

  const allCompanies = useMemo(
    () => [...(data?.companies ?? [])].sort(),
    [data?.companies],
  );

  const updatedAt = useMemo(
    () => formatRelativeTime(data?.latest_run_at),
    [data?.latest_run_at]
  );

  const subtitleDetail = (() => {
    if (isLoading) return "loading mentions…";
    if (error) return "failed to load mentions";
    if (!data) return "no data yet";
    const totalLabel = hasActiveFilter(filters)
      ? `${filteredMentions.length} of ${data.total} mentions (filtered)`
      : `${data.total} classified mentions`;
    return `${totalLabel} across ${data.companies.length} competitors`;
  })();

  return (
    <div className="w-full flex flex-col gap-24">
      {/* Page header */}
      <header className="flex items-end justify-between gap-6 pb-6 border-b border-neutral-grey-30">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] tracking-[0.18em] uppercase text-neutral-grey-20 font-medium">
            Celonis and Competitors
          </span>
          <h1 className="text-3xl font-medium text-primary-white leading-none">
            Share of Voice
          </h1>
          <p className="mt-2 text-sm text-neutral-grey-20 max-w-xl">
            Mentions of Celonis and its tracked competitors across news and SEO,
            classified by theme and region —{" "}
            <span className="text-primary-white font-medium">{subtitleDetail}</span>.
          </p>
        </div>
        <PageToolbar runtime="manual / weekly" updatedAt={updatedAt} agentsRunning={0} />
      </header>

      {/* Zone 1 — Global filter bar */}
      <section>
        <SectionHeader
          label="Filters"
          description="Theme, region, period and source filters applied across all visualizations."
          action={
            hasActiveFilter(filters) ? (
              <button
                type="button"
                onClick={() => setFilters(DEFAULT_SOV_FILTERS)}
                className="text-xs text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer"
              >
                Clear filters ×
              </button>
            ) : undefined
          }
        />
        <SovFilters filters={filters} onChange={setFilters} />
      </section>

      {/* Phase 4 — KPIs */}
      <section>
        <SectionHeader
          label="At a glance"
          description="Total mentions, leading competitor, dominant theme and active companies in the selected period."
        />
        <SovKpis mentions={filteredMentions} totalCompanies={allCompanies.length} />
      </section>

      {/* Phase 4 — Share of Voice headline */}
      <section>
        <SectionHeader
          label="Share of Voice"
          description="Each competitor's share of all relevant mentions in the selected period."
        />
        <SovShareDonut
          mentions={filteredMentions}
          allCompanies={allCompanies}
          brandColors={brandColors}
        />
      </section>

      {/* Phase 5 — Trend over time */}
      <section>
        <SectionHeader
          label="Trend over time"
          description="Mentions per month per competitor — who's gaining, who's losing visibility."
        />
        <SovTrendChart
          mentions={filteredMentions}
          allCompanies={allCompanies}
          brandColors={brandColors}
        />
      </section>

      {/* Phase 5 — Theme breakdown */}
      <section>
        <SectionHeader
          label="Themes"
          description="Which competitor dominates which theme — Process Mining, Agentic AI, ERP & SAP and others."
        />
        <SovThemeBreakdown
          mentions={filteredMentions}
          allCompanies={allCompanies}
          brandColors={brandColors}
        />
      </section>

      {/* Phase 5 — Regional distribution */}
      <section>
        <SectionHeader
          label="Regions"
          description="DACH, Europe, NA, APAC and Global mention volumes — note that SEO mentions are always Global."
        />
        <SovRegionChart mentions={filteredMentions} />
      </section>

      {/* Trending themes — rising / declining */}
      <section>
        <SectionHeader
          label="Trending themes"
          description="Topics gaining and losing momentum compared to the previous month."
        />
        <SovTrendingAlerts mentions={filteredMentions} />
      </section>

      {/* Mention detail list */}
      <section>
        <SectionHeader
          label="Mentions"
          description="All individual mentions with title, themes, region and source — filterable above."
        />
        <SovMentionList
          mentions={filteredMentions}
          allCompanies={allCompanies}
          brandColors={brandColors}
        />
      </section>
    </div>
  );
}
