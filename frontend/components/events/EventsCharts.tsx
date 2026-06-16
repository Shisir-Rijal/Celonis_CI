"use client";

import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, Legend,
} from "recharts";

import { useEvents } from "@/lib/events/hooks";
import { computeAnalysis } from "@/lib/events/analysis";
import DashboardCard from "@components/brand/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/brand/ZoneState";

// ---------------------------------------------------------------------------
// Colours
// ---------------------------------------------------------------------------

const CELONIS_GREEN = "#5CFE50";
const BAR_OTHER    = "rgba(255,255,255,0.14)";
const ONLINE_COLOR = "#3233F5";
const INPERSON_COLOR = "#f59e0b";
const GRID_COLOR   = "rgba(255,255,255,0.08)";

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};
const AXIS_NUM  = { fill: "#767676", fontSize: 11 };
const AXIS_CAT  = { fill: "#CBCBCB", fontSize: 11 };

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-lg border border-white/10 bg-neutral-grey-30 px-3 py-2.5 shadow-lg text-xs"
      style={CHART_FONT}
    >
      <div className="font-medium text-primary-white mb-1.5 truncate max-w-[160px]">{label}</div>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {payload.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2 mt-1">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: entry.fill ?? entry.color }} />
          <span className="text-neutral-grey-20">{entry.name}</span>
          <span className="ml-auto font-medium text-primary-white pl-4 tabular-nums">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EventsCharts() {
  const { data, isLoading, isError } = useEvents();

  const allCompanies = useMemo(
    () => [...new Set((data?.events ?? []).map((e) => e.company))].sort(),
    [data]
  );

  const analysis = useMemo(
    () => (data?.events.length ? computeAnalysis(data.events, allCompanies) : null),
    [data, allCompanies]
  );

  const barHeight = Math.max(240, (analysis?.perCompany.length ?? 6) * 38);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ZoneSkeleton height={320} />
        <ZoneSkeleton height={320} />
      </div>
    );
  }

  if (isError) return <ZoneError />;
  if (!analysis) return <ZoneEmpty message="No event data available." />;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Events per Competitor */}
      <DashboardCard
        label="Events per competitor"
        sublabel="Total scraped events · Celonis highlighted in green"
      >
        <div style={CHART_FONT}>
          <ResponsiveContainer width="100%" height={barHeight}>
            <BarChart
              layout="vertical"
              data={analysis.perCompany}
              margin={{ top: 4, right: 36, bottom: 0, left: 0 }}
              barCategoryGap="32%"
            >
              <CartesianGrid horizontal={false} stroke={GRID_COLOR} strokeDasharray="4 4" />
              <XAxis type="number" tick={AXIS_NUM} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="company" tick={AXIS_CAT} axisLine={false} tickLine={false} width={96} />
              <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="count" name="Events" radius={[0, 4, 4, 0]}>
                {analysis.perCompany.map((entry, i) => (
                  <Cell key={i} fill={entry.isCelonis ? CELONIS_GREEN : BAR_OTHER} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </DashboardCard>

      {/* Format Mix */}
      <DashboardCard
        label="Format mix"
        sublabel="In-person vs. online events per competitor"
      >
        <div style={CHART_FONT}>
          <ResponsiveContainer width="100%" height={barHeight}>
            <BarChart
              layout="vertical"
              data={analysis.formatMix}
              margin={{ top: 4, right: 36, bottom: 0, left: 0 }}
              barCategoryGap="32%"
            >
              <CartesianGrid horizontal={false} stroke={GRID_COLOR} strokeDasharray="4 4" />
              <XAxis type="number" tick={AXIS_NUM} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="company" tick={AXIS_CAT} axisLine={false} tickLine={false} width={96} />
              <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Legend
                wrapperStyle={{ ...CHART_FONT, fontSize: 11, color: "#767676", paddingTop: 12 }}
                iconType="circle"
                iconSize={8}
              />
              <Bar dataKey="inPerson" name="In-Person" stackId="fmt" fill={INPERSON_COLOR} radius={[0, 0, 0, 0]} />
              <Bar dataKey="online"   name="Online"    stackId="fmt" fill={ONLINE_COLOR}   radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </DashboardCard>
    </div>
  );
}