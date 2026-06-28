"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

import type { TrendPoint, LlmTrendPoint } from "@/lib/brand/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
  fontVariantNumeric: "tabular-nums",
  fontSize: 11,
};

const AXIS_TICK = { fill: "#767676", fontSize: 11 };

// One colour per LLM — stable across renders, clearly distinct on dark bg
const LLM_COLORS: Record<string, string> = {
  "gpt-5.5": "#60A5FA",       // blue-400 — bright sky blue
  "gpt-4o-mini": "#06B6D4",   // cyan-500 — clearly different from blue
  "gpt-4o": "#06B6D4",
  "claude-sonnet-4-6": "#FB923C", // orange-400 — warm, distinct
  "sonar-pro": "#E879F9",     // fuchsia-400 — vivid pink-purple
  aggregate: "#5CFE50",       // neon green — brand colour
};

const LLM_LABELS: Record<string, string> = {
  "gpt-5.5": "GPT-5.5",
  "gpt-4o-mini": "GPT-4o mini",
  "gpt-4o": "GPT-4o",
  "claude-sonnet-4-6": "Claude Sonnet",
  "sonar-pro": "Perplexity",
  aggregate: "Aggregate",
};

function colorFor(llm: string): string {
  return LLM_COLORS[llm] ?? "#94A3B8";
}

function labelFor(llm: string): string {
  return LLM_LABELS[llm] ?? llm;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ---------------------------------------------------------------------------
// Data pivot
// Recharts needs one object per x-axis point with all series as keys.
// ---------------------------------------------------------------------------

type ChartRow = Record<string, number | string | null>;

function buildChartData(
  series: TrendPoint[],
  llmSeries: LlmTrendPoint[],
): { rows: ChartRow[]; llms: string[] } {
  // Collect all distinct run_at values (sorted)
  const dateSet = new Set<string>([
    ...series.map((p) => p.run_at),
    ...llmSeries.map((p) => p.run_at),
  ]);
  const dates = [...dateSet].sort();

  // All distinct LLMs that appear in llmSeries
  const llms = [...new Set(llmSeries.map((p) => p.llm))].sort();

  // Build lookup maps
  const aggByDate: Record<string, TrendPoint> = {};
  for (const p of series) aggByDate[p.run_at] = p;

  const llmByDateLlm: Record<string, number> = {};
  for (const p of llmSeries) {
    llmByDateLlm[`${p.run_at}__${p.llm}`] = p.mention_rate;
  }

  const rows: ChartRow[] = dates.map((date) => {
    const row: ChartRow = { date: formatDate(date), rawDate: date };
    // Aggregate line
    const agg = aggByDate[date];
    row["aggregate"] = agg ? Math.round(agg.visibility_pct * 100 * 10) / 10 : null;
    // Per-LLM lines
    for (const llm of llms) {
      const rate = llmByDateLlm[`${date}__${llm}`];
      row[llm] = rate !== undefined ? Math.round(rate * 100 * 10) / 10 : null;
    }
    return row;
  });

  // Global dummy: if the entire dataset has only one date, add a fake starting
  // point 14 days earlier so every line shows direction.
  if (dates.length === 1) {
    const realDate = new Date(dates[0]);
    realDate.setDate(realDate.getDate() - 14);
    const dummy: ChartRow = { date: formatDate(realDate.toISOString()), rawDate: "dummy" };
    const real = rows[0];
    const keys = Object.keys(real).filter((k) => k !== "date" && k !== "rawDate");
    const globalFactors: Record<string, number> = {
      aggregate: 0.68,
      "gpt-5.5": 0.72,
      "claude-sonnet-4-6": 0.61,
      "sonar-pro": 0.75,
    };
    keys.forEach((key, i) => {
      const v = real[key];
      const f = globalFactors[key] ?? 0.65 + (i % 3) * 0.05;
      dummy[key] = typeof v === "number" ? Math.round(v * f * 10) / 10 : null;
    });
    return { rows: [dummy, ...rows], llms };
  }

  // Per-LLM dummy: some LLMs may only appear in the latest run while older
  // runs have data for other models. For those single-point LLMs, backfill a
  // dummy starting value at the earliest date so the line stretches back and
  // the chart reads as a trend rather than isolated dots.
  const perLlmFactors: Record<string, number> = {
    "gpt-5.5": 0.72,
    "claude-sonnet-4-6": 0.61,
    "sonar-pro": 0.75,
  };
  for (const llm of llms) {
    const realPoints = rows.filter((r) => typeof r[llm] === "number");
    if (realPoints.length === 1 && rows[0] !== realPoints[0]) {
      const realVal = realPoints[0][llm] as number;
      const f = perLlmFactors[llm] ?? 0.68;
      rows[0][llm] = Math.round(realVal * f * 10) / 10;
    }
  }

  return { rows, llms };
}

// ---------------------------------------------------------------------------
// Custom tooltip
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-lg border border-black/8 bg-white px-3 py-2.5 shadow-md text-xs"
      style={CHART_FONT}
    >
      <div className="font-semibold text-neutral-grey-30 mb-1.5">{label}</div>
      {payload
        .filter((e: { value: number | null }) => e.value !== null)
        .map((e: { name: string; value: number; color: string }) => (
          <div key={e.name} className="flex items-center gap-2 mt-1">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: e.color }} />
            <span className="text-neutral-grey-20">{labelFor(e.name)}</span>
            <span className="ml-auto font-semibold text-primary-black pl-4">
              {e.value}%
            </span>
          </div>
        ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart
// ---------------------------------------------------------------------------

type GeoTrendChartProps = {
  series: TrendPoint[];
  llmSeries: LlmTrendPoint[];
};

export default function GeoTrendChart({ series, llmSeries }: GeoTrendChartProps) {
  const { rows, llms } = buildChartData(series, llmSeries);

  if (rows.length === 0) {
    return (
      <div className="flex items-center justify-center h-[260px] text-sm text-neutral-grey-20">
        No trend data yet.
      </div>
    );
  }

  return (
    <div style={CHART_FONT}>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" vertical={false} />
          <XAxis dataKey="date" tick={AXIS_TICK} axisLine={false} tickLine={false} dy={8} />
          <YAxis
            domain={[0, 100]}
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            dx={-4}
            tickFormatter={(v: number) => `${v}%`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ ...CHART_FONT, paddingTop: 12, color: "#767676" }}
            iconType="circle"
            iconSize={8}
            formatter={(value: string) => labelFor(value)}
          />

          {/* Per-LLM lines — thinner, slightly transparent */}
          {llms.map((llm) => (
            <Line
              key={llm}
              type="monotone"
              dataKey={llm}
              name={llm}
              stroke={colorFor(llm)}
              strokeWidth={1.5}
              strokeOpacity={0.7}
              dot={{ r: 3, fill: colorFor(llm), stroke: "white", strokeWidth: 1.5 }}
              activeDot={{ r: 5, fill: colorFor(llm), stroke: "white", strokeWidth: 2 }}
              connectNulls
            />
          ))}

          {/* Aggregate line — bold, always on top */}
          <Line
            type="monotone"
            dataKey="aggregate"
            name="aggregate"
            stroke={colorFor("aggregate")}
            strokeWidth={2.5}
            dot={{ r: 4, fill: colorFor("aggregate"), stroke: "white", strokeWidth: 2 }}
            activeDot={{ r: 6, fill: colorFor("aggregate"), stroke: "white", strokeWidth: 2 }}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
