"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { getCompetitorColor } from "@/lib/competitors/colors";
import type { NewsArticle } from "@/lib/news/types";

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
  fontSize: 11,
};

const AXIS_TICK = { fill: "#767676", fontSize: 11 };

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

function toMonthKey(ms: number): string {
  const d = new Date(ms);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

type CompanyArticles = {
  company: string;
  name: string;
  articles: NewsArticle[];
};

type NewsTrendChartProps = {
  companies: CompanyArticles[];
  allCompanies: string[];
  brandColors?: Record<string, string>;
};

export default function NewsTrendChart({
  companies,
  allCompanies,
  brandColors = {},
}: NewsTrendChartProps) {
  const monthSet = new Set<string>();
  const companyMonthCounts: Record<string, Record<string, number>> = {};

  for (const { company, articles } of companies) {
    companyMonthCounts[company] = {};
    for (const article of articles) {
      const ms = parseDateToMs(article.published_date);
      if (ms === 0) continue;
      const key = toMonthKey(ms);
      monthSet.add(key);
      companyMonthCounts[company][key] =
        (companyMonthCounts[company][key] ?? 0) + 1;
    }
  }

  const months = [...monthSet].sort(
    (a, b) => new Date(a).getTime() - new Date(b).getTime()
  );

  if (months.length === 0) {
    return (
      <div className="flex items-center justify-center h-[280px] text-sm text-neutral-grey-20">
        No trend data yet.
      </div>
    );
  }

  const chartData = months.map((month) => {
    const point: Record<string, string | number> = { month };
    for (const { company, name } of companies) {
      point[name] = companyMonthCounts[company][month] ?? 0;
    }
    return point;
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function CustomTooltip({ active, payload, label }: any) {
    if (!active || !payload?.length) return null;
    const nonZero = payload.filter((e: { value: number }) => e.value > 0);
    if (nonZero.length === 0) return null;
    return (
      <div
        className="rounded-lg border border-white/10 bg-neutral-grey-30 px-3 py-2.5 shadow-md text-xs max-w-[200px]"
        style={CHART_FONT}
      >
        <div className="font-medium text-primary-white mb-1.5">{label}</div>
        {nonZero.map((entry: { name: string; value: number; color: string }) => (
          <div key={entry.name} className="flex items-center gap-2 mt-1">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: entry.color }}
            />
            <span className="text-neutral-grey-20 truncate">{entry.name}</span>
            <span className="ml-auto font-semibold text-primary-white pl-2">
              {entry.value}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={CHART_FONT}>
      {/* Legend — rendered outside chart to avoid overlap */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3">
        {companies.map(({ company, name }) => (
          <div key={company} className="flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{
                background: getCompetitorColor(company, allCompanies, brandColors),
              }}
            />
            <span className="text-[10px] text-neutral-grey-20">{name}</span>
          </div>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={250}>
        <LineChart
          data={chartData}
          margin={{ top: 8, right: 16, bottom: 0, left: -8 }}
        >
          <CartesianGrid
            stroke="#ffffff10"
            strokeDasharray="4 4"
            vertical={false}
          />
          <XAxis
            dataKey="month"
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            dy={8}
            height={70}
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
            position={{ y: 0 }}
          />
          {companies.map(({ company, name }) => (
            <Line
              key={company}
              type="monotone"
              dataKey={name}
              stroke={getCompetitorColor(company, allCompanies, brandColors)}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3, strokeWidth: 0 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}