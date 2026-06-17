"use client";

import { useMemo } from "react";

import { useEvents } from "@/lib/events/hooks";
import { computeAnalysis } from "@/lib/events/analysis";
import DashboardCard from "@components/brand/DashboardCard";
import { ZoneSkeleton, ZoneError } from "@components/brand/ZoneState";

export default function EventsKpis() {
  const { data, isLoading, isError, error } = useEvents();

  const allCompanies = useMemo(
    () => [...new Set((data?.events ?? []).map((e) => e.company))].sort(),
    [data]
  );

  const analysis = useMemo(
    () => (data?.events.length ? computeAnalysis(data.events, allCompanies) : null),
    [data, allCompanies]
  );

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-2 gap-4">
        {Array.from({ length: 3 }).map((_, i) => <ZoneSkeleton key={i} height={150} />)}
      </div>
    );
  }

  if (isError) return <ZoneError message={(error as Error)?.message} />;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {/* Trending Topic */}
      <DashboardCard className="flex flex-col gap-2">
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          Trending topic
        </span>
        <span className="text-[44px] leading-none font-medium tracking-tight text-primary-white">
          {analysis?.total ?? "—"}
        </span>
        <span className="text-xs text-neutral-grey-20">Over the last 3 months</span>
      </DashboardCard>

      {/* Total Events */}
      <DashboardCard className="flex flex-col gap-2">
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          Total events tracked
        </span>
        <span className="text-[44px] leading-none font-medium tracking-tight text-primary-white">
          {analysis?.total ?? "—"}
        </span>
        <span className="text-xs text-neutral-grey-20">Across all competitors</span>
      </DashboardCard>

      {/* Celonis Event Share — hero tile */}
      <DashboardCard className="relative overflow-hidden flex flex-col gap-2">
        <div className="absolute top-0 left-0 right-0 h-[3px] bg-secondary-green" />
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          Celonis event share
        </span>
        <div className="flex items-baseline gap-1">
          <span className="text-[44px] leading-none font-medium tracking-tight text-primary-white">
            {analysis ? analysis.celonisShare.toFixed(1) : "—"}
          </span>
          {analysis && <span className="text-lg text-neutral-grey-20 font-normal">%</span>}
        </div>
        <span className="text-xs text-neutral-grey-20">
          {analysis?.celonisCount ?? 0} of {analysis?.total ?? 0} events
        </span>
      </DashboardCard>

      {/* Most Active Competitor */}
      <DashboardCard className="flex flex-col gap-2">
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          Most active competitor
        </span>
        {analysis?.mostActiveCompetitor ? (
          <>
            <span className="text-[32px] leading-tight font-medium tracking-tight text-primary-white truncate">
              {analysis.mostActiveCompetitor.name}
            </span>
            <span className="text-xs text-neutral-grey-20">
              {analysis.mostActiveCompetitor.count} events tracked
            </span>
          </>
        ) : (
          <span className="text-[44px] leading-none font-medium text-primary-white">—</span>
        )}
      </DashboardCard>
    </div>
  );
}