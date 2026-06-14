"use client";

import dynamic from "next/dynamic";
import type { TerritoryMapBlock } from "@/lib/brand/types";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

const CHART_FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif";

const TIER_LABELS: Record<string, string> = {
  brand_category: "Brand",
  use_case: "Use Case",
  competitor_trigger: "Competitor Trigger",
};

const STRENGTH_LABELS: Record<string, string> = {
  listed: "Listed",
  attributed: "Attributed",
  recommended: "Recommended",
  default: "Default",
  absent: "Absent",
};

// Territory status badge colours
const OWNED_COLOR = "#dcfce7";
const CONTESTED_COLOR = "#fef9c3";
const ABSENT_COLOR = "#f5f5f5";

function TerritoryBadge({
  label,
  color,
  items,
}: {
  label: string;
  color: string;
  items: string[];
}) {
  if (!items.length) return null;
  return (
    <div className="flex items-start gap-2">
      <span
        className="mt-0.5 shrink-0 w-3 h-3 rounded-sm border border-black/10"
        style={{ background: color }}
      />
      <div style={{ fontFamily: CHART_FONT }}>
        <span className="text-[10px] tracking-[0.12em] uppercase text-neutral-grey-20 font-medium">
          {label}:{" "}
        </span>
        <span className="text-[11px] text-primary-black">
          {items.slice(0, 3).join(", ")}
          {items.length > 3 ? ` +${items.length - 3}` : ""}
        </span>
      </div>
    </div>
  );
}

type TerritoryHeatmapProps = {
  data: TerritoryMapBlock;
};

export default function TerritoryHeatmap({ data }: TerritoryHeatmapProps) {
  const rows = data?.rows ?? [];
  const owned_territories = data?.owned_territories ?? [];
  const contested_territories = data?.contested_territories ?? [];
  const absent_territories = data?.absent_territories ?? [];

  if (!rows.length) {
    return (
      <div className="flex flex-col items-center justify-center h-[220px] gap-2">
        <p className="text-sm text-neutral-grey-20">No territory data yet.</p>
      </div>
    );
  }

  // Build ECharts heatmap data: [colIndex, rowIndex, value]
  const allStrengths = ["listed", "attributed", "recommended", "default", "absent"];
  const allTiers = rows.map((r) => r.id);

  const chartData: [number, number, number][] = [];
  let maxVal = 0;

  rows.forEach((row, rowIdx) => {
    allStrengths.forEach((strength, colIdx) => {
      const cell = row.data.find((c) => c.x === strength);
      const val = cell?.y ?? 0;
      if (val > maxVal) maxVal = val;
      chartData.push([colIdx, rowIdx, val]);
    });
  });

  const colLabels = allStrengths.map((s) => STRENGTH_LABELS[s] ?? s);
  const rowLabels = allTiers.map((t) => TIER_LABELS[t] ?? t);

  const option = {
    tooltip: {
      trigger: "item",
      formatter: (p: { data: [number, number, number] }) => {
        const [col, row, val] = p.data;
        const tier = rowLabels[row] ?? "";
        const strength = colLabels[col] ?? "";
        return `<span style="font-family:${CHART_FONT};font-size:12px">
          <b>${tier}</b><br/>${strength}: <b>${val}</b> keyword${val !== 1 ? "s" : ""}
        </span>`;
      },
      backgroundColor: "#fff",
      borderColor: "rgba(0,0,0,0.08)",
      borderWidth: 1,
      extraCssText: "box-shadow:0 2px 8px rgba(0,0,0,0.08);border-radius:8px;",
    },
    grid: { top: 40, right: 20, bottom: 10, left: 140 },
    xAxis: {
      type: "category",
      data: colLabels,
      splitArea: { show: true },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        fontFamily: CHART_FONT,
        fontSize: 11,
        color: "#767676",
        interval: 0,
      },
    },
    yAxis: {
      type: "category",
      data: rowLabels,
      splitArea: { show: true },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        fontFamily: CHART_FONT,
        fontSize: 11,
        color: "#767676",
        width: 120,
        overflow: "truncate",
      },
    },
    visualMap: {
      min: 0,
      max: maxVal || 1,
      calculable: false,
      show: false,
      inRange: {
        // 0 → near white, max → secondary-green
        color: ["#f0fdf4", "#86efac", "#5CFE50"],
      },
    },
    series: [
      {
        type: "heatmap",
        data: chartData,
        label: {
          show: true,
          fontFamily: CHART_FONT,
          fontSize: 12,
          fontWeight: 500,
          color: "#1D1D1D",
          formatter: (p: { data: [number, number, number] }) =>
            p.data[2] === 0 ? "" : String(p.data[2]),
        },
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowColor: "rgba(0,0,0,0.1)" },
        },
        itemStyle: {
          borderColor: "#fff",
          borderWidth: 3,
          borderRadius: 4,
        },
      },
    ],
  };

  return (
    <div>
      <ReactECharts
        option={option}
        style={{ width: "100%", height: 200 }}
        opts={{ renderer: "svg" }}
      />

      <div
        className="mt-3 flex flex-col gap-1.5 text-[11px] border-t border-black/5 pt-3"
        style={{ fontFamily: CHART_FONT }}
      >
        <TerritoryBadge label="Owned" color={OWNED_COLOR} items={owned_territories} />
        <TerritoryBadge label="Contested" color={CONTESTED_COLOR} items={contested_territories} />
        <TerritoryBadge label="Gap" color={ABSENT_COLOR} items={absent_territories} />
      </div>
    </div>
  );
}
