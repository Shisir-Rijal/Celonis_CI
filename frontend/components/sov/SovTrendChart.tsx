"use client";

import { useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneEmpty } from "@components/geo/ZoneState";
import { aggregateByMonth } from "@/lib/sov/analysis";
import { getCompetitorColor } from "@/lib/competitors/colors";
import type { SovMention } from "@/lib/sov/types";

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};
const GRID_COLOR = "rgba(255,255,255,0.08)";
const AXIS_NUM = { fill: "#767676", fontSize: 11 };
const AXIS_CAT = { fill: "#CBCBCB", fontSize: 11 };

type Props = {
  mentions: SovMention[];
  allCompanies: string[];
  brandColors: Record<string, string>;
};

function formatMonth(ym: string): string {
  // "2026-03" → "Mar '26"
  const [y, m] = ym.split("-").map(Number);
  if (!y || !m) return ym;
  const d = new Date(y, m - 1, 1);
  return d.toLocaleString("en-US", { month: "short" }) + ` '${String(y).slice(2)}`;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  // Sort entries desc by value so highest is on top
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rows = [...payload].sort((a: any, b: any) => (b.value ?? 0) - (a.value ?? 0));
  return (
    <div
      className="rounded-lg border border-white/10 bg-neutral-grey-30 px-3 py-2.5 shadow-lg text-xs"
      style={CHART_FONT}
    >
      <div className="font-medium text-primary-white mb-1.5">{formatMonth(label)}</div>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {rows.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2 mt-1">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: entry.color }} />
          <span className="text-neutral-grey-20 truncate max-w-[160px]">{entry.name}</span>
          <span className="ml-auto font-medium text-primary-white pl-4 tabular-nums">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function SovTrendChart({ mentions, allCompanies, brandColors }: Props) {
  const data = useMemo(
    () => aggregateByMonth(mentions, allCompanies),
    [mentions, allCompanies],
  );

  // Only chart companies that actually appear in the filtered window
  const activeCompanies = useMemo(() => {
    const seen = new Set(mentions.map((m) => m.company));
    return allCompanies.filter((c) => seen.has(c));
  }, [mentions, allCompanies]);

  if (data.length === 0 || activeCompanies.length === 0) {
    return (
      <DashboardCard>
        <ZoneEmpty message="No mentions in the selected period." />
      </DashboardCard>
    );
  }

  return (
    <DashboardCard>
      <div style={CHART_FONT}>
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={data} margin={{ top: 8, right: 24, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={GRID_COLOR} strokeDasharray="4 4" vertical={false} />
            <XAxis
              dataKey="month"
              tick={AXIS_CAT}
              axisLine={false}
              tickLine={false}
              tickFormatter={formatMonth}
            />
            <YAxis tick={AXIS_NUM} axisLine={false} tickLine={false} allowDecimals={false} />
            <Tooltip content={<DarkTooltip />} cursor={{ stroke: "rgba(255,255,255,0.12)" }} />
            <Legend
              wrapperStyle={{ ...CHART_FONT, fontSize: 11, color: "#767676", paddingTop: 12 }}
              iconType="circle"
              iconSize={8}
            />
            {activeCompanies.map((company) => (
              <Line
                key={company}
                type="monotone"
                dataKey={company}
                name={company}
                stroke={getCompetitorColor(company, allCompanies, brandColors)}
                strokeWidth={2}
                dot={{ r: 2 }}
                activeDot={{ r: 4 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </DashboardCard>
  );
}
