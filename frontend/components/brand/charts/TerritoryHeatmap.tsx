"use client";

import dynamic from "next/dynamic";
import type { TerritoryMapBlock } from "@/lib/brand/types";

// ---------------------------------------------------------------------------
// Dynamic import — Nivo uses browser APIs
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ResponsiveHeatMap = dynamic<any>(
  () => import("@nivo/heatmap").then((m) => m.ResponsiveHeatMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-[320px] text-xs text-neutral-grey-20">
        Loading heatmap…
      </div>
    ),
  }
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STRENGTH_LABELS: Record<string, string> = {
  listed: "Listed",
  attributed: "Attributed",
  recommended: "Recommended",
  default: "Default",
};

const TIER_LABELS: Record<string, string> = {
  brand_category: "Brand & Category",
  use_case: "Use Case",
  competitor_trigger: "Competitor Trigger",
};

// Ownership badge colours
const OWNED_COLOR = "#dcfce7";    // green-100
const CONTESTED_COLOR = "#fef9c3"; // yellow-100
const ABSENT_COLOR = "#f5f5f5";   // grey-00

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

function CellTooltip({
  cell,
}: {
  cell: {
    id: string;
    serieId: string;
    value: number | null;
    data: { x: string; y: number };
  };
}) {
  const tier = TIER_LABELS[cell.serieId] ?? cell.serieId;
  const strength = STRENGTH_LABELS[cell.data.x] ?? cell.data.x;
  const count = cell.value ?? 0;

  return (
    <div
      className="rounded-lg border border-black/8 bg-white px-3 py-2.5 shadow-md text-xs"
      style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
    >
      <div className="font-semibold text-primary-black mb-1">
        {tier} — {strength}
      </div>
      <div className="text-neutral-grey-20">
        {count} keyword{count !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Territory status legend helper
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
  if (!items.length) return null;
  return (
    <div className="flex items-start gap-2">
      <span
        className="mt-0.5 shrink-0 w-3 h-3 rounded-sm border border-black/10"
        style={{ background: color }}
      />
      <div>
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

// ---------------------------------------------------------------------------
// Chart
// ---------------------------------------------------------------------------

type TerritoryHeatmapProps = {
  data: TerritoryMapBlock;
};

export default function TerritoryHeatmap({ data }: TerritoryHeatmapProps) {
  const { rows, owned_territories, contested_territories, absent_territories } =
    data;

  if (!rows.length) {
    return (
      <div className="flex flex-col items-center justify-center h-[320px] gap-2">
        <p className="text-sm text-neutral-grey-20">No territory data yet.</p>
        <p className="text-xs text-neutral-grey-10">
          Requires at least one pipeline run with structured keyword analysis.
        </p>
      </div>
    );
  }

  // Relabel row ids and cell x-values for display
  const displayRows = rows.map((row) => ({
    id: TIER_LABELS[row.id] ?? row.id,
    data: row.data.map((cell) => ({
      x: STRENGTH_LABELS[cell.x] ?? cell.x,
      y: cell.y,
    })),
  }));

  return (
    <div>
      <div style={{ height: 260 }}>
        <ResponsiveHeatMap
          data={displayRows}
          margin={{ top: 20, right: 20, bottom: 40, left: 130 }}
          valueFormat=">-.0f"
          colors={{
            type: "sequential",
            scheme: "greens",
            minValue: 0,
          }}
          emptyColor="#f5f5f5"
          borderRadius={4}
          borderWidth={2}
          borderColor="#ffffff"
          enableLabels
          labelTextColor={(cell: { value: number }) =>
            (cell.value ?? 0) > 3 ? "#ffffff" : "#1D1D1D"
          }
          axisTop={null}
          axisLeft={{
            tickSize: 0,
            tickPadding: 8,
            legend: "",
            legendOffset: 0,
          }}
          axisBottom={{
            tickSize: 0,
            tickPadding: 8,
            legend: "",
            legendOffset: 36,
          }}
          tooltip={CellTooltip}
          animate={false}
          theme={{
            text: {
              fontFamily: "system-ui, -apple-system, sans-serif",
              fontSize: 11,
              fill: "#767676",
            },
            axis: {
              ticks: {
                text: {
                  fontFamily: "system-ui, -apple-system, sans-serif",
                  fontSize: 11,
                  fill: "#767676",
                },
              },
            },
          }}
        />
      </div>

      {/* Territory status */}
      <div
        className="mt-4 flex flex-col gap-2 text-[11px] border-t border-black/5 pt-4"
        style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
      >
        <TerritoryBadge
          label="Owned"
          color={OWNED_COLOR}
          items={owned_territories}
        />
        <TerritoryBadge
          label="Contested"
          color={CONTESTED_COLOR}
          items={contested_territories}
        />
        <TerritoryBadge
          label="Gap"
          color={ABSENT_COLOR}
          items={absent_territories}
        />
      </div>
    </div>
  );
}
