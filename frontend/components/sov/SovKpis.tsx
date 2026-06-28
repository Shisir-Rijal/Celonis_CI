"use client";

import { useMemo } from "react";

import DashboardCard from "@components/geo/DashboardCard";
import { aggregateByCompany, aggregateByTheme } from "@/lib/sov/analysis";
import type { SovMention } from "@/lib/sov/types";

type Props = {
  mentions: SovMention[];
  totalCompanies: number;
};

const CELONIS = "celonis.com";

export default function SovKpis({ mentions, totalCompanies }: Props) {
  const perCompany = useMemo(() => aggregateByCompany(mentions), [mentions]);
  const perTheme = useMemo(() => aggregateByTheme(mentions), [mentions]);

  const total = mentions.length;
  const leader = perCompany[0];
  const celonis = perCompany.find((c) => c.company === CELONIS);
  const dominantTheme = perTheme[0];
  const activeCompanies = perCompany.length;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total mentions */}
      <DashboardCard className="flex flex-col gap-2">
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          Total mentions
        </span>
        <span className="text-[44px] leading-none font-medium tracking-tight text-primary-white">
          {total || "—"}
        </span>
        <span className="text-xs text-neutral-grey-20">In the selected period</span>
      </DashboardCard>

      {/* Celonis share — hero tile */}
      <DashboardCard className="relative overflow-hidden flex flex-col gap-2">
        <div className="absolute top-0 left-0 right-0 h-[3px] bg-secondary-green" />
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          Celonis share
        </span>
        <div className="flex items-baseline gap-3">
          <div className="gap-1">
            <span className="text-[44px] leading-none font-medium tracking-tight text-primary-white">
              {celonis ? (celonis.share * 100).toFixed(1) : "—"}
            </span>
            {celonis && <span className="text-lg text-neutral-grey-20 font-normal">%</span>}
          </div>
          <span className="text-sm text-neutral-grey-20">
            of all mentions
          </span>
        </div>
        <span className="text-xs text-neutral-grey-20">
          {celonis?.count ?? 0} of {total} mentions
        </span>
      </DashboardCard>

      {/* Leading competitor */}
      <DashboardCard className="flex flex-col gap-2">
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          Leading competitor
        </span>
        {leader ? (
          <>
            <span className="text-[32px] leading-tight font-medium tracking-tight text-primary-white truncate">
              {leader.company}
            </span>
            <span className="text-xs text-neutral-grey-20">
              {leader.count} mentions · {(leader.share * 100).toFixed(1)}%
            </span>
          </>
        ) : (
          <span className="text-[44px] leading-none font-medium text-primary-white">—</span>
        )}
      </DashboardCard>

      {/* Dominant theme */}
      <DashboardCard className="flex flex-col gap-2">
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          Dominant theme
        </span>
        {dominantTheme ? (
          <>
            <span className="text-[28px] leading-tight font-medium tracking-tight text-primary-white truncate">
              {dominantTheme.theme}
            </span>
            <span className="text-xs text-neutral-grey-20">
              {dominantTheme.count} mention{dominantTheme.count !== 1 ? "s" : ""}
            </span>
          </>
        ) : (
          <span className="text-[44px] leading-none font-medium text-primary-white">—</span>
        )}
        <span className="text-xs text-neutral-grey-20">
          {activeCompanies} of {totalCompanies} competitors active
        </span>
      </DashboardCard>
    </div>
  );
}
