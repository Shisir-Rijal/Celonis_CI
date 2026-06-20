"use client";

import { ExternalLink, Calendar, User } from "lucide-react";

import DashboardCard from "@components/brand/DashboardCard";
import type { NewsArticle } from "@/lib/news/types";
import { getCompetitorColor } from "@/lib/competitors/colors";
import { useCompetitorColors } from "@/lib/competitors/hooks";

const SOURCE_LABELS: Record<string, string> = {
  firecrawl: "Official",
  finnhub: "Financial News",
  serper: "Media Coverage",
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr; // relative strings like "2 days ago" pass through
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

type NewsArticleCardProps = {
  article: NewsArticle;
  company: string;
  companyName: string;
  allCompanies: string[];
};

export default function NewsArticleCard({
  article,
  company,
  companyName,
  allCompanies,
}: NewsArticleCardProps) {
  const { data: brandColors = {} } = useCompetitorColors();
  const color = getCompetitorColor(company, allCompanies, brandColors);
  const title = article.heading ?? article.title ?? "Untitled article";
  const body = article.text ?? article.summary ?? "";

  return (
    <DashboardCard className="flex flex-col gap-4 h-full">
      {/* Company badge + source type */}
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[10px] tracking-widest uppercase font-medium px-2 py-0.5 rounded-sm"
            style={{ backgroundColor: `${color}26`, color }}
          >
            {companyName}
          </span>
          {article.source_type && (
            <span className="text-[10px] tracking-widest uppercase font-medium text-neutral-grey-20 px-2 py-0.5 rounded-sm bg-white/5">
              {SOURCE_LABELS[article.source_type] ?? article.source_type}
            </span>
          )}
        </div>
        {article.published_date && (
          <div className="flex items-center gap-1 text-[11px] text-neutral-grey-20 shrink-0">
            <Calendar size={11} />
            <span>{formatDate(article.published_date)}</span>
          </div>
        )}
      </div>

      {/* Title */}
      <h3 className="text-base font-medium text-primary-white leading-snug">
        {title}
      </h3>

      {/* Author */}
      {article.author && (
        <div className="flex items-center gap-1 text-xs text-neutral-grey-20">
          <User size={11} className="shrink-0" />
          {article.author}
        </div>
      )}

      {/* Body */}
      {body && (
        <p className="text-xs text-neutral-grey-10 leading-relaxed line-clamp-3 flex-1">
          {body}
        </p>
      )}

      {/* Source link */}
      {article.url && (
        <div className="mt-auto pt-3 border-t border-white/8">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-secondary-green hover:opacity-80 transition-opacity font-medium"
          >
            Read article <ExternalLink size={11} />
          </a>
        </div>
      )}
    </DashboardCard>
  );
}