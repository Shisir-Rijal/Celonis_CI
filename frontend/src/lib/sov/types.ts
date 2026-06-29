/**
 * TypeScript types mirroring the SoV backend payload from
 * `app/api/sov.py` (SovMention / SovListResponse).
 *
 * The dashboard fetches the full list once and aggregates / filters
 * client-side. Filter state lives on the page and is passed down to
 * visualization components as already-filtered data.
 */

// ---------------------------------------------------------------------------
// Backend payload shape
// ---------------------------------------------------------------------------

export type SovSourceType = "news" | "seo";

export type SovRegion = "DACH" | "Europe" | "NA" | "APAC" | "Global";

export type SovMention = {
  id: string;
  run_at: string;          // ISO timestamp
  company: string;         // domain, e.g. "celonis.com"
  source_type: SovSourceType;
  source: string;          // e.g. "finnhub", "google_serp"
  title: string;
  content: string | null;
  date: string;            // YYYY-MM-DD
  month_bucket: string;    // YYYY-MM
  url: string;
  language: string | null;
  themes: string[];        // values from THEMES taxonomy
  region: SovRegion | null;
  is_relevant: boolean;
  reasoning: string | null;
};

export type SovListResponse = {
  mentions: SovMention[];
  total: number;
  latest_run_at: string | null;
  companies: string[];     // distinct, sorted
};

// ---------------------------------------------------------------------------
// Filter state (used by SovFilters + analysis.ts in later phases)
// ---------------------------------------------------------------------------

export type SovPeriod = "1m" | "3m" | "6m" | "ytd" | "all";

export type SovSourceFilter = "news" | "seo" | "both";

export type SovFilters = {
  period: SovPeriod;
  themes: string[];        // empty = all
  regions: SovRegion[];    // empty = all
  source: SovSourceFilter;
};

export const DEFAULT_SOV_FILTERS: SovFilters = {
  period: "3m",
  themes: [],
  regions: [],
  source: "news",          // News-only by default — see plan §9
};
