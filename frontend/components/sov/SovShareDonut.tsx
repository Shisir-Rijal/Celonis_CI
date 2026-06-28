"use client";

import { useMemo } from "react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
} from "recharts";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneEmpty } from "@components/geo/ZoneState";
import { aggregateByCompany } from "@/lib/sov/analysis";
import { getCompetitorColor } from "@/lib/competitors/colors";
import type { SovMention } from "@/lib/sov/types";

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};

type Props = {
  mentions: SovMention[];
  allCompanies: string[];
  brandColors: Record<string, string>;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DonutTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const entry = payload[0];
  const { company, count, share } = entry.payload;
  return (
    <div
      className="rounded-lg border border-white/10 bg-neutral-grey-30 px-3 py-2.5 shadow-lg text-xs"
      style={CHART_FONT}
    >
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: entry.color ?? entry.payload.fill }} />
        <span className="font-medium text-primary-white">{company}</span>
      </div>
      <div className="mt-1 text-neutral-grey-20 tabular-nums">
        {count} mentions · {(share * 100).toFixed(1)}%
      </div>
    </div>
  );
}

export default function SovShareDonut({ mentions, allCompanies, brandColors }: Props) {
  const data = useMemo(() => aggregateByCompany(mentions), [mentions]);

  if (data.length === 0) {
    return (
      <DashboardCard label="Share of Voice" sublabel="Each competitor's share of all relevant mentions">
        <ZoneEmpty message="No mentions in the selected period." />
      </DashboardCard>
    );
  }

  return (
    <DashboardCard label="Share of Voice" sublabel="Each competitor's share of all relevant mentions">
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 items-center">
        {/* Donut */}
        <div style={CHART_FONT}>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={data}
                dataKey="count"
                nameKey="company"
                cx="50%"
                cy="50%"
                innerRadius={80}
                outerRadius={130}
                paddingAngle={1}
                stroke="rgba(0,0,0,0)"
              >
                {data.map((entry) => (
                  <Cell
                    key={entry.company}
                    fill={getCompetitorColor(entry.company, allCompanies, brandColors)}
                  />
                ))}
              </Pie>
              <Tooltip content={<DonutTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <ul className="flex flex-col gap-2 min-w-[200px]">
          {data.map((entry) => (
            <li key={entry.company} className="flex items-center gap-3 text-xs">
              <span
                className="w-2.5 h-2.5 rounded-sm shrink-0"
                style={{ background: getCompetitorColor(entry.company, allCompanies, brandColors) }}
              />
              <span className="text-primary-white truncate flex-1">{entry.company}</span>
              <span className="text-neutral-grey-20 tabular-nums">
                {(entry.share * 100).toFixed(1)}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </DashboardCard>
  );
}
