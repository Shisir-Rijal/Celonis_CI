"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, Suspense } from "react";

import SectionHeader from "@components/geo/SectionHeader";
import PageToolbar from "@components/geo/PageToolbar";
import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import NewsFilters, { DateRange, SourceType } from "@components/news/NewsFilters";
import NewsArticleCard from "@components/news/NewsArticleCard";
import NewsActivityChart from "@components/news/charts/NewsActivityChart";
import NewsTrendChart from "@components/news/charts/NewsTrendChart";
import { useNewsList } from "@/lib/news/hooks";
import { groupAndSortArticles } from "@/lib/news/groupArticles";
import { useCompetitorColors } from "@/lib/competitors/hooks";
import type { NewsArticle } from "@/lib/news/types";
import ExportButton from "@components/report/ExportButton";

function parseCompanies(param: string | null): string[] {
  if (!param) return [];
  return param.split(",").filter(Boolean);
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

const RELATIVE_UNIT_MS: Record<string, number> = {
  hour: 60 * 60 * 1000,
  hours: 60 * 60 * 1000,
  day: 24 * 60 * 60 * 1000,
  days: 24 * 60 * 60 * 1000,
  week: 7 * 24 * 60 * 60 * 1000,
  weeks: 7 * 24 * 60 * 60 * 1000,
  month: 30 * 24 * 60 * 60 * 1000,
  months: 30 * 24 * 60 * 60 * 1000,
};

function parseDateToMs(dateStr: string | null): number {
  if (!dateStr) return 0;
  const parsed = new Date(dateStr);
  if (!isNaN(parsed.getTime())) return parsed.getTime();
  const match = dateStr.match(/(\d+)\s+(hour|hours|day|days|week|weeks|month|months)\s+ago/i);
  if (match) {
    const amount = parseInt(match[1], 10);
    const unit = match[2].toLowerCase();
    return Date.now() - amount * (RELATIVE_UNIT_MS[unit] ?? 0);
  }
  return 0;
}

function getDateRangeCutoff(dateRange: DateRange): number {
  const now = Date.now();
  switch (dateRange) {
    case "7d": return now - 7 * 24 * 60 * 60 * 1000;
    case "30d": return now - 30 * 24 * 60 * 60 * 1000;
    case "3m": return now - 90 * 24 * 60 * 60 * 1000;
    default: return 0;
  }
}

function filterArticles(
  articles: NewsArticle[],
  dateRange: DateRange,
  source: SourceType,
  topic: string,
): NewsArticle[] {
  const cutoff = getDateRangeCutoff(dateRange);
  return articles.filter((a) => {
    if (source !== "all" && a.source_type !== source) return false;
    if (cutoff > 0 && parseDateToMs(a.published_date) < cutoff) return false;
    if (topic !== "all" && !(a.topic ?? []).includes(topic)) return false;
    return true;
  });
}

function NewsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: brandColors = {} } = useCompetitorColors();

  const selected = useMemo(
    () => parseCompanies(searchParams.get("companies")),
    [searchParams]
  );

  const dateRange = (searchParams.get("dateRange") ?? "all") as DateRange;
  const selectedSource = (searchParams.get("source") ?? "all") as SourceType;
  const selectedTopic = searchParams.get("topic") ?? "all";

  const { data: allData, isLoading, isError, error } = useNewsList([]);

  function updateParams(updates: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "all" || value === "") {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    }
    router.replace(`/news?${params.toString()}`, { scroll: false });
  }

  function handleCompaniesChange(next: string[]) {
    updateParams({ companies: next.join(",") || null });
  }

  function handleDateRangeChange(next: DateRange) {
    updateParams({ dateRange: next });
  }

  function handleSourceChange(next: SourceType) {
    updateParams({ source: next });
  }

  function handleTopicChange(next: string) {
    updateParams({ topic: next });
  }

  const allOptions = useMemo(() => {
    if (!allData) return [];
    return allData.companies
      .map((c) => ({ domain: c.company, name: c.name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [allData]);

  const allDomains = useMemo(() => allOptions.map((o) => o.domain), [allOptions]);

  const visibleCompanies = useMemo(() => {
    if (!allData) return [];
    return allData.companies.filter(
      (c) => selected.length === 0 || selected.includes(c.company)
    );
  }, [allData, selected]);

  const mostRecentRunAt = useMemo(() => {
    if (visibleCompanies.length === 0) return undefined;
    return visibleCompanies.reduce((latest, c) =>
      new Date(c.run_at) > new Date(latest) ? c.run_at : latest,
      visibleCompanies[0].run_at
    );
  }, [visibleCompanies]);

  const activityData = useMemo(() => {
    if (!allData) return [];
    return allData.companies.map((c) => ({
      company: c.company,
      name: c.name,
      articles: c.articles,
    }));
  }, [allData]);

  const trendCompanies = useMemo(() => {
    if (!allData) return [];
    return allData.companies.map((c) => ({
      company: c.company,
      name: c.name,
      articles: c.articles,
    }));
  }, [allData]);

  const availableTopics = useMemo(() => {
    if (!allData) return [];
    const topicSet = new Set<string>();
    for (const company of allData.companies) {
      for (const article of company.articles) {
        for (const t of article.topic ?? []) {
          if (t && t !== "news") topicSet.add(t);
        }
      }
    }
    return [...topicSet].sort();
  }, [allData]);

  return (
    <div className="w-full flex flex-col gap-12">
      {/* Page header */}
      <header className="flex items-end justify-between gap-6 pb-6 border-b border-neutral-grey-30">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] tracking-[0.18em] uppercase text-neutral-grey-20 font-medium">
            News Intelligence
          </span>
          <h1 className="text-3xl font-medium text-primary-white leading-none">
            Competitor News
          </h1>
          <p className="mt-2 text-sm text-neutral-grey-20 max-w-xl">
            Latest articles and press coverage across tracked competitors.
          </p>
        </div>
        <PageToolbar
          runtime="Daily"
          updatedAt={formatRelativeTime(mostRecentRunAt)}
        />
      </header>

      {/* Insight charts */}
      {!isLoading && !isError && allData && (
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
          <DashboardCard
            label="Activity Overview"
            sublabel="Total articles per competitor"
            className="flex flex-col"
          >
            <div className="flex-1">
              <NewsActivityChart
                data={activityData}
                allCompanies={allDomains}
                brandColors={brandColors}
              />
            </div>
          </DashboardCard>
          <DashboardCard
            label="News Frequency Trend"
            sublabel="Article volume per month across competitors"
            className="flex flex-col"
          >
            <div className="flex-1">
              <NewsTrendChart
                companies={trendCompanies}
                allCompanies={allDomains}
                brandColors={brandColors}
              />
            </div>
          </DashboardCard>
        </section>
      )}

      {/* Filters */}
      <section>
        <NewsFilters
          companyOptions={allOptions}
          selectedCompanies={selected}
          onCompaniesChange={handleCompaniesChange}
          dateRange={dateRange}
          onDateRangeChange={handleDateRangeChange}
          selectedSource={selectedSource}
          onSourceChange={handleSourceChange}
          availableTopics={availableTopics}
          selectedTopic={selectedTopic}
          onTopicChange={handleTopicChange}
        />
      </section>

      {/* Article grid */}
      <section className="flex flex-col gap-10">
        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <ZoneSkeleton height={280} />
            <ZoneSkeleton height={280} />
            <ZoneSkeleton height={280} />
          </div>
        )}

        {isError && <ZoneError message={error?.message} />}

        {!isLoading && !isError && visibleCompanies.length === 0 && (
          <ZoneEmpty message="No news available for the selected companies." />
        )}

        {!isLoading &&
          !isError &&
          [...visibleCompanies]
            .sort((a, b) => {
              if (selected.length === 0) return a.name.localeCompare(b.name);
              const aIndex = selected.indexOf(a.company);
              const bIndex = selected.indexOf(b.company);
              return aIndex - bIndex;
            })
            .map((companyNews) => {
              const filteredArticles = filterArticles(
                companyNews.articles,
                dateRange,
                selectedSource,
                selectedTopic,
              );

              if (filteredArticles.length === 0) return null;

              return (
                <div key={companyNews.company} className="flex flex-col gap-6">
                  <SectionHeader
                    label={companyNews.name}
                    description={`${filteredArticles.length} articles · updated ${formatRelativeTime(
                      companyNews.run_at
                    )}`}
                  />
                  {groupAndSortArticles(filteredArticles).map((group) => (
                    <div key={group.sourceType} className="flex flex-col gap-3">
                      <span className="text-[11px] tracking-widest uppercase font-medium text-neutral-grey-20">
                        {group.label}
                      </span>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {group.articles.map((article, idx) => (
                          <NewsArticleCard
                            key={`${companyNews.company}-${group.sourceType}-${idx}`}
                            article={article}
                            company={companyNews.company}
                            companyName={companyNews.name}
                            allCompanies={allDomains}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
      </section>
    </div>
  );
}

export default function NewsPage() {
  return (
    <Suspense>
      <NewsPageInner />
    </Suspense>
  );
}