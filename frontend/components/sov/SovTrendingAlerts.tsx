"use client";

import { useMemo } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";

import DashboardCard from "@components/geo/DashboardCard";
import { computeThemeMomentum, type ThemeMomentum } from "@/lib/sov/analysis";
import type { SovMention } from "@/lib/sov/types";

type Props = {
  mentions: SovMention[];
};

export default function SovTrendingAlerts({ mentions }: Props) {
  const momentum = useMemo(() => computeThemeMomentum(mentions), [mentions]);

  if (!momentum) {
    return (
      <DashboardCard className="text-sm text-neutral-grey-20">
        Not enough monthly data to compute momentum — need at least two months of mentions.
      </DashboardCard>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <MomentumCard
        kind="rising"
        items={momentum.rising}
        emptyHint="No theme gained traction this month."
      />
      <MomentumCard
        kind="declining"
        items={momentum.declining}
        emptyHint="No theme lost traction this month."
      />
    </div>
  );
}

function MomentumCard({
  kind,
  items,
  emptyHint,
}: {
  kind: "rising" | "declining";
  items: ThemeMomentum[];
  emptyHint: string;
}) {
  const isRising = kind === "rising";
  const Icon = isRising ? TrendingUp : TrendingDown;
  const accent = isRising ? "text-secondary-green" : "text-[#f59e0b]";

  return (
    <DashboardCard className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Icon size={16} className={accent} />
        <span className={`text-[11px] tracking-[0.16em] uppercase font-medium ${accent}`}>
          {isRising ? "Rising themes" : "Declining themes"}
        </span>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-neutral-grey-20">{emptyHint}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((item) => (
            <li key={item.theme} className="flex items-baseline justify-between gap-4">
              <div className="flex flex-col">
                <span className="text-base text-primary-white font-medium truncate">
                  {item.theme}
                </span>
                <span className="text-xs text-neutral-grey-20 tabular-nums">
                  {item.previous} → {item.current} mentions
                </span>
              </div>
              <span className={`text-base font-medium tabular-nums shrink-0 ${accent}`}>
                {item.delta > 0 ? "+" : ""}
                {item.delta}
                <span className="text-xs text-neutral-grey-20 ml-2">
                  {item.previous === 0 ? "new" : `${item.pctChange > 0 ? "+" : ""}${Math.round(item.pctChange)}%`}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </DashboardCard>
  );
}
