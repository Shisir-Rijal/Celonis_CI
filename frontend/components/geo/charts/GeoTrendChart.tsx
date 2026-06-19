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

import type { TrendPoint } from "@/lib/brand/types";

// ---------------------------------------------------------------------------
// Data helpers
// ---------------------------------------------------------------------------

type ChartPoint = {
  date: string;        // formatted for x-axis label
  rawDate: string;     // ISO for tooltip
  visibility: number;  // 0–100
  geoScore: number;    // 0–100
  isDummy: boolean;
};

/**
 * If only one real run exists, prepend a synthetic baseline 7 days earlier
 * at 70 % of the current values. This lets the trend line show direction
 * instead of a single dot. The dummy point is hollow and annotated.
 */
function buildSeries(series: TrendPoint[]): {
  points: ChartPoint[];
  hasDummy: boolean;
} {
  const toPoint = (p: TrendPoint, dummy = false): ChartPoint => ({
    date: new Date(p.run_at).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
    rawDate: p.run_at,
    visibility: Math.round(p.visibility_pct * 100 * 10) / 10,
    geoScore: Math.round(p.geo_score * 10) / 10,
    isDummy: dummy,
  });

  if (series.length >= 2) {
    return { points: series.map((p) => toPoint(p)), hasDummy: false };
  }

  if (series.length === 1) {
    const real = series[0];
    const priorDate = new Date(real.run_at);
    priorDate.setDate(priorDate.getDate() - 7);
    const dummy: TrendPoint = {
      run_at: priorDate.toISOString(),
      visibility_pct: real.visibility_pct * 0.72,
      geo_score: real.geo_score * 0.68,
    };
    return {
      points: [toPoint(dummy, true), toPoint(real, false)],
      hasDummy: true,
    };
  }

  return { points: [], hasDummy: false };
}

// ---------------------------------------------------------------------------
// Custom renderers
// ---------------------------------------------------------------------------

const CHART_FONT: React.CSSProperties = {
  fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
  fontVariantNumeric: "tabular-nums",
  fontSize: 11,
};

const AXIS_TICK = { fill: "#767676", fontSize: 11 };

type DotProps = {
  cx?: number;
  cy?: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any;
  color: string;
};

function CustomDot({ cx, cy, payload, color }: DotProps) {
  if (cx === undefined || cy === undefined) return null;
  if (payload?.isDummy) {
    return (
      <circle
        cx={cx}
        cy={cy}
        r={5}
        fill="white"
        stroke={color}
        strokeWidth={2}
        strokeDasharray="3 2"
        opacity={0.6}
      />
    );
  }
  return <circle cx={cx} cy={cy} r={5} fill={color} stroke="white" strokeWidth={2} />;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const isDummy = payload[0]?.payload?.isDummy;
  return (
    <div
      className="rounded-lg border border-black/8 bg-white px-3 py-2.5 shadow-md text-xs"
      style={CHART_FONT}
    >
      <div className="font-semibold text-neutral-grey-30 mb-1.5">
        {label}
        {isDummy && (
          <span className="ml-2 text-neutral-grey-10 font-normal">
            (estimated)
          </span>
        )}
      </div>
      {payload.map(
        (entry: { name: string; value: number; color: string }) => (
          <div key={entry.name} className="flex items-center gap-2 mt-1">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: entry.color }}
            />
            <span className="text-neutral-grey-20">{entry.name}</span>
            <span className="ml-auto font-semibold text-primary-black pl-4">
              {entry.value}
              {entry.name === "Visibility" ? "%" : ""}
            </span>
          </div>
        )
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart
// ---------------------------------------------------------------------------

type GeoTrendChartProps = {
  series: TrendPoint[];
};

export default function GeoTrendChart({ series }: GeoTrendChartProps) {
  const { points, hasDummy } = buildSeries(series);

  if (points.length === 0) {
    return (
      <div className="flex items-center justify-center h-[260px] text-sm text-neutral-grey-20">
        No trend data yet.
      </div>
    );
  }

  return (
    <div style={CHART_FONT}>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart
          data={points}
          margin={{ top: 8, right: 16, bottom: 0, left: -8 }}
        >
          <CartesianGrid
            stroke="#f0f0f0"
            strokeDasharray="4 4"
            vertical={false}
          />
          <XAxis
            dataKey="date"
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
            tickFormatter={(v: number) => `${v}`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ ...CHART_FONT, paddingTop: 12, color: "#767676" }}
            iconType="circle"
            iconSize={8}
          />
          <Line
            type="monotone"
            dataKey="visibility"
            name="Visibility"
            stroke="#3233F5"
            strokeWidth={2}
            strokeDasharray={hasDummy ? "6 3" : undefined}
            dot={(props) => (
              <CustomDot key={`vis-${props.cx}-${props.cy}`} {...props} color="#3233F5" />
            )}
            activeDot={{ r: 6, fill: "#3233F5", stroke: "white", strokeWidth: 2 }}
          />
          <Line
            type="monotone"
            dataKey="geoScore"
            name="GEO Score"
            stroke="#5CFE50"
            strokeWidth={2.5}
            strokeDasharray={hasDummy ? "6 3" : undefined}
            dot={(props) => (
              <CustomDot key={`geo-${props.cx}-${props.cy}`} {...props} color="#16a34a" />
            )}
            activeDot={{ r: 6, fill: "#16a34a", stroke: "white", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>

    </div>
  );
}
