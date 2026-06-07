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
      ? 36
      : Math.max(10, Math.round(10 + (n.weight / maxWeight) * 22)),
    itemStyle: {
      color: n.is_target
        ? "#5CFE50"
        : primary_peer_group.has(n.id)
        ? "#3233F5"
        : "#CBCBCB",
      borderColor: n.is_target ? "#16a34a" : "#ffffff",
      borderWidth: 2,
    },
    isTarget: n.is_target,
    label: {
      show: n.is_target || n.weight >= 6,
      color: "#1D1D1D",
      fontSize: 11,
      fontFamily: CHART_FONT,
      fontWeight: n.is_target ? 600 : 400,
      formatter: (p: { name: string }) =>
        p.name.length > 16 ? p.name.slice(0, 14) + "…" : p.name,
    },
  }));

  const echartsLinks = links.map((l) => ({
    source: l.source,
    target: l.target,
    value: l.weight,
    lineStyle: {
      width: Math.max(1, Math.round(l.weight * 0.5)),
      color: "#e5e5e5",
      curveness: 0,
      opacity: 0.8,
    },
  }));

  const option = {
    tooltip: {
      trigger: "item",
      formatter: (p: { data: { name: string; value?: number; isTarget?: boolean } }) => {
        if (!p.data?.name) return "";
        const count = p.data.value ?? 0;
        const sublabel = p.data.isTarget
          ? `Mentioned in <b>${count}</b> of 30 keywords`
          : `Co-mentioned in <b>${count}</b> keyword${count !== 1 ? "s" : ""} alongside Celonis`;
        return `<span style="font-family:${CHART_FONT};font-size:12px">
          <b>${p.data.name}</b><br/><span style="color:#767676;font-size:11px">${sublabel}</span>
        </span>`;
      },
      backgroundColor: "#fff",
      borderColor: "rgba(0,0,0,0.08)",
      borderWidth: 1,
      extraCssText: "box-shadow:0 2px 8px rgba(0,0,0,0.08);border-radius:8px;",
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
          repulsion: 180,
          gravity: 0.1,
          edgeLength: [30, 200],
          layoutAnimation: true,
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: { width: 3 },
        },
        lineStyle: { opacity: 0.6 },
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
