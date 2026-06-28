/**
 * Pure aggregation + filter helpers for the SoV dashboard.
 *
 * Functions are framework-agnostic — they take primitives in and return
 * primitives out. Components wrap them in `useMemo` to derive view data.
 */

import type { SovFilters, SovMention, SovPeriod } from "./types";

// ---------------------------------------------------------------------------
// Period handling
// ---------------------------------------------------------------------------

/**
 * Returns a cutoff Date — only mentions whose `date` is on or after this point
 * pass the period filter. `null` means "no cutoff" (period = "all").
 */
export function periodCutoff(period: SovPeriod, now: Date = new Date()): Date | null {
  switch (period) {
    case "1m":
      return new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
    case "3m":
      return new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
    case "6m":
      return new Date(now.getFullYear(), now.getMonth() - 6, now.getDate());
    case "ytd":
      return new Date(now.getFullYear(), 0, 1);
    case "all":
      return null;
  }
}

// ---------------------------------------------------------------------------
// Main filter
// ---------------------------------------------------------------------------

/**
 * Apply the global filter state to the raw mentions list.
 *
 * Empty `themes` / `regions` arrays mean "all" — they do not filter.
 * Source filter "both" likewise does not filter.
 */
export function applyFilters(mentions: SovMention[], filters: SovFilters): SovMention[] {
  const cutoff = periodCutoff(filters.period);
  const themeSet = new Set(filters.themes);
  const regionSet = new Set(filters.regions);

  return mentions.filter((m) => {
    // Period
    if (cutoff) {
      const d = new Date(m.date);
      if (Number.isNaN(d.getTime()) || d < cutoff) return false;
    }

    // Source
    if (filters.source !== "both" && m.source_type !== filters.source) {
      return false;
    }

    // Themes — at least one of the mention's themes must be selected
    if (themeSet.size > 0 && !m.themes.some((t) => themeSet.has(t))) {
      return false;
    }

    // Regions
    if (regionSet.size > 0 && (!m.region || !regionSet.has(m.region))) {
      return false;
    }

    return true;
  });
}

// ---------------------------------------------------------------------------
// Filter-active helper (used to decide whether to show "Clear filters ×")
// ---------------------------------------------------------------------------

export function hasActiveFilter(filters: SovFilters): boolean {
  return (
    filters.period !== "3m" ||
    filters.themes.length > 0 ||
    filters.regions.length > 0 ||
    filters.source !== "news"
  );
}

// ---------------------------------------------------------------------------
// Aggregations
// ---------------------------------------------------------------------------

export type CompanyShare = {
  company: string;
  count: number;
  share: number; // 0..1
};

/**
 * Group mentions by company, sorted by count desc. `share` is the fraction
 * of the *given* mentions list — so it already reflects active filters.
 */
export function aggregateByCompany(mentions: SovMention[]): CompanyShare[] {
  const counts = new Map<string, number>();
  for (const m of mentions) {
    counts.set(m.company, (counts.get(m.company) ?? 0) + 1);
  }
  const total = mentions.length;
  return Array.from(counts.entries())
    .map(([company, count]) => ({
      company,
      count,
      share: total > 0 ? count / total : 0,
    }))
    .sort((a, b) => b.count - a.count);
}

export type ThemeCount = {
  theme: string;
  count: number;
};

/**
 * Count how often each theme appears across all mentions. A mention with
 * multiple themes contributes to each of them.
 */
export function aggregateByTheme(mentions: SovMention[]): ThemeCount[] {
  const counts = new Map<string, number>();
  for (const m of mentions) {
    for (const theme of m.themes) {
      counts.set(theme, (counts.get(theme) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .map(([theme, count]) => ({ theme, count }))
    .sort((a, b) => b.count - a.count);
}

// ---------------------------------------------------------------------------
// Time series — mentions per month per company
// ---------------------------------------------------------------------------

export type MonthRow = {
  month: string; // YYYY-MM
} & Record<string, number | string>;

/**
 * Build a wide-format row per month: {month, [company1]: count, [company2]: count, ...}.
 * Months are filled contiguously between the earliest and latest seen — so the
 * line chart has no gaps. Companies missing in a given month default to 0.
 */
export function aggregateByMonth(
  mentions: SovMention[],
  allCompanies: string[],
): MonthRow[] {
  if (mentions.length === 0) return [];

  // Bucket counts: month -> company -> count
  const buckets = new Map<string, Map<string, number>>();
  for (const m of mentions) {
    const month = m.month_bucket;
    if (!month) continue;
    if (!buckets.has(month)) buckets.set(month, new Map());
    const inner = buckets.get(month)!;
    inner.set(m.company, (inner.get(m.company) ?? 0) + 1);
  }

  const months = Array.from(buckets.keys()).sort();
  if (months.length === 0) return [];

  // Fill gaps so the line chart is continuous
  const filled = fillMonthRange(months[0], months[months.length - 1]);

  return filled.map((month) => {
    const inner = buckets.get(month) ?? new Map<string, number>();
    const row: MonthRow = { month };
    for (const company of allCompanies) {
      row[company] = inner.get(company) ?? 0;
    }
    return row;
  });
}

/** Inclusive month range "YYYY-MM" → list of YYYY-MM strings, no gaps. */
function fillMonthRange(start: string, end: string): string[] {
  const [sy, sm] = start.split("-").map(Number);
  const [ey, em] = end.split("-").map(Number);
  const out: string[] = [];
  let y = sy;
  let m = sm;
  while (y < ey || (y === ey && m <= em)) {
    out.push(`${y}-${String(m).padStart(2, "0")}`);
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Themes × Companies (stacked horizontal bar)
// ---------------------------------------------------------------------------

export type ThemeRow = {
  theme: string;
  total: number;
} & Record<string, number | string>;

/**
 * One row per theme, with counts per company as keys.
 * Sorted by total desc so the dominant theme is on top.
 */
export function aggregateThemeByCompany(
  mentions: SovMention[],
  allCompanies: string[],
): ThemeRow[] {
  const byTheme = new Map<string, Map<string, number>>();
  for (const m of mentions) {
    for (const theme of m.themes) {
      if (!byTheme.has(theme)) byTheme.set(theme, new Map());
      const inner = byTheme.get(theme)!;
      inner.set(m.company, (inner.get(m.company) ?? 0) + 1);
    }
  }
  return Array.from(byTheme.entries())
    .map(([theme, inner]) => {
      const row: ThemeRow = { theme, total: 0 };
      let total = 0;
      for (const company of allCompanies) {
        const c = inner.get(company) ?? 0;
        row[company] = c;
        total += c;
      }
      row.total = total;
      return row;
    })
    .sort((a, b) => b.total - a.total);
}

// ---------------------------------------------------------------------------
// Regions
// ---------------------------------------------------------------------------

export type RegionCount = {
  region: string;
  count: number;
};

/**
 * Mentions per region. Mentions with `region == null` are bucketed as "Unknown".
 */
export function aggregateByRegion(mentions: SovMention[]): RegionCount[] {
  const counts = new Map<string, number>();
  for (const m of mentions) {
    const r = m.region ?? "Unknown";
    counts.set(r, (counts.get(r) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([region, count]) => ({ region, count }))
    .sort((a, b) => b.count - a.count);
}

// ---------------------------------------------------------------------------
// Rising / Declining themes — month-over-month momentum
// ---------------------------------------------------------------------------

export type ThemeMomentum = {
  theme: string;
  current: number;  // mentions in latest month
  previous: number; // mentions in the month before
  delta: number;    // current - previous
  pctChange: number; // (current - previous) / max(previous, 1) * 100
};

/**
 * Compare the latest month against the month before it.
 *
 * Returns `null` when there are fewer than two months of data — momentum
 * needs at least one prior period to compare against.
 *
 * Sorting strategy: by absolute delta first (real volume swings dominate),
 * with the pct change as a tiebreaker / display value.
 */
export function computeThemeMomentum(mentions: SovMention[]): {
  rising: ThemeMomentum[];
  declining: ThemeMomentum[];
} | null {
  if (mentions.length === 0) return null;

  const monthSet = new Set<string>();
  for (const m of mentions) {
    if (m.month_bucket) monthSet.add(m.month_bucket);
  }
  const months = Array.from(monthSet).sort();
  if (months.length < 2) return null;

  const currentMonth = months[months.length - 1];
  const previousMonth = months[months.length - 2];

  const currentCounts = new Map<string, number>();
  const previousCounts = new Map<string, number>();
  for (const m of mentions) {
    if (m.month_bucket === currentMonth) {
      for (const t of m.themes) currentCounts.set(t, (currentCounts.get(t) ?? 0) + 1);
    } else if (m.month_bucket === previousMonth) {
      for (const t of m.themes) previousCounts.set(t, (previousCounts.get(t) ?? 0) + 1);
    }
  }

  const themes = new Set([...currentCounts.keys(), ...previousCounts.keys()]);
  const momentum: ThemeMomentum[] = Array.from(themes).map((theme) => {
    const current = currentCounts.get(theme) ?? 0;
    const previous = previousCounts.get(theme) ?? 0;
    return {
      theme,
      current,
      previous,
      delta: current - previous,
      pctChange: previous > 0 ? ((current - previous) / previous) * 100 : current > 0 ? 100 : 0,
    };
  });

  const rising = momentum
    .filter((t) => t.delta > 0)
    .sort((a, b) => b.delta - a.delta)
    .slice(0, 3);

  const declining = momentum
    .filter((t) => t.delta < 0)
    .sort((a, b) => a.delta - b.delta)
    .slice(0, 3);

  return { rising, declining };
}
