"use client";

import { useMemo, useState } from "react";
import { ExternalLink, Calendar } from "lucide-react";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneEmpty } from "@components/geo/ZoneState";
import { getCompetitorColor } from "@/lib/competitors/colors";
import type { SovMention } from "@/lib/sov/types";

const SOURCE_LABELS: Record<string, string> = {
  finnhub: "Financial news",
  google_serp: "Web search",
  serper: "Media coverage",
};

const PAGE_SIZE = 12;

type Props = {
  mentions: SovMention[];
  allCompanies: string[];
  brandColors: Record<string, string>;
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function SovMentionList({ mentions, allCompanies, brandColors }: Props) {
  const sorted = useMemo(
    () => [...mentions].sort((a, b) => (b.date ?? "").localeCompare(a.date ?? "")),
    [mentions],
  );

  const [visible, setVisible] = useState(PAGE_SIZE);

  if (sorted.length === 0) {
    return <ZoneEmpty message="No mentions match the current filters." />;
  }

  const shown = sorted.slice(0, visible);
  const remaining = sorted.length - visible;

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {shown.map((m) => (
          <SovMentionCard
            key={m.id}
            mention={m}
            allCompanies={allCompanies}
            brandColors={brandColors}
          />
        ))}
      </div>

      {remaining > 0 && (
        <button
          type="button"
          onClick={() => setVisible((v) => v + PAGE_SIZE)}
          className="self-center text-xs text-neutral-grey-20 hover:text-primary-white transition-colors px-4 py-2 border border-neutral-grey-30 rounded-sm cursor-pointer"
        >
          Show more ({remaining} remaining)
        </button>
      )}
    </div>
  );
}

function SovMentionCard({
  mention,
  allCompanies,
  brandColors,
}: {
  mention: SovMention;
  allCompanies: string[];
  brandColors: Record<string, string>;
}) {
  const color = getCompetitorColor(mention.company, allCompanies, brandColors);
  const sourceLabel = SOURCE_LABELS[mention.source] ?? mention.source;

  return (
    <DashboardCard className="flex flex-col gap-3 h-full">
      {/* Top row: company badge + source + date */}
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[10px] tracking-widest uppercase font-medium px-2 py-0.5 rounded-sm"
            style={{ backgroundColor: `${color}26`, color }}
          >
            {mention.company}
          </span>
          <span className="text-[10px] tracking-widest uppercase font-medium text-neutral-grey-20 px-2 py-0.5 rounded-sm bg-white/5">
            {sourceLabel}
          </span>
          <span className="text-[10px] tracking-widest uppercase font-medium text-neutral-grey-20 px-2 py-0.5 rounded-sm bg-white/5">
            {mention.source_type}
          </span>
        </div>
        <div className="flex items-center gap-1 text-[11px] text-neutral-grey-20 shrink-0">
          <Calendar size={11} />
          <span>{formatDate(mention.date)}</span>
        </div>
      </div>

      {/* Title */}
      <h3 className="text-sm font-medium text-primary-white leading-snug line-clamp-3">
        {mention.title || "Untitled mention"}
      </h3>

      {/* Themes + region */}
      <div className="flex flex-wrap gap-1.5 mt-auto">
        {mention.themes.map((theme) => (
          <span
            key={theme}
            className="text-[10px] px-2 py-0.5 rounded-sm border border-white/10 text-neutral-grey-10"
          >
            {theme}
          </span>
        ))}
        {mention.region && (
          <span className="text-[10px] px-2 py-0.5 rounded-sm border border-secondary-green/40 text-secondary-green">
            {mention.region}
          </span>
        )}
      </div>

      {/* Link */}
      {mention.url && (
        <div className="pt-3 border-t border-white/8">
          <a
            href={mention.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-secondary-green hover:opacity-80 transition-opacity font-medium"
          >
            Read mention <ExternalLink size={11} />
          </a>
        </div>
      )}
    </DashboardCard>
  );
}
