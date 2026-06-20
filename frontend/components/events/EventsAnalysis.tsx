"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from "recharts";

import { useEvents } from "@/lib/events/hooks";
import type { EventItem } from "@/lib/events/types";
import DashboardCard from "@components/geo/DashboardCard";
import AlertCard from "@components/geo/AlertCard";
import SectionHeader from "@components/geo/SectionHeader";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";

// ---------------------------------------------------------------------------
// Colours
// ---------------------------------------------------------------------------

const CELONIS_GREEN = "#5CFE50";
const BAR_OTHER = "rgba(255,255,255,0.14)";
const ONLINE_COLOR = "#3233F5";
const INPERSON_COLOR = "#f59e0b";
const GRID_COLOR = "rgba(255,255,255,0.08)";

// ---------------------------------------------------------------------------
// Region helper (minimal version — only needs the "Online / Virtual" bucket)
// ---------------------------------------------------------------------------

const ONLINE_KEYWORDS = [
  "online", "virtual", "remote", "webinar", "digital", "zoom", "livestream", "hybrid",
];

function isOnlineEvent(location: string | null): boolean {
  if (!location) return false;
  const lower = location.toLowerCase();
  return ONLINE_KEYWORDS.some((kw) => lower.includes(kw));
}

// ---------------------------------------------------------------------------
// Dark tooltip — reused across both charts
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-lg border border-white/10 bg-neutral-grey-30 px-3 py-2.5 shadow-lg text-xs"
      style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif" }}
    >
      <div className="font-medium text-primary-white mb-1.5 truncate max-w-[160px]">
        {label}
      </div>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {payload.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2 mt-1">
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: entry.fill ?? entry.color }}
          />
          <span className="text-neutral-grey-20">{entry.name}</span>
          <span className="ml-auto font-medium text-primary-white pl-4 tabular-nums">
            {entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Analytics computation
// ---------------------------------------------------------------------------

type PerCompany = { company: string; count: number; isCelonis: boolean };
type FormatRow  = { company: string; inPerson: number; online: number; isCelonis: boolean };

type Analysis = {
  total: number;
  celonisCount: number;
  celonisShare: number;
  mostActiveCompetitor: { name: string; count: number } | null;
  perCompany: PerCompany[];
  formatMix: FormatRow[];
  coverageGap: { region: string; competitorEvents: number } | null;
  topicGap: { topic: string; celonisCount: number; otherCount: number } | null;
  momentum: {
    thisYear: number;
    lastYear: number;
    direction: "up" | "down" | "flat";
    pctChange: number;
  } | null;
};

const REGION_KEYWORDS: Array<{ region: string; keywords: string[] }> = [
  { region: "Europe",       keywords: ["germany","uk","united kingdom","france","spain","italy","netherlands","sweden","norway","denmark","finland","belgium","austria","switzerland","poland","portugal","ireland","europe","london","berlin","paris","amsterdam","munich","münchen","frankfurt","vienna","wien","zurich","stockholm","copenhagen","oslo","helsinki","brussels","dublin","madrid","barcelona","rome","milan","warsaw","prague","budapest","lisbon","edinburgh"] },
  { region: "North America",keywords: ["usa","united states","canada","mexico","california","new york","texas","florida","san francisco","los angeles","chicago","boston","seattle","austin","houston","dallas","miami","atlanta","las vegas","denver","toronto","vancouver","montreal","mexico city"] },
  { region: "South America",keywords: ["brazil","argentina","chile","colombia","peru","são paulo","sao paulo","buenos aires","santiago","bogotá","bogota","lima","rio de janeiro"] },
  { region: "Asia Pacific", keywords: ["china","japan","india","australia","singapore","korea","indonesia","malaysia","thailand","vietnam","new zealand","hong kong","taiwan","tokyo","shanghai","beijing","sydney","seoul","mumbai","bangalore","bengaluru","jakarta","bangkok","kuala lumpur","taipei","auckland","delhi"] },
  { region: "Middle East & Africa", keywords: ["uae","saudi arabia","israel","turkey","egypt","south africa","nigeria","kenya","morocco","qatar","dubai","abu dhabi","tel aviv","riyadh","istanbul","cairo","johannesburg","lagos","nairobi","cape town"] },
];

function locationToRegionForGap(location: string | null): string {
  if (!location) return "Other";
  const lower = location.toLowerCase();
  for (const { region, keywords } of REGION_KEYWORDS) {
    if (keywords.some((kw) => lower.includes(kw))) return region;
  }
  return "Other";
}

function computeAnalysis(events: EventItem[], allCompanies: string[]): Analysis {
  const celonisName = allCompanies.find((c) => c.toLowerCase().includes("celonis")) ?? "";
  const isCelonis = (c: string) => c === celonisName;

  const total = events.length;
  const celonisEvents = events.filter((e) => isCelonis(e.company));
  const celonisCount = celonisEvents.length;
  const celonisShare = total > 0 ? (celonisCount / total) * 100 : 0;

  // Per-company counts (sorted by count desc)
  const countMap: Record<string, number> = {};
  for (const e of events) countMap[e.company] = (countMap[e.company] ?? 0) + 1;
  const perCompany: PerCompany[] = Object.entries(countMap)
    .map(([company, count]) => ({ company, count, isCelonis: isCelonis(company) }))
    .sort((a, b) => b.count - a.count);

  const mostActiveCompetitor = perCompany.find((c) => !c.isCelonis) ?? null;

  // Format mix (same order as perCompany)
  const fmtMap: Record<string, { online: number; inPerson: number }> = {};
  for (const e of events) {
    if (!fmtMap[e.company]) fmtMap[e.company] = { online: 0, inPerson: 0 };
    if (isOnlineEvent(e.location)) fmtMap[e.company].online++;
    else fmtMap[e.company].inPerson++;
  }
  const formatMix: FormatRow[] = perCompany.map((c) => ({
    company: c.company,
    inPerson: fmtMap[c.company]?.inPerson ?? 0,
    online: fmtMap[c.company]?.online ?? 0,
    isCelonis: c.isCelonis,
  }));

  // Coverage gap — in-person regions where Celonis has 0 events
  const celonisRegions = new Set(
    celonisEvents
      .filter((e) => !isOnlineEvent(e.location))
      .map((e) => locationToRegionForGap(e.location))
  );
  const gapMap: Record<string, number> = {};
  for (const e of events) {
    if (isCelonis(e.company) || isOnlineEvent(e.location)) continue;
    const r = locationToRegionForGap(e.location);
    if (r !== "Other" && !celonisRegions.has(r)) {
      gapMap[r] = (gapMap[r] ?? 0) + 1;
    }
  }
  const topGap = Object.entries(gapMap).sort(([, a], [, b]) => b - a)[0];
  const coverageGap = topGap ? { region: topGap[0], competitorEvents: topGap[1] } : null;

  // Topic gap — topic with largest (other - celonis) delta
  const topicCelonis: Record<string, number> = {};
  const topicOther: Record<string, number> = {};
  for (const e of events) {
    if (!e.event_topic) continue;
    if (isCelonis(e.company)) topicCelonis[e.event_topic] = (topicCelonis[e.event_topic] ?? 0) + 1;
    else topicOther[e.event_topic] = (topicOther[e.event_topic] ?? 0) + 1;
  }
  let topicGap: Analysis["topicGap"] = null;
  let maxDelta = 0;
  for (const [topic, otherCount] of Object.entries(topicOther)) {
    const cel = topicCelonis[topic] ?? 0;
    if (otherCount - cel > maxDelta) {
      maxDelta = otherCount - cel;
      topicGap = { topic, celonisCount: cel, otherCount };
    }
  }

  // Momentum — Celonis YoY
  const now = new Date();
  const thisYr = now.getFullYear();
  let thisYear = 0;
  let lastYear = 0;
  for (const e of celonisEvents) {
    if (!e.event_date) continue;
    const d = new Date(e.event_date);
    if (isNaN(d.getTime())) continue;
    if (d.getFullYear() === thisYr) thisYear++;
    if (d.getFullYear() === thisYr - 1) lastYear++;
  }
  const pctChange =
    lastYear > 0 ? Math.round(((thisYear - lastYear) / lastYear) * 100) : 0;
  const momentum: Analysis["momentum"] =
    celonisCount > 0
      ? {
          thisYear,
          lastYear,
          direction: pctChange > 0 ? "up" : pctChange < 0 ? "down" : "flat",
          pctChange,
        }
      : null;

  return {
    total,
    celonisCount,
    celonisShare,
    mostActiveCompetitor,
    perCompany,
    formatMix,
    coverageGap,
    topicGap,
    momentum,
  };
}

// ---------------------------------------------------------------------------
// Shared axis / chart styles
// ---------------------------------------------------------------------------

const AXIS_TICK_DARK = { fill: "#767676", fontSize: 11 };
const Y_AXIS_TICK   = { fill: "#CBCBCB", fontSize: 11 };
const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EventsAnalysis() {
  const { data, isLoading, isError, error } = useEvents();

  const allCompanies = useMemo(
    () => [...new Set((data?.events ?? []).map((e) => e.company))].sort(),
    [data]
  );

  const analysis = useMemo(
    () =>
      data?.events.length ? computeAnalysis(data.events, allCompanies) : null,
    [data, allCompanies]
  );

  const barHeight = Math.max(240, (analysis?.perCompany.length ?? 6) * 38);

  return (
    <div className="flex flex-col gap-14">
      {/* ================================================================== */}
      {/* Zone 1 — KPI Tiles                                                 */}
      {/* ================================================================== */}
      <section>
        <SectionHeader
          label="Events at a glance"
          description="High-level event presence across all tracked competitors."
        />

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <ZoneSkeleton key={i} height={150} />
            ))}
          </div>
        ) : isError ? (
          <ZoneError message={(error as Error)?.message} />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Total Events */}
            <DashboardCard className="flex flex-col gap-2">
              <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
                Total events tracked
              </span>
              <span className="text-[44px] leading-none font-medium tracking-tight text-primary-white">
                {analysis?.total ?? "—"}
              </span>
              <span className="text-xs text-neutral-grey-20">
                Across all competitors
              </span>
            </DashboardCard>

            {/* Celonis Event Share — hero tile */}
            <DashboardCard className="relative overflow-hidden flex flex-col gap-2">
              <div className="absolute top-0 left-0 right-0 h-[3px] bg-secondary-green" />
              <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
                Celonis event share
              </span>
              <div className="flex items-baseline gap-1">
                <span className="text-[44px] leading-none font-medium tracking-tight text-primary-white">
                  {analysis ? analysis.celonisShare.toFixed(1) : "—"}
                </span>
                {analysis && (
                  <span className="text-lg text-neutral-grey-20 font-normal">%</span>
                )}
              </div>
              <span className="text-xs text-neutral-grey-20">
                {analysis?.celonisCount ?? 0} of {analysis?.total ?? 0} events
              </span>
            </DashboardCard>

            {/* Most Active Competitor */}
            <DashboardCard className="flex flex-col gap-2">
              <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
                Most active competitor
              </span>
              {analysis?.mostActiveCompetitor ? (
                <>
                  <span className="text-[32px] leading-tight font-medium tracking-tight text-primary-white truncate">
                    {analysis.mostActiveCompetitor.name}
                  </span>
                  <span className="text-xs text-neutral-grey-20">
                    {analysis.mostActiveCompetitor.count} events tracked
                  </span>
                </>
              ) : (
                <span className="text-[44px] leading-none font-medium text-primary-white">
                  —
                </span>
              )}
            </DashboardCard>
          </div>
        )}
      </section>

      {/* ================================================================== */}
      {/* Zone 2 — Competitive Charts                                         */}
      {/* ================================================================== */}
      <section>
        <SectionHeader
          label="Competitive landscape"
          description="Event volume and format split across all tracked competitors."
        />

        {isLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ZoneSkeleton height={320} />
            <ZoneSkeleton height={320} />
          </div>
        ) : isError ? (
          <ZoneError />
        ) : !analysis ? (
          <ZoneEmpty message="No event data available." />
        ) : (
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
                    <CartesianGrid
                      horizontal={false}
                      stroke={GRID_COLOR}
                      strokeDasharray="4 4"
                    />
                    <XAxis
                      type="number"
                      tick={AXIS_TICK_DARK}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="company"
                      tick={Y_AXIS_TICK}
                      axisLine={false}
                      tickLine={false}
                      width={96}
                    />
                    <Tooltip
                      content={<DarkTooltip />}
                      cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    />
                    <Bar dataKey="count" name="Events" radius={[0, 4, 4, 0]}>
                      {analysis.perCompany.map((entry, i) => (
                        <Cell
                          key={i}
                          fill={entry.isCelonis ? CELONIS_GREEN : BAR_OTHER}
                        />
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
                    <CartesianGrid
                      horizontal={false}
                      stroke={GRID_COLOR}
                      strokeDasharray="4 4"
                    />
                    <XAxis
                      type="number"
                      tick={AXIS_TICK_DARK}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="company"
                      tick={Y_AXIS_TICK}
                      axisLine={false}
                      tickLine={false}
                      width={96}
                    />
                    <Tooltip
                      content={<DarkTooltip />}
                      cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    />
                    <Legend
                      wrapperStyle={{
                        ...CHART_FONT,
                        fontSize: 11,
                        color: "#767676",
                        paddingTop: 12,
                      }}
                      iconType="circle"
                      iconSize={8}
                    />
                    <Bar
                      dataKey="inPerson"
                      name="In-Person"
                      stackId="fmt"
                      fill={INPERSON_COLOR}
                      radius={[0, 0, 0, 0]}
                    />
                    <Bar
                      dataKey="online"
                      name="Online"
                      stackId="fmt"
                      fill={ONLINE_COLOR}
                      radius={[0, 4, 4, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </DashboardCard>
          </div>
        )}
      </section>

      {/* ================================================================== */}
      {/* Zone 3 — Strategic Alerts                                           */}
      {/* ================================================================== */}
      <section>
        <SectionHeader
          label="Celonis positioning"
          description="Automated strategic signals derived from scraped event data."
        />

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <ZoneSkeleton key={i} height={180} />
            ))}
          </div>
        ) : isError ? (
          <ZoneError />
        ) : !analysis ? (
          <ZoneEmpty message="No analysis available yet." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Coverage Gap */}
            {analysis.coverageGap ? (
              <AlertCard
                category="Coverage Gap"
                text={`Celonis has no in-person events in ${analysis.coverageGap.region}, where ${analysis.coverageGap.competitorEvents} competitor event${analysis.coverageGap.competitorEvents !== 1 ? "s" : ""} are active.`}
                priority={analysis.coverageGap.competitorEvents >= 5 ? "high" : "medium"}
                recommendation="Consider attending or sponsoring events in this region."
              />
            ) : (
              <DashboardCard label="Coverage Gap">
                <p className="text-sm text-neutral-grey-20">
                  No regional gaps detected — Celonis is present in all active
                  in-person regions.
                </p>
              </DashboardCard>
            )}

            {/* Topic Gap */}
            {analysis.topicGap ? (
              <AlertCard
                category="Topic Gap"
                text={`Competitors have ${analysis.topicGap.otherCount} events on "${analysis.topicGap.topic}" while Celonis has ${analysis.topicGap.celonisCount === 0 ? "none" : analysis.topicGap.celonisCount}.`}
                priority={analysis.topicGap.celonisCount === 0 ? "high" : "medium"}
                recommendation="Evaluate whether this topic aligns with Celonis messaging."
              />
            ) : (
              <DashboardCard label="Topic Gap">
                <p className="text-sm text-neutral-grey-20">
                  No topic gaps detected.
                </p>
              </DashboardCard>
            )}

            {/* Momentum */}
            {analysis.momentum ? (
              <AlertCard
                category="Momentum"
                text={
                  analysis.momentum.lastYear === 0
                    ? `Celonis has ${analysis.momentum.thisYear} event${analysis.momentum.thisYear !== 1 ? "s" : ""} tracked in ${new Date().getFullYear()}. No prior-year data to compare against.`
                    : `Celonis event volume is ${
                        analysis.momentum.direction === "up"
                          ? `up ${analysis.momentum.pctChange}%`
                          : analysis.momentum.direction === "down"
                          ? `down ${Math.abs(analysis.momentum.pctChange)}%`
                          : "flat"
                      } year-over-year (${analysis.momentum.lastYear} → ${analysis.momentum.thisYear} events).`
                }
                priority={
                  analysis.momentum.direction === "down" &&
                  Math.abs(analysis.momentum.pctChange) >= 30
                    ? "high"
                    : analysis.momentum.direction === "up"
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
        )}
      </section>
    </div>
  );
}

export default EventsAnalysis;
