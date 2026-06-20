"use client";

import dynamic from "next/dynamic";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useImagerySimilarity } from "@/lib/branding/hooks";
import { isHomeCompany } from "@/lib/competitors/highlight";

// ECharts must be imported client-side only (uses window)
const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

const CHART_FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif";
const MIN_SIMILARITY_TO_SHOW = 0.3;

export function ImagerySimilarityNetwork() {
  const { data, isLoading, isError, error } = useImagerySimilarity();

  if (isLoading) return <ZoneSkeleton height={360} />;
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.nodes.length === 0) {
    return <ZoneEmpty message="No imagery similarity analysis available yet." />;
  }

  const maxImages = Math.max(1, ...data.nodes.map((n) => n.imageCount));
  const links = data.links.filter((l) => l.similarity >= MIN_SIMILARITY_TO_SHOW);

  const echartsNodes = data.nodes.map((n) => {
    const home = isHomeCompany(n.company);
    return {
      id: n.company,
      name: n.company,
      value: n.imageCount,
      symbolSize: home ? 40 : Math.max(16, Math.round(16 + (n.imageCount / maxImages) * 24)),
      itemStyle: {
        color: home ? "#5CFE50" : "#CBCBCB",
        borderColor: home ? "#16a34a" : "#ffffff",
        borderWidth: 2,
      },
      isHome: home,
      label: {
        show: true,
        color: "#1D1D1D",
        fontSize: 11,
        fontFamily: CHART_FONT,
        fontWeight: home ? 600 : 400,
      },
    };
  });

  const echartsLinks = links.map((l) => ({
    source: l.source,
    target: l.target,
    value: l.similarity,
    lineStyle: {
      width: Math.max(1, Math.round(l.similarity * 5)),
      color: "#5CFE50",
      opacity: Math.max(0.25, l.similarity),
      curveness: 0,
    },
  }));

  const option = {
    tooltip: {
      trigger: "item",
      formatter: (p: {
        dataType?: string;
        data: { name?: string; value?: number; source?: string; target?: string };
      }) => {
        if (p.dataType === "edge") {
          const pct = Math.round((p.data.value ?? 0) * 100);
          return `<span style="font-family:${CHART_FONT};font-size:12px">
            <b>${p.data.source}</b> ↔ <b>${p.data.target}</b><br/>
            <span style="color:#767676;font-size:11px">${pct}% imagery similarity</span>
          </span>`;
        }
        return `<span style="font-family:${CHART_FONT};font-size:12px">
          <b>${p.data.name}</b><br/>
          <span style="color:#767676;font-size:11px">${p.data.value ?? 0} images analyzed</span>
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
        roam: false,
        draggable: true,
        force: {
          repulsion: 220,
          gravity: 0.1,
          edgeLength: [50, 220],
          layoutAnimation: true,
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: { width: 4 },
        },
        lineStyle: { opacity: 0.6 },
      },
    ],
  };

  return (
    <DashboardCard
      label="Imagery Similarity"
      sublabel="Competitors whose imagery style (across style, effect, subject, look & feel, color scheme) clusters together"
    >
      <ReactECharts option={option} style={{ width: "100%", height: 320 }} opts={{ renderer: "svg" }} />
      <div className="flex items-center gap-5 text-[11px] text-neutral-grey-20 mt-2" style={{ fontFamily: CHART_FONT }}>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-secondary-green border-2 border-green-600 shrink-0" />
          <span>Celonis</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-neutral-grey-10 shrink-0" />
          <span>Competitors</span>
        </div>
        <span className="ml-auto text-neutral-grey-10">
          Node size = images analyzed · edge thickness = similarity · drag nodes to rearrange
        </span>
      </div>
    </DashboardCard>
  );
}
