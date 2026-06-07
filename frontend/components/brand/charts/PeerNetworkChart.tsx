"use client";

import dynamic from "next/dynamic";
import type { PeerNetworkBlock } from "@/lib/brand/types";

// ---------------------------------------------------------------------------
// Types — extend Nivo's InputNode / InputLink with our custom fields
// ---------------------------------------------------------------------------

type NetworkNode = {
  id: string;
  is_target: boolean;
  weight: number;
};

type NetworkLink = {
  source: string;
  target: string;
  weight: number;
  distance: number;
};

// ---------------------------------------------------------------------------
// Dynamic import — Nivo uses browser APIs, cannot be SSR'd
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ResponsiveNetwork = dynamic<any>(
  () => import("@nivo/network").then((m) => m.ResponsiveNetwork),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-[320px] text-xs text-neutral-grey-20">
        Loading network…
      </div>
    ),
  }
);

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

function NodeTooltip({ node }: { node: { id: string; data: NetworkNode } }) {
  return (
    <div
      className="rounded-lg border border-black/8 bg-white px-3 py-2 shadow-md text-xs"
      style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
    >
      <span className="font-semibold text-primary-black">{node.id}</span>
      <span className="text-neutral-grey-20 ml-2">
        {node.data.weight} co-mention{node.data.weight !== 1 ? "s" : ""}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart
// ---------------------------------------------------------------------------

type PeerNetworkChartProps = {
  data: PeerNetworkBlock;
};

export default function PeerNetworkChart({ data }: PeerNetworkChartProps) {
  const { nodes, links, primary_peer_group } = data;

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

  const networkNodes: NetworkNode[] = nodes.map((n) => ({
    id: n.id,
    is_target: n.is_target,
    weight: n.weight,
  }));

  const networkLinks: NetworkLink[] = links.map((l) => ({
    source: l.source,
    target: l.target,
    weight: l.weight,
    distance: l.distance,
  }));

  const primarySet = new Set(primary_peer_group);

  return (
    <div>
      <div style={{ height: 320 }}>
        <ResponsiveNetwork
          nodes={networkNodes}
          links={networkLinks}
          repulsivity={8}
          distanceMin={1}
          distanceMax={300}
          iterations={80}
          animate={false}
          nodeSize={(node: { data: NetworkNode }) =>
            node.data.is_target ? 22 : Math.max(10, 8 + node.data.weight * 2)
          }
          activeNodeSize={(node: { data: NetworkNode }) =>
            node.data.is_target ? 26 : Math.max(12, 10 + node.data.weight * 2)
          }
          inactiveNodeSize={(node: { data: NetworkNode }) =>
            node.data.is_target ? 20 : Math.max(8, 6 + node.data.weight * 2)
          }
          nodeColor={(node: { data: NetworkNode }) => {
            if (node.data.is_target) return "#5CFE50";
            if (primarySet.has(node.data.id)) return "#3233F5";
            return "#CBCBCB";
          }}
          nodeBorderWidth={2}
          nodeBorderColor={(node: { data: NetworkNode }) =>
            node.data.is_target ? "#16a34a" : "#ffffff"
          }
          linkThickness={(link: { data: NetworkLink }) =>
            Math.max(1, link.data.weight * 0.8)
          }
          linkColor={{ from: "color", modifiers: [["opacity", 0.15]] }}
          nodeTooltip={NodeTooltip}
          theme={{
            tooltip: { container: { display: "none" } },
          }}
        />
      </div>

      {/* Legend */}
      <div
        className="mt-3 flex items-center gap-5 text-[11px] text-neutral-grey-20"
        style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
      >
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-secondary-green border-2 border-green-600" />
          <span>Celonis</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-secondary-blue" />
          <span>Primary peer group</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-neutral-grey-10" />
          <span>Other mentions</span>
        </div>
        <div className="ml-auto text-neutral-grey-10">
          Node size = co-mention frequency
        </div>
      </div>
    </div>
  );
}
