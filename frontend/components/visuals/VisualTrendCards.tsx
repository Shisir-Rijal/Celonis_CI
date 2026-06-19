"use client";

import { Palette, Type, Aperture, Image as ImageIcon, ArrowUp, ArrowDown, Minus } from "lucide-react";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useVisualTrends } from "@/lib/branding/hooks";
import type { TrendDirection, VisualElementTrend } from "@/lib/branding/types";

const ELEMENT_ICONS: Record<VisualElementTrend["element"], React.ReactNode> = {
  Color: <Palette size={16} />,
  Font: <Type size={16} />,
  Logo: <Aperture size={16} />,
  Imagery: <ImageIcon size={16} />,
};

const DIRECTION_STYLE: Record<TrendDirection, { icon: React.ReactNode; label: string; className: string }> = {
  up: { icon: <ArrowUp size={12} strokeWidth={2.5} />, label: "Trending up", className: "text-success" },
  down: { icon: <ArrowDown size={12} strokeWidth={2.5} />, label: "Trending down", className: "text-error" },
  flat: { icon: <Minus size={12} strokeWidth={2.5} />, label: "Steady", className: "text-neutral-grey-20" },
};

function TrendCard({ trend }: { trend: VisualElementTrend }) {
  const direction = DIRECTION_STYLE[trend.direction];
  return (
    <DashboardCard className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm font-medium text-primary-white">
          <span className="text-neutral-grey-20">{ELEMENT_ICONS[trend.element]}</span>
          {trend.element}
        </span>
        <span className={`flex items-center gap-1 text-xs font-medium ${direction.className}`}>
          {direction.icon}
          {direction.label}
        </span>
      </div>
      <p className="text-xs text-neutral-grey-20 leading-relaxed">{trend.summary}</p>
    </DashboardCard>
  );
}

export function VisualTrendCards() {
  const { data, isLoading, isError, error } = useVisualTrends();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <ZoneSkeleton key={i} height={120} />
        ))}
      </div>
    );
  }
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.trends.length === 0) {
    return <ZoneEmpty message="No trend analysis available yet." />;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {data.trends.map((trend) => (
        <TrendCard key={trend.element} trend={trend} />
      ))}
    </div>
  );
}
