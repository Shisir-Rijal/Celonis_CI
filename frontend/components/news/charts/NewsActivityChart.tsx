"use client";

import { useState, useMemo } from "react";
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
import { getCompetitorColor } from "@/lib/competitors/colors";
import type { NewsArticle } from "@/lib/news/types";

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
  fontSize: 11,
};

const AXIS_TICK = { fill: "#767676", fontSize: 10 };

type Period = "all" | "7d" | "30d" | "3m";

const PERIOD_OPTIONS: { value: Period; label: string }[] = [
  { value: "all", label: "All time" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "3m", label: "3m" },
];

const RELATIVE_UNIT_MS: Record<string, number> = {
  hour: 60 * 60 * 1000,
  hours: 60 * 60 * 1000,
  day: 24 * 60 * 60 * 1000,
  days: 24 * 60 * 60 * 1000,
  week: 7 * 24 * 60 * 60 * 1000,
  weeks: 7 * 24 * 60 * 60 * 1000,
  month: 30 * 24 * 60 * 60 * 1000,
  months: 30 * 24 * 60 * 60 * 1000,
};

function parseDateToMs(dateStr: string | null): number {
  if (!dateStr) return 0;
  const parsed = new Date(dateStr);
  if (!isNaN(parsed.getTime())) return parsed.getTime();
  const match = dateStr.match(/(\d+)\s+(hour|hours|day|days|week|weeks|month|months)\s+ago/i);
  if (match) {
    const amount = parseInt(match[1], 10);
    const unit = match[2].toLowerCase();
    return Date.now() - amount * (RELATIVE_UNIT_MS[unit] ?? 0);
  }
  return 0;
}

function getCutoff(period: Period): number {
  const now = Date.now();
  switch (period) {
    case "7d": return now - 7 * 24 * 60 * 60 * 1000;
    case "30d": return now - 30 * 24 * 60 * 60 * 1000;
    case "3m": return now - 90 * 24 * 60 * 60 * 1000;
    default: return 0;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-lg border border-white/10 bg-neutral-grey-30 px-3 py-2.5 shadow-md text-xs"
      style={CHART_FONT}
    >
      <div className="font-medium text-primary-white mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{ background: payload[0].fill }}
        />
        <span className="text-neutral-grey-20">Articles</span>
        <span className="ml-auto font-semibold text-primary-white pl-4">
          {payload[0].value}
        </span>
      </div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomXAxisTick({ x, y, payload }: any) {
  const firstName = (payload?.value ?? "").split(" ")[0];
  return (
    <g transform={`translate(${x},${y + 4})`}>
      <text
        textAnchor="end"
        fill="#767676"
        fontSize={10}
        transform="rotate(-45)"
      >
        {firstName}
      </text>
    </g>
  );
}

type CompanyData = {
  company: string;
  name: string;
  articles: NewsArticle[];
};

type NewsActivityChartProps = {
  data: CompanyData[];
  allCompanies: string[];
  brandColors?: Record<string, string>;
};

export default function NewsActivityChart({
  data,
  allCompanies,
  brandColors = {},
}: NewsActivityChartProps) {
  const [period, setPeriod] = useState<Period>("all");

  const chartData = useMemo(() => {
    const cutoff = getCutoff(period);
    return data
      .map((c) => ({
        company: c.company,
        name: c.name,
        count:
          cutoff > 0
            ? c.articles.filter((a) => parseDateToMs(a.published_date) >= cutoff).length
            : c.articles.length,
      }))
      .sort((a, b) => b.count - a.count);
  }, [data, period]);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[200px] text-sm text-neutral-grey-20">
        No data yet.
      </div>
    );
  }

  return (
    <div style={CHART_FONT}>
      {/* Internal period filter */}
      <div className="flex items-center gap-1 mb-4">
        {PERIOD_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setPeriod(opt.value)}
            className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
              period === opt.value
                ? "bg-white/10 text-primary-white border-white/30"
                : "bg-transparent text-neutral-grey-20 border-white/10 hover:border-white/20"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={chartData}
          margin={{ top: 8, right: 16, bottom: 8, left: -8 }}
          barSize={18}
        >
          <CartesianGrid
            stroke="#ffffff10"
            strokeDasharray="4 4"
            vertical={false}
          />
          <XAxis
            dataKey="name"
            tick={<CustomXAxisTick />}
            axisLine={false}
            tickLine={false}
            interval={0}
            height={80}
          />
          <YAxis
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            dx={-4}
            allowDecimals={false}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {chartData.map((entry) => (
              <Cell
                key={entry.company}
                fill={getCompetitorColor(entry.company, allCompanies, brandColors)}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}