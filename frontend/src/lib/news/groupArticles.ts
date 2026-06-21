import type { NewsArticle } from "./types";

const SOURCE_LABELS: Record<string, string> = {
  firecrawl: "Official",
  finnhub: "Financial News",
  serper: "Media Coverage",
};

function getSourceLabel(sourceType: string): string {
  return SOURCE_LABELS[sourceType] ?? sourceType;
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

function parsePublishedDate(dateStr: string | null): number {
  if (!dateStr) return 0;

  const parsed = new Date(dateStr);
  if (!isNaN(parsed.getTime())) {
    return parsed.getTime();
  }

  const match = dateStr.match(/(\d+)\s+(hour|hours|day|days|week|weeks|month|months)\s+ago/i);
  if (match) {
    const amount = parseInt(match[1], 10);
    const unit = match[2].toLowerCase();
    const unitMs = RELATIVE_UNIT_MS[unit] ?? 0;
    return Date.now() - amount * unitMs;
  }

  return 0;
}

export type ArticleGroup = {
  sourceType: string;
  label: string;
  articles: NewsArticle[];
};

export function groupAndSortArticles(articles: NewsArticle[]): ArticleGroup[] {
  const groups = new Map<string, NewsArticle[]>();

  for (const article of articles) {
    const key = article.source_type ?? "other";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(article);
  }

  const result: ArticleGroup[] = [];
  for (const [sourceType, groupArticles] of groups) {
    const sorted = [...groupArticles].sort(
      (a, b) => parsePublishedDate(b.published_date) - parsePublishedDate(a.published_date)
    );
    result.push({ sourceType, label: getSourceLabel(sourceType), articles: sorted });
  }

  const SOURCE_PRIORITY: Record<string, number> = {
    firecrawl: 0, // Official — highest trust, always first
    finnhub: 1,   // Financial News
    serper: 2,    // Media Coverage
    };

  result.sort((a, b) => {
    const aPriority = SOURCE_PRIORITY[a.sourceType] ?? 99;
    const bPriority = SOURCE_PRIORITY[b.sourceType] ?? 99;
    return aPriority - bPriority;
    });

  return result;
}