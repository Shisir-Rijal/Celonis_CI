"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import type { TerritoryMapBlock } from "@/lib/brand/types";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

const CHART_FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif";

const TIER_LABELS: Record<string, string> = {
  brand_category: "Brand",
  use_case: "Use Case",
  competitor_trigger: "Competitor Trigger",
};

// Left = weakest / not present, right = strongest signal
const STRENGTH_ORDER = ["absent", "listed", "attributed", "recommended", "organic"];

const STRENGTH_LABELS: Record<string, string> = {
  absent: "Absent",
  listed: "Listed",
  attributed: "Attributed",
  recommended: "Recommended",
  organic: "Organic",
};

// Tooltip explaining each strength level — shown on cell hover
const STRENGTH_DESCRIPTIONS: Record<string, string> = {
  absent: "Not mentioned for this keyword",
  listed: "Listed among providers, no emphasis",
  attributed: "A capability is attributed, not a recommendation",
  recommended: "Actively suggested when alternatives are asked",
  organic: "Unprompted first choice — named without being asked",
};

const OWNED_COLOR = "#dcfce7";
const CONTESTED_COLOR = "#fef9c3";
const ABSENT_COLOR = "#f5f5f5";

// ---------------------------------------------------------------------------
// Territory badge with hover tooltip for overflow items
// ---------------------------------------------------------------------------

function TerritoryBadge({
  label,
  color,
  items,
}: {
  label: string;
  color: string;
  items: string[];
}) {
  const [tooltipOpen, setTooltipOpen] = useState(false);
  if (!items.length) return null;

  const visible = items.slice(0, 3);
  const overflow = items.slice(3);

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
        <span className="text-[11px] text-primary-white">
          {visible.join(", ")}
          {overflow.length > 0 && (
            <span className="relative inline-block">
              <button
                type="button"
                className="ml-1 text-secondary-green underline underline-offset-2 cursor-pointer hover:text-secondary-green/80 transition-colors"
                onMouseEnter={() => setTooltipOpen(true)}
                onMouseLeave={() => setTooltipOpen(false)}
                onClick={() => setTooltipOpen((o) => !o)}
              >
                +{overflow.length}
              </button>
              {tooltipOpen && (
                <div
                  className="absolute bottom-full left-0 mb-1.5 z-50 min-w-[200px] max-w-[280px] rounded-lg border border-black/8 bg-white shadow-lg px-3 py-2"
                  style={{ fontFamily: CHART_FONT }}
                >
                  <p className="text-[10px] tracking-[0.1em] uppercase text-neutral-grey-20 font-medium mb-1">
                    {label} — all keywords
                  </p>
                  <ul className="space-y-0.5">
                    {items.map((item) => (
                      <li key={item} className="text-[11px] text-primary-black leading-snug">
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </span>
          )}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Heatmap
// ---------------------------------------------------------------------------

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
      <div className="flex flex-col items-center justify-center h-55 gap-2">
        <p className="text-sm text-neutral-grey-20">No territory data yet.</p>
      </div>
    );
  }

  const allTiers = rows.map((r) => r.id);

  const chartData: [number, number, number][] = [];
  let maxVal = 0;

  rows.forEach((row, rowIdx) => {
    STRENGTH_ORDER.forEach((strength, colIdx) => {
      const cell = row.data.find((c) => c.x === strength);
      const val = cell?.y ?? 0;
      if (val > maxVal) maxVal = val;
      // Include all cells (val=0 too) so empty cells are hoverable.
      // visualMap outOfRange renders them transparent.
      chartData.push([colIdx, rowIdx, val]);
    });
  });

  const colLabels = STRENGTH_ORDER.map((s) => STRENGTH_LABELS[s]);
  const rowLabels = allTiers.map((t) => TIER_LABELS[t] ?? t);

  const option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      formatter: (p: { data: [number, number, number] }) => {
        const [col, row, val] = p.data;
        const tier = rowLabels[row] ?? "";
        const strength = STRENGTH_ORDER[col] ?? "";
        const label = STRENGTH_LABELS[strength] ?? strength;
        const desc = STRENGTH_DESCRIPTIONS[strength] ?? "";
        return `<div style="font-family:${CHART_FONT};font-size:12px;max-width:180px;word-wrap:break-word;white-space:normal">
          <b style="color:#E5E5E5">${tier} · ${label}</b>
          <div style="color:#767676;font-size:11px;margin-top:3px;line-height:1.4">${desc}</div>
          <div style="margin-top:5px;font-size:13px;color:#E5E5E5"><b>${val}</b> keyword${val !== 1 ? "s" : ""}</div>
        </div>`;
      },
      backgroundColor: "#1a1a1a",
      borderColor: "rgba(255,255,255,0.1)",
      borderWidth: 1,
      textStyle: { color: "#E5E5E5" },
      extraCssText: "box-shadow:0 4px 12px rgba(0,0,0,0.4);border-radius:8px;padding:10px 12px;max-width:200px;",
    },
    grid: { top: 40, right: 20, bottom: 10, left: 140 },
    xAxis: {
      type: "category",
      data: colLabels,
      splitArea: {
        show: true,
        areaStyle: {
          color: ["rgba(255,255,255,0.03)", "rgba(255,255,255,0.06)"],
        },
      },
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
      splitArea: {
        show: true,
        areaStyle: {
          color: ["rgba(255,255,255,0.03)", "rgba(255,255,255,0.06)"],
        },
      },
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
      min: 1,
      max: maxVal || 1,
      calculable: false,
      show: false,
      inRange: {
        color: ["rgba(92,254,80,0.25)", "#86efac", "#5CFE50"],
      },
      // Values below min (i.e. 0) are rendered transparent so the cell
      // exists geometrically (hover works) but is invisible.
      outOfRange: {
        color: ["rgba(0,0,0,0)"],
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
          fontWeight: 600,
          color: "#0D0D0D",
          formatter: (p: { data: [number, number, number] }) =>
            p.data[2] === 0 ? "" : String(p.data[2]),
        },
        emphasis: {
          itemStyle: { shadowBlur: 8, shadowColor: "rgba(92,254,80,0.3)" },
        },
        itemStyle: {
          borderColor: "rgba(0,0,0,0.5)",
          borderWidth: 2,
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

      <p className="mt-1 text-[10px] text-neutral-grey-10 text-center" style={{ fontFamily: CHART_FONT }}>
        ← not present &nbsp;·&nbsp; columns left to right = increasing AI recommendation strength &nbsp;·&nbsp; hover cell for definition
      </p>

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
