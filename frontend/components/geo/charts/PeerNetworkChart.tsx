"use client";

import dynamic from "next/dynamic";
import type { PeerNetworkBlock } from "@/lib/brand/types";

// ECharts must be imported client-side only (uses window)
const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

const CHART_FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif";

type PeerNetworkChartProps = {
  data: PeerNetworkBlock;
};

export default function PeerNetworkChart({ data }: PeerNetworkChartProps) {
  const nodes = data?.nodes ?? [];
  const links = data?.links ?? [];
  const primary_peer_group = new Set(data?.primary_peer_group ?? []);

  if (!nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center h-[320px] gap-2">
        <p className="text-sm text-neutral-grey-20">No co-mentions found yet.</p>
        <p className="text-xs text-neutral-grey-10">
          Run the pipeline on more keywords to populate the network.
        </p>
      </div>
    );
  }

  const maxWeight = Math.max(...nodes.map((n) => n.weight));

  const echartsNodes = nodes.map((n) => ({
    id: n.id,
    name: n.id,
    value: n.weight,
    symbolSize: n.is_target
      ? 38
      : Math.max(12, Math.round(12 + (n.weight / maxWeight) * 20)),
    itemStyle: {
      color: n.is_target
        ? "#5CFE50"
        : primary_peer_group.has(n.id)
        ? "#3233F5"
        : "#4B4B4B",
      borderColor: n.is_target ? "#16a34a" : "rgba(255,255,255,0.15)",
      borderWidth: 1.5,
    },
    isTarget: n.is_target,
    label: {
      show: n.is_target || n.weight >= 4,
      color: n.is_target ? "#0D0D0D" : "#E5E5E5",
      fontSize: 11,
      fontFamily: CHART_FONT,
      fontWeight: n.is_target ? 700 : 400,
      formatter: (p: { name: string }) =>
        p.name.length > 16 ? p.name.slice(0, 14) + "…" : p.name,
    },
  }));

  const echartsLinks = links.map((l) => ({
    source: l.source,
    target: l.target,
    value: l.weight,
    lineStyle: {
      // Cap at 4px — high co-mention counts otherwise produce absurdly thick edges
      width: Math.min(4, Math.max(1, Math.round(l.weight * 0.3))),
      color: "rgba(255,255,255,0.18)",
      curveness: 0,
      opacity: 0.9,
    },
  }));

  const option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      formatter: (p: { data: { name: string; value?: number; isTarget?: boolean } }) => {
        if (!p.data?.name) return "";
        const count = p.data.value ?? 0;
        const sublabel = p.data.isTarget
          ? `Mentioned in <b>${count}</b> of 30 keywords`
          : `Co-mentioned in <b>${count}</b> keyword${count !== 1 ? "s" : ""} alongside Celonis`;
        return `<div style="font-family:${CHART_FONT};font-size:12px">
          <b>${p.data.name}</b><br/><span style="color:#767676;font-size:11px">${sublabel}</span>
        </div>`;
      },
      backgroundColor: "#1a1a1a",
      borderColor: "rgba(255,255,255,0.1)",
      borderWidth: 1,
      textStyle: { color: "#E5E5E5" },
      extraCssText: "box-shadow:0 4px 12px rgba(0,0,0,0.4);border-radius:8px;padding:8px 12px;",
    },
    series: [
      {
        type: "graph",
        layout: "force",
        data: echartsNodes,
        links: echartsLinks,
        roam: true,
        draggable: true,
        force: {
          repulsion: 200,
          gravity: 0.12,
          edgeLength: [40, 180],
          layoutAnimation: true,
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: { width: 2, color: "rgba(255,255,255,0.5)" },
        },
        lineStyle: { opacity: 0.7 },
      },
    ],
  };

  return (
    <div>
      <ReactECharts
        option={option}
        style={{ width: "100%", height: 320 }}
        opts={{ renderer: "svg" }}
      />
      <div
        className="flex items-center gap-5 text-[11px] text-neutral-grey-20"
        style={{ fontFamily: CHART_FONT }}
      >
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-secondary-green border-2 border-green-600 shrink-0" />
          <span>Celonis</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-secondary-blue shrink-0" />
          <span>Primary peer group</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-neutral-grey-10 shrink-0" />
          <span>Other mentions</span>
        </div>
        <span className="ml-auto text-neutral-grey-10">Node size = frequency · drag to explore</span>
      </div>
    </div>
  );
}
