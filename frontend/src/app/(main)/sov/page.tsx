"use client";

import { useMemo } from "react";

import PageToolbar from "@components/geo/PageToolbar";
import SectionHeader from "@components/geo/SectionHeader";
import { useSov } from "@/lib/sov/hooks";

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

  const updatedAt = useMemo(
    () => formatRelativeTime(data?.latest_run_at),
    [data?.latest_run_at]
  );

  const subtitleDetail = (() => {
    if (isLoading) return "loading mentions…";
    if (error) return "failed to load mentions";
    if (!data) return "no data yet";
    return `${data.total} classified mentions across ${data.companies.length} competitors`;
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

      {/* Phase 3 — global filter bar */}
      <section>
        <SectionHeader
          label="Filters"
          description="Theme, region, period and source filters applied across all visualizations."
        />
        <PhasePlaceholder phase={3} note="Global filter bar lands here." />
      </section>

      {/* Phase 4 — KPIs */}
      <section>
        <SectionHeader
          label="At a glance"
          description="Total mentions, leading competitor, dominant theme and active companies in the selected period."
        />
        <PhasePlaceholder phase={4} note="Four KPI tiles." />
      </section>

      {/* Phase 4 — Share of Voice headline */}
      <section>
        <SectionHeader
          label="Share of Voice"
          description="Each competitor's share of all relevant mentions in the selected period."
        />
        <PhasePlaceholder phase={4} note="Donut chart with competitor colors." />
      </section>

      {/* Phase 5 — Trend over time */}
      <section>
        <SectionHeader
          label="Trend over time"
          description="Mentions per month per competitor — who's gaining, who's losing visibility."
        />
        <PhasePlaceholder phase={5} note="Multi-line chart, one line per competitor." />
      </section>

      {/* Phase 5 — Theme breakdown */}
      <section>
        <SectionHeader
          label="Themes"
          description="Which competitor dominates which theme — Process Mining, Agentic AI, ERP & SAP and others."
        />
        <PhasePlaceholder phase={5} note="Stacked horizontal bar: themes × competitors." />
      </section>

      {/* Phase 5 — Regional distribution */}
      <section>
        <SectionHeader
          label="Regions"
          description="DACH, Europe, NA, APAC and Global mention volumes — note that SEO mentions are always Global."
        />
        <PhasePlaceholder phase={5} note="Bar chart per region." />
      </section>

      {/* Phase 6 — Rising / Declining themes */}
      <section>
        <SectionHeader
          label="Trending themes"
          description="Topics gaining and losing momentum compared to the previous month."
        />
        <PhasePlaceholder phase={6} note="Two alert cards: rising / declining." />
      </section>

      {/* Phase 6 — Mention detail list */}
      <section>
        <SectionHeader
          label="Mentions"
          description="All individual mentions with title, themes, region and source — filterable."
        />
        <PhasePlaceholder phase={6} note="Mention cards with their own scoped filters." />
      </section>
    </div>
  );
}

function PhasePlaceholder({ phase, note }: { phase: number; note: string }) {
  return (
    <div className="rounded-sm border border-dashed border-neutral-grey-30 bg-primary-black/40 px-6 py-8 flex flex-col gap-1">
      <span className="text-[11px] tracking-[0.18em] uppercase text-neutral-grey-20 font-medium">
        Phase {phase}
      </span>
      <span className="text-sm text-neutral-grey-10">{note}</span>
    </div>
  );
}
