"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
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

/** Pretty-print LLM model names to keep axis labels concise. */
function labelLlm(raw: string): string {
  const map: Record<string, string> = {
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o mini",
    "gpt-4": "GPT-4",
    "gpt-3.5-turbo": "GPT-3.5",
    "gemini-pro": "Gemini Pro",
    "gemini-1.5-pro": "Gemini 1.5",
    "claude-3-opus": "Claude Opus",
    "claude-3-sonnet": "Claude Sonnet",
    "claude-3-haiku": "Claude Haiku",
  };
  return map[raw] ?? raw;
}

// ---------------------------------------------------------------------------
// Custom renderers
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const value: number = payload[0]?.value ?? 0;
  return (
    <div
      className="rounded-lg border border-black/8 bg-white px-3 py-2.5 shadow-md text-xs"
      style={CHART_FONT}
    >
      <div className="font-semibold text-neutral-grey-30 mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{ background: payload[0]?.fill }}
        />
        <span className="text-neutral-grey-20">Mention rate</span>
        <span className="ml-auto font-semibold text-primary-black pl-4">
          {value.toFixed(1)}%
        </span>
      </div>
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

  const maxValue = Math.max(...data.map((d) => d.mention_rate * 100));

  const points = data.map((d) => ({
    llm: labelLlm(d.llm),
    rawLlm: d.llm,
    value: Math.round(d.mention_rate * 100 * 10) / 10,
    isTop: d.mention_rate * 100 === maxValue,
  }));

  return (
    <div style={CHART_FONT}>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart
          data={points}
          margin={{ top: 8, right: 16, bottom: 0, left: -8 }}
          barCategoryGap="40%"
        >
          <CartesianGrid
            stroke="#f0f0f0"
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
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "#f5f5f5" }} />
          <Bar dataKey="value" name="Mention rate" radius={[4, 4, 0, 0]}>
            {points.map((entry) => (
              <Cell
                key={entry.rawLlm}
                fill={entry.isTop ? "#5CFE50" : "#CBCBCB"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

    </div>
  );
}
