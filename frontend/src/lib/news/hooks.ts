// frontend/lib/news/hooks.ts

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CompanyNews, NewsListResponse } from "./types";

const STALE_TIME = 5 * 60 * 1000;

export function useNewsList(companies: string[] = []) {
  const queryString =
    companies.length > 0
      ? "?" + companies.map((c) => `companies=${encodeURIComponent(c)}`).join("&")
      : "";

  return useQuery<NewsListResponse>({
    queryKey: ["news-list", ...companies.slice().sort()],
    queryFn: () => apiFetch<NewsListResponse>(`/news${queryString}`),
    staleTime: STALE_TIME,
  });
}

export function useCompanyNews(company: string) {
  return useQuery<CompanyNews>({
    queryKey: ["company-news", company],
    queryFn: () => apiFetch<CompanyNews>(`/news/${encodeURIComponent(company)}`),
    staleTime: STALE_TIME,
    enabled: Boolean(company),
  });
}