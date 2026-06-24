"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import SectionHeader from "@components/geo/SectionHeader";
import PageToolbar from "@components/geo/PageToolbar";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import CompanyChipFilter from "@components/news/CompanyChipFilter";
import NewsArticleCard from "@components/news/NewsArticleCard";
import { useNewsList } from "@/lib/news/hooks";
import { groupAndSortArticles } from "@/lib/news/groupArticles";
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

export default function NewsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selected = useMemo(
    () => parseCompanies(searchParams.get("companies")),
    [searchParams]
  );

  const { data, isLoading, isError, error } = useNewsList(selected);
  const { data: allData } = useNewsList([]);

  function handleFilterChange(next: string[]) {
    const params = new URLSearchParams(searchParams.toString());
    if (next.length > 0) {
      params.set("companies", next.join(","));
    } else {
      params.delete("companies");
    }
    router.push(`/news?${params.toString()}`);
  }

  const allOptions = useMemo(() => {
    if (!allData) return [];
    return allData.companies
      .map((c) => ({ domain: c.company, name: c.name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [allData]);

  const allDomains = useMemo(() => allOptions.map((o) => o.domain), [allOptions]);

  const mostRecentRunAt = useMemo(() => {
    if (!data || data.companies.length === 0) return undefined;
    return data.companies.reduce(
      (latest, c) =>
        new Date(c.run_at) > new Date(latest) ? c.run_at : latest,
      data.companies[0].run_at
    );
  }, [data]);

  return (
    <div className="w-full flex flex-col gap-12">
      {/* ============================================================== */}
      {/* Page header                                                    */}
      {/* ============================================================== */}
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

      {/* ============================================================== */}
      {/* Filter                                                         */}
      {/* ============================================================== */}
      <section>
        <CompanyChipFilter
          options={allOptions}
          selected={selected}
          onChange={handleFilterChange}
        />
      </section>

      {/* ============================================================== */}
      {/* Article grid, grouped by company → grouped by source           */}
      {/* ============================================================== */}
      <section className="flex flex-col gap-10">
        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <ZoneSkeleton height={280} />
            <ZoneSkeleton height={280} />
            <ZoneSkeleton height={280} />
          </div>
        )}

        {isError && <ZoneError message={error?.message} />}

        {!isLoading && !isError && data && data.companies.length === 0 && (
          <ZoneEmpty message="No news available for the selected companies." />
        )}

        {!isLoading &&
          !isError &&
          data &&
          [...data.companies]
            .sort((a, b) => {
              if (selected.length === 0) {
                return a.name.localeCompare(b.name);
              }
              const aIndex = selected.indexOf(a.company);
              const bIndex = selected.indexOf(b.company);
              return aIndex - bIndex;
            })
            .map((companyNews) => (
              <div key={companyNews.company} className="flex flex-col gap-6">
                <SectionHeader
                  label={companyNews.name}
                  description={`${companyNews.article_count} articles · updated ${formatRelativeTime(
                    companyNews.run_at
                  )}`}
                />

                {companyNews.articles.length === 0 ? (
                  <ZoneEmpty message="No articles found." />
                ) : (
                  groupAndSortArticles(companyNews.articles).map((group) => (
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
                  ))
                )}
              </div>
            ))}
      </section>
    </div>
  );
}