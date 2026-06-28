"use client";

import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, LabelList,
} from "recharts";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneEmpty } from "@components/geo/ZoneState";
import { aggregateByRegion } from "@/lib/sov/analysis";
import type { SovMention } from "@/lib/sov/types";

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};
const GRID_COLOR = "rgba(255,255,255,0.08)";
const LABEL_COLOR = "#CBCBCB";
const AXIS_NUM = { fill: "#767676", fontSize: 11 };
const AXIS_CAT = { fill: "#CBCBCB", fontSize: 11 };
const CELONIS_GREEN = "#5CFE50";

// Tints from secondary-green for visual ranking
const TINTS = [
  "rgba(92,254,80,0.95)",
  "rgba(92,254,80,0.80)",
  "rgba(92,254,80,0.65)",
  "rgba(92,254,80,0.50)",
  "rgba(92,254,80,0.35)",
  "rgba(92,254,80,0.25)",
];

type Props = {
  mentions: SovMention[];
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const entry = payload[0];
  return (
    <div
      className="rounded-lg border border-white/10 bg-neutral-grey-30 px-3 py-2.5 shadow-lg text-xs"
      style={CHART_FONT}
    >
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: CELONIS_GREEN }} />
        <span className="font-medium text-primary-white">{label}</span>
      </div>
      <div className="mt-1 text-neutral-grey-20 tabular-nums">
        {entry.value} mentions
      </div>
    </div>
  );
}

export default function SovRegionChart({ mentions }: Props) {
  const data = useMemo(() => aggregateByRegion(mentions), [mentions]);

  if (data.length === 0) {
    return (
      <DashboardCard>
        <ZoneEmpty message="No regions in the selected period." />
      </DashboardCard>
    );
  }

  const chartHeight = Math.max(220, data.length * 44);

  return (
    <DashboardCard>
      <div style={CHART_FONT}>
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            layout="vertical"
            data={data}
            margin={{ top: 4, right: 48, bottom: 0, left: 0 }}
            barCategoryGap="30%"
          >
            <CartesianGrid horizontal={false} stroke={GRID_COLOR} strokeDasharray="4 4" />
            <XAxis type="number" tick={AXIS_NUM} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis type="category" dataKey="region" tick={AXIS_CAT} axisLine={false} tickLine={false} width={96} />
            <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
            <Bar dataKey="count" name="Mentions" radius={[0, 4, 4, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={TINTS[i % TINTS.length]} />
              ))}
              <LabelList
                dataKey="count"
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
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </DashboardCard>
  );
}
