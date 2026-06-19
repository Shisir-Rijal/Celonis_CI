"use client";

import { useMemo, useState } from "react";

import DashboardCard from "@components/geo/DashboardCard";
import KpiTile from "@components/geo/KpiTile";
import SectionHeader from "@components/geo/SectionHeader";
import PageToolbar from "@components/geo/PageToolbar";
import AlertCard from "@components/geo/AlertCard";
import GeoTrendChart from "@components/geo/charts/GeoTrendChart";
import LlmComparisonChart from "@components/geo/charts/LlmComparisonChart";
import SovTierPanel from "@components/geo/charts/SovTierPanel";
import PeerNetworkChart from "@components/geo/charts/PeerNetworkChart";
import TerritoryHeatmap from "@components/geo/charts/TerritoryHeatmap";
import KeywordTable from "@components/geo/charts/KeywordTable";
import {
  ZoneEmpty,
  ZoneError,
  ZoneSkeleton,
} from "@components/geo/ZoneState";

import {
  useGeoDeepDive,
  useGeoIntelligence,
  useGeoShareOfVoice,
  useGeoStrategicMaps,
} from "@/lib/brand/hooks";

import type { DeepDiveResponse } from "@/lib/brand/types";

const DEFAULT_COMPANY = "celonis.com";

// ---------------------------------------------------------------------------
// Deep Dive Zone — extracted to keep the main component readable
// ---------------------------------------------------------------------------

function DeepDiveZone({ data }: { data: DeepDiveResponse }) {
  const [briefingOpen, setBriefingOpen] = useState(false);
  const { alerts, keyword_rows, full_briefing } = data;

  return (
    <div className="flex flex-col gap-4">
      {/* Alert cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {alerts.critical_gap ? (
          <AlertCard
            category="Critical Gap"
            text={alerts.critical_gap}
            priority="high"
            recommendation="Address this territory in the next messaging update."
          />
        ) : (
          <DashboardCard label="Critical Gap">
            <p className="text-sm text-neutral-grey-20">No critical gap identified.</p>
          </DashboardCard>
        )}

        {alerts.framing_gap ? (
          <AlertCard
            category="Framing Gap"
            text={alerts.framing_gap}
            priority="medium"
          />
        ) : (
          <DashboardCard label="Framing Gap">
            <p className="text-sm text-neutral-grey-20">No framing gap identified.</p>
          </DashboardCard>
        )}

        {alerts.counter_positioning ? (
          <AlertCard
            category="Counter-Positioning"
            text={alerts.counter_positioning}
            priority="medium"
            recommendation="Review messaging to address this criticism."
          />
        ) : (
          <DashboardCard label="Counter-Positioning">
            <p className="text-sm text-neutral-grey-20">No counter-positioning found.</p>
          </DashboardCard>
        )}
      </div>

      {/* Keyword table */}
      <DashboardCard
        label="Keyword performance"
        sublabel={`${keyword_rows.length} keywords · Click any row to see the AI response excerpt`}
      >
        <KeywordTable rows={keyword_rows} />
      </DashboardCard>

      {/* Full briefing — collapsible */}
      {full_briefing && (
        <DashboardCard
          label="Full strategic briefing"
          sublabel="Synthesised narrative across all keywords"
        >
          <button
            type="button"
            onClick={() => setBriefingOpen((o) => !o)}
            className="flex items-center gap-2 text-sm text-primary-black hover:text-secondary-green transition-colors font-medium cursor-pointer"
          >
            <span>{briefingOpen ? "▲" : "▼"}</span>
            <span>{briefingOpen ? "Collapse" : "Read full briefing"}</span>
          </button>
          {briefingOpen && (
            <div className="mt-4 pt-4 border-t border-black/5">
              <p
                className="text-sm text-primary-black leading-relaxed whitespace-pre-wrap"
                style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif" }}
              >
                {full_briefing}
              </p>
            </div>
          )}
        </DashboardCard>
      )}
    </div>
  );
}

function formatPct(value: number | undefined | null): string {
  if (value === undefined || value === null) return "—";
  return (value * 100).toFixed(1);
}

function formatScore(value: number | undefined | null): string {
  if (value === undefined || value === null) return "—";
  return value.toFixed(1);
}

function formatRelativeTime(iso: string | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const minutes = Math.floor((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  return `${days} d ago`;
}

export default function GeoIntelligencePage() {
  const company = DEFAULT_COMPANY;

  const intel = useGeoIntelligence(company);
  const sov = useGeoShareOfVoice(company);
  const maps = useGeoStrategicMaps(company);
  const deep = useGeoDeepDive(company);

  const kpis = intel.data?.kpis;
  const deltas = kpis?.deltas;

  const updatedAt = useMemo(
    () => formatRelativeTime(intel.data?.latest_run_at),
    [intel.data?.latest_run_at]
  );

  return (
    <div className="w-full flex flex-col gap-24">
      {/* ============================================================== */}
      {/* Page header                                                    */}
      {/* ============================================================== */}
      <header className="flex items-end justify-between gap-6 pb-6 border-b border-neutral-grey-30">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] tracking-[0.18em] uppercase text-neutral-grey-20 font-medium">
            GEO Intelligence
          </span>
          <h1 className="text-3xl font-medium text-primary-white leading-none">
            {company}
          </h1>
          <p className="mt-2 text-sm text-neutral-grey-20 max-w-xl">
            How AI assistants surface this brand across {" "}
            <span className="text-primary-white font-medium">30 keywords</span>{" "}
            spanning brand, use-case and competitor-trigger queries.
          </p>
        </div>
        <PageToolbar runtime="every month" updatedAt={updatedAt} agentsRunning={1} />
      </header>

      {/* ============================================================== */}
      {/* Zone 1 — KPI Tiles                                             */}
      {/* ============================================================== */}
      <section>
        <SectionHeader
          label="Visibility at a glance"
          description="Four headline metrics from the latest analysis run."
        />
        {intel.isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <ZoneSkeleton height={120} />
            <ZoneSkeleton height={120} />
            <ZoneSkeleton height={120} />
            <ZoneSkeleton height={120} />
          </div>
        ) : intel.isError ? (
          <ZoneError message={intel.error?.message} />
        ) : !kpis ? (
          <ZoneEmpty message="No pipeline runs yet for this company." />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <KpiTile
              label="AI Visibility"
              value={formatPct(kpis.visibility_pct)}
              suffix="%"
              subtitle="Keyword mention rate"
              delta={
                deltas?.visibility_pct !== null &&
                deltas?.visibility_pct !== undefined
                  ? {
                      value: Number((deltas.visibility_pct * 100).toFixed(1)),
                      label: "pp vs last run",
                    }
                  : null
              }
            />
            <KpiTile
              label="GEO Score"
              value={formatScore(kpis.geo_score)}
              subtitle="Composite AI search visibility"
              highlight
              delta={
                deltas?.geo_score !== null && deltas?.geo_score !== undefined
                  ? {
                      value: Number(deltas.geo_score.toFixed(1)),
                      label: "vs last run",
                    }
                  : null
              }
            />
            <KpiTile
              label="Active Recommendations"
              value={formatPct(kpis.active_recommendation_pct)}
              suffix="%"
              subtitle="Recommended or default placements"
              delta={
                deltas?.active_recommendation_pct !== null &&
                deltas?.active_recommendation_pct !== undefined
                  ? {
                      value: Number(
                        (deltas.active_recommendation_pct * 100).toFixed(1)
                      ),
                      label: "pp vs last run",
                    }
                  : null
              }
            />
            <KpiTile
              label="Territory Gaps"
              value={kpis.gap_count}
              subtitle="Keywords with no mention"
              delta={
                deltas?.gap_count !== null && deltas?.gap_count !== undefined
                  ? {
                      value: deltas.gap_count,
                      direction:
                        deltas.gap_count > 0
                          ? "down"
                          : deltas.gap_count < 0
                          ? "up"
                          : "flat",
                      label: "vs last run",
                    }
                  : null
              }
            />
          </div>
        )}
      </section>

      {/* ============================================================== */}
      {/* Zone 2 — Performance Trends                                    */}
      {/* ============================================================== */}
      <section>
        <SectionHeader
          label="Performance trends"
          description="Movement across runs, broken down by metric and by LLM."
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <DashboardCard
            label="GEO Visibility Trend"
            sublabel="Mention rate and GEO score per pipeline run"
          >
            {intel.isLoading ? (
              <ZoneSkeleton height={260} />
            ) : intel.isError ? (
              <ZoneError />
            ) : (
              <GeoTrendChart series={intel.data?.trends.series ?? []} />
            )}
          </DashboardCard>
          <DashboardCard
            label="LLM Comparison"
            sublabel="Mention rate per AI model in the latest run"
          >
            {intel.isLoading ? (
              <ZoneSkeleton height={260} />
            ) : intel.isError ? (
              <ZoneError />
            ) : (
              <LlmComparisonChart
                data={intel.data?.trends.llm_comparison ?? []}
              />
            )}
          </DashboardCard>
        </div>
      </section>

      {/* ============================================================== */}
      {/* Zone 3 — AI Share of Voice                                     */}
      {/* ============================================================== */}
      <section>
        <SectionHeader
          label="AI share of voice"
          description="Top companies surfaced alongside, split by keyword tier."
        />
        {sov.isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ZoneSkeleton height={220} />
            <ZoneSkeleton height={220} />
            <ZoneSkeleton height={220} />
          </div>
        ) : sov.isError ? (
          <ZoneError message={sov.error?.message} />
        ) : !sov.data?.tiers?.length ? (
          <ZoneEmpty message="No sightings yet for share of voice." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {sov.data.tiers.map((tier) => (
              <DashboardCard
                key={tier.tier}
                label={tier.label}
                sublabel={`Top co-mentioned companies · ${tier.total_keywords} keywords`}
              >
                <SovTierPanel tier={tier} />
              </DashboardCard>
            ))}
          </div>
        )}
      </section>

      {/* ============================================================== */}
      {/* Zone 4 — Strategic Maps                                        */}
      {/* ============================================================== */}
      <section>
        <SectionHeader
          label="Strategic maps"
          description="Which companies appear alongside us, and which use-case territories we own."
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <DashboardCard
            label="Competitive Set Map"
            sublabel="Co-mentioned companies · node size = frequency"
          >
            {maps.isLoading ? (
              <ZoneSkeleton height={320} />
            ) : maps.isError ? (
              <ZoneError />
            ) : maps.data?.peer_network ? (
              <PeerNetworkChart data={maps.data.peer_network} />
            ) : (
              <ZoneEmpty message="No co-mention data yet." />
            )}
          </DashboardCard>
          <DashboardCard
            label="Use-Case Territory Map"
            sublabel="Keyword tier × recommendation strength — darker = more keywords"
          >
            {maps.isLoading ? (
              <ZoneSkeleton height={320} />
            ) : maps.isError ? (
              <ZoneError />
            ) : maps.data?.territory_map ? (
              <TerritoryHeatmap data={maps.data.territory_map} />
            ) : (
              <ZoneEmpty message="No territory data yet." />
            )}
          </DashboardCard>
        </div>
      </section>

      {/* ============================================================== */}
      {/* Zone 5 — Deep Dive                                             */}
      {/* ============================================================== */}
      <section>
        <SectionHeader
          label="Deep dive"
          description="Strategic alerts and keyword-level evidence behind the headline numbers."
          action={
            <button
              type="button"
              className="text-xs tracking-[0.16em] uppercase font-medium text-primary-white hover:text-secondary-green transition-colors cursor-pointer"
            >
              Export →
            </button>
          }
        />

        {deep.isLoading ? (
          <ZoneSkeleton height={400} />
        ) : deep.isError ? (
          <ZoneError message={deep.error?.message} />
        ) : deep.data ? (
          <DeepDiveZone data={deep.data} />
        ) : (
          <ZoneEmpty message="No deep dive data yet." />
        )}
      </section>
    </div>
  );
}
