"use client";

import { useMemo } from "react";

import { useEvents } from "@/lib/events/hooks";
import { computeAnalysis } from "@/lib/events/analysis";
import DashboardCard from "@components/brand/DashboardCard";
import AlertCard from "@components/brand/AlertCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/brand/ZoneState";

export default function EventsAlerts() {
  const { data, isLoading, isError } = useEvents();

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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => <ZoneSkeleton key={i} height={180} />)}
      </div>
    );
  }

  if (isError) return <ZoneError />;
  if (!analysis) return <ZoneEmpty message="No analysis available yet." />;

  const { coverageGap, topicGap, momentum } = analysis;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Coverage Gap */}
      {coverageGap ? (
        <AlertCard
          category="Coverage Gap"
          text={`Celonis has no in-person events in ${coverageGap.region}, where ${coverageGap.competitorEvents} competitor event${coverageGap.competitorEvents !== 1 ? "s" : ""} are active.`}
          priority={coverageGap.competitorEvents >= 5 ? "high" : "medium"}
          recommendation="Consider attending or sponsoring events in this region."
        />
      ) : (
        <DashboardCard label="Coverage Gap">
          <p className="text-sm text-neutral-grey-20">
            No regional gaps — Celonis is present in all active in-person regions.
          </p>
        </DashboardCard>
      )}

      {/* Topic Gap */}
      {topicGap ? (
        <AlertCard
          category="Topic Gap"
          text={`Competitors have ${topicGap.otherCount} events on "${topicGap.topic}" while Celonis has ${topicGap.celonisCount === 0 ? "none" : topicGap.celonisCount}.`}
          priority={topicGap.celonisCount === 0 ? "high" : "medium"}
          recommendation="Evaluate whether this topic aligns with Celonis messaging."
        />
      ) : (
        <DashboardCard label="Topic Gap">
          <p className="text-sm text-neutral-grey-20">No topic gaps detected.</p>
        </DashboardCard>
      )}

      {/* Momentum */}
      {momentum ? (
        <AlertCard
          category="Momentum"
          text={
            momentum.lastYear === 0
              ? `Celonis has ${momentum.thisYear} event${momentum.thisYear !== 1 ? "s" : ""} tracked in ${new Date().getFullYear()}. No prior-year data to compare against.`
              : `Celonis event volume is ${
                  momentum.direction === "up"
                    ? `up ${momentum.pctChange}%`
                    : momentum.direction === "down"
                    ? `down ${Math.abs(momentum.pctChange)}%`
                    : "flat"
                } year-over-year (${momentum.lastYear} → ${momentum.thisYear} events).`
          }
          priority={
            momentum.direction === "down" && Math.abs(momentum.pctChange) >= 30
              ? "high"
              : momentum.direction === "up"
              ? "low"
              : "medium"
          }
        />
      ) : (
        <DashboardCard label="Momentum">
          <p className="text-sm text-neutral-grey-20">
            No Celonis events found to assess momentum.
          </p>
        </DashboardCard>
      )}
    </div>
  );
}