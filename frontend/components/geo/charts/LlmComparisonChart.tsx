"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

import type { LlmComparisonPoint } from "@/lib/brand/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
  fontVariantNumeric: "tabular-nums",
  fontSize: 11,
};

const AXIS_TICK = { fill: "#767676", fontSize: 11 };

const MENTION_COLOR = "#5CFE50";
const REC_COLOR = "#A3E8FE";

function labelLlm(raw: string): string {
  const map: Record<string, string> = {
    "gpt-5.5": "GPT-5.5",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o mini",
    "gpt-4": "GPT-4",
    "claude-sonnet-4-6": "Claude Sonnet",
    "claude-3-opus": "Claude Opus",
    "claude-3-sonnet": "Claude Sonnet",
    "claude-3-haiku": "Claude Haiku",
    "sonar-pro": "Perplexity",
    "gemini-pro": "Gemini Pro",
    "gemini-1.5-pro": "Gemini 1.5",
    aggregate: "Aggregate",
  };
  return map[raw] ?? raw;
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
      {payload.map((p: { name: string; value: number; fill: string }) => (
        <div key={p.name} className="flex items-center gap-2 mb-0.5">
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: p.fill }}
          />
          <span className="text-neutral-grey-20">{p.name}</span>
          <span className="ml-auto font-semibold text-primary-black pl-4">
            {p.value.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart
// ---------------------------------------------------------------------------

type LlmComparisonChartProps = {
  data: LlmComparisonPoint[];
};

export default function LlmComparisonChart({ data }: LlmComparisonChartProps) {
  if (!data?.length) {
    return (
      <div className="flex items-center justify-center h-[260px] text-sm text-neutral-grey-20">
        No LLM data available.
      </div>
    );
  }

  const points = data.map((d) => ({
    llm: labelLlm(d.llm),
    rawLlm: d.llm,
    "Mention rate": Math.round(d.mention_rate * 100 * 10) / 10,
    "Recommendation rate": Math.round(d.recommendation_rate * 100 * 10) / 10,
  }));

  return (
    <div style={CHART_FONT}>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart
          data={points}
          margin={{ top: 8, right: 16, bottom: 0, left: -8 }}
          barCategoryGap="30%"
          barGap={4}
        >
          <CartesianGrid
            stroke="rgba(255,255,255,0.08)"
            strokeDasharray="4 4"
            vertical={false}
          />
          <XAxis
            dataKey="llm"
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            dy={8}
          />
          <YAxis
            domain={[0, 100]}
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            dx={-4}
            tickFormatter={(v: number) => `${v}%`}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
          <Legend
            wrapperStyle={{ ...CHART_FONT, paddingTop: 8 }}
            iconType="circle"
            iconSize={8}
          />
          <Bar
            dataKey="Mention rate"
            fill={MENTION_COLOR}
            radius={[4, 4, 0, 0]}
          />
          <Bar
            dataKey="Recommendation rate"
            fill={REC_COLOR}
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
