"use client";

import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, LabelList,
} from "recharts";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneEmpty } from "@components/geo/ZoneState";
import { aggregateThemeByCompany } from "@/lib/sov/analysis";
import { getCompetitorColor } from "@/lib/competitors/colors";
import type { SovMention } from "@/lib/sov/types";

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};
const GRID_COLOR = "rgba(255,255,255,0.08)";
const LABEL_COLOR = "#CBCBCB";
const AXIS_NUM = { fill: "#767676", fontSize: 11 };
const AXIS_CAT = { fill: "#CBCBCB", fontSize: 11 };

type Props = {
  mentions: SovMention[];
  allCompanies: string[];
  brandColors: Record<string, string>;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rows = payload
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((e: any) => (e.value ?? 0) > 0)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .sort((a: any, b: any) => (b.value ?? 0) - (a.value ?? 0));
  if (rows.length === 0) return null;
  return (
    <div
      className="rounded-lg border border-white/10 bg-neutral-grey-30 px-3 py-2.5 shadow-lg text-xs"
      style={CHART_FONT}
    >
      <div className="font-medium text-primary-white mb-1.5">{label}</div>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {rows.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2 mt-1">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: entry.color ?? entry.fill }} />
          <span className="text-neutral-grey-20 truncate max-w-[160px]">{entry.name}</span>
          <span className="ml-auto font-medium text-primary-white pl-4 tabular-nums">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function SovThemeBreakdown({ mentions, allCompanies, brandColors }: Props) {
  const data = useMemo(
    () => aggregateThemeByCompany(mentions, allCompanies),
    [mentions, allCompanies],
  );

  const activeCompanies = useMemo(() => {
    const seen = new Set(mentions.map((m) => m.company));
    return allCompanies.filter((c) => seen.has(c));
  }, [mentions, allCompanies]);

  if (data.length === 0) {
    return (
      <DashboardCard>
        <ZoneEmpty message="No themes in the selected period." />
      </DashboardCard>
    );
  }

  const chartHeight = Math.max(240, data.length * 40);

  return (
    <DashboardCard>
      <div style={CHART_FONT}>
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            layout="vertical"
            data={data}
            margin={{ top: 4, right: 56, bottom: 0, left: 0 }}
            barCategoryGap="28%"
          >
            <CartesianGrid horizontal={false} stroke={GRID_COLOR} strokeDasharray="4 4" />
            <XAxis type="number" tick={AXIS_NUM} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis type="category" dataKey="theme" tick={AXIS_CAT} axisLine={false} tickLine={false} width={150} />
            <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
            <Legend
              wrapperStyle={{ ...CHART_FONT, fontSize: 11, color: "#767676", paddingTop: 12 }}
              iconType="circle"
              iconSize={8}
            />
            {activeCompanies.map((company, i) => (
              <Bar
                key={company}
                dataKey={company}
                name={company}
                stackId="theme"
                fill={getCompetitorColor(company, allCompanies, brandColors)}
                radius={i === activeCompanies.length - 1 ? [0, 4, 4, 0] : [0, 0, 0, 0]}
              >
                {i === activeCompanies.length - 1 && (
                  <LabelList
                    dataKey="total"
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    content={(props: any) => {
                      const { x, y, width, height, value } = props;
                      if (!value) return null;
                      return (
                        <text
                          x={x + width + 8}
                          y={y + height / 2}
                          fill={LABEL_COLOR}
                          fontSize={11}
                          textAnchor="start"
                          dominantBaseline="middle"
                        >
                          {value}
                        </text>
                      );
                    }}
                  />
                )}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </DashboardCard>
  );
}
