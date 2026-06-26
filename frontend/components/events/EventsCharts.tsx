"use client";

import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, Legend, LabelList,
} from "recharts";

import { useEvents } from "@/lib/events/hooks";
import { computeAnalysis } from "@/lib/events/analysis";
import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useCompetitorColors } from "@/lib/competitors/hooks";
import { getCompetitorColor } from "@/lib/competitors/colors";

// ---------------------------------------------------------------------------
// Colours
// ---------------------------------------------------------------------------

const CELONIS_GREEN = "#5CFE50";
const BAR_OTHER    = "rgba(255,255,255,0.14)";
const ONLINE_COLOR = "#3233F5";
const INPERSON_COLOR = "#f59e0b";
const GRID_COLOR   = "rgba(255,255,255,0.08)";
const LABEL_COLOR  = "#CBCBCB";

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

  const { data: brandColors = {} } = useCompetitorColors();

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
    <div className="flex flex-col gap-4">
      {/* Row 1: Format Mix + Region Mix */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
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
                margin={{ top: 4, right: 48, bottom: 0, left: 0 }}
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
                <Bar dataKey="online" name="Online" stackId="fmt" fill={ONLINE_COLOR} radius={[0, 4, 4, 0]}>
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  <LabelList dataKey="total" content={(props: any) => {
                    const { x, y, width, height, value } = props;
                    if (!value) return null;
                    return <text x={x + width + 8} y={y + height / 2} fill={LABEL_COLOR} fontSize={11} textAnchor="start" dominantBaseline="middle">{value}</text>;
                  }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </DashboardCard>

        {/* Region Mix */}
        <DashboardCard
          label="Region mix"
          sublabel="In-person vs. online events per region"
        >
          <div style={CHART_FONT}>
            <ResponsiveContainer width="100%" height={Math.max(200, analysis.regionMix.length * 40)}>
              <BarChart
                layout="vertical"
                data={analysis.regionMix}
                margin={{ top: 4, right: 48, bottom: 0, left: 0 }}
                barCategoryGap="32%"
              >
                <CartesianGrid horizontal={false} stroke={GRID_COLOR} strokeDasharray="4 4" />
                <XAxis type="number" tick={AXIS_NUM} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="region" tick={AXIS_CAT} axisLine={false} tickLine={false} width={130} />
                <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                <Legend
                  wrapperStyle={{ ...CHART_FONT, fontSize: 11, color: "#767676", paddingTop: 12 }}
                  iconType="circle"
                  iconSize={8}
                />
                <Bar dataKey="inPerson" name="In-Person" stackId="rgn" fill={INPERSON_COLOR} radius={[0, 0, 0, 0]} />
                <Bar dataKey="online" name="Online" stackId="rgn" fill={ONLINE_COLOR} radius={[0, 4, 4, 0]}>
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  <LabelList dataKey="total" content={(props: any) => {
                    const { x, y, width, height, value } = props;
                    if (!value) return null;
                    return <text x={x + width + 8} y={y + height / 2} fill={LABEL_COLOR} fontSize={11} textAnchor="start" dominantBaseline="middle">{value}</text>;
                  }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </DashboardCard>
      </div>

      {/* Row 2: Trending Topics + Topics by Competitor */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Trending Topics */}
        <DashboardCard label="Trending topics" sublabel="Most frequent event topics across all competitors">
          <div style={CHART_FONT}>
            <ResponsiveContainer width="100%" height={Math.max(200, analysis.trendingTopics.length * 36)}>
              <BarChart
                layout="vertical"
                data={analysis.trendingTopics}
                margin={{ top: 4, right: 48, bottom: 0, left: 0 }}
                barCategoryGap="32%"
              >
                <CartesianGrid horizontal={false} stroke={GRID_COLOR} strokeDasharray="4 4" />
                <XAxis type="number" tick={AXIS_NUM} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="topic" tick={AXIS_CAT} axisLine={false} tickLine={false} width={150} />
                <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                <Bar dataKey="total" name="Events" radius={[0, 4, 4, 0]}>
                  {analysis.trendingTopics.map((_, i) => (
                    <Cell key={i} fill={`rgba(92,254,80,${Math.max(0.25, 0.9 - i * 0.07)})`} />
                  ))}
                  <LabelList
                    dataKey="total"
                    content={(props: any) => {
                      const { x, y, width, height, value } = props;
                      if (!value) return null;
                      return (
                        <text x={x + width + 8} y={y + height / 2} fill={LABEL_COLOR} fontSize={11} textAnchor="start" dominantBaseline="middle">{value}</text>
                      );
                    }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </DashboardCard>

        {/* Topics by Competitor */}
        <DashboardCard label="Topic breakdown" sublabel="Which competitor focuses on which topic">
          <div style={CHART_FONT}>
            <ResponsiveContainer width="100%" height={Math.max(200, analysis.topicByCompany.length * 36)}>
              <BarChart
                layout="vertical"
                data={analysis.topicByCompany}
                margin={{ top: 4, right: 48, bottom: 0, left: 0 }}
                barCategoryGap="32%"
              >
                <CartesianGrid horizontal={false} stroke={GRID_COLOR} strokeDasharray="4 4" />
                <XAxis type="number" tick={AXIS_NUM} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="topic" tick={AXIS_CAT} axisLine={false} tickLine={false} width={150} />
                <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                <Legend wrapperStyle={{ ...CHART_FONT, fontSize: 11, color: "#767676", paddingTop: 12 }} iconType="circle" iconSize={8} />
                {allCompanies.map((company, i) => (
                  <Bar
                    key={company}
                    dataKey={company}
                    name={company}
                    stackId="tc"
                    fill={getCompetitorColor(company, allCompanies, brandColors)}
                    radius={i === allCompanies.length - 1 ? [0, 4, 4, 0] : [0, 0, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </DashboardCard>

      </div>
    </div>
  );
}