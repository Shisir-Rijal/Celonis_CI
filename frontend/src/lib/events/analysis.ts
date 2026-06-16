import type { EventItem } from "./types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ONLINE_KEYWORDS = [
  "online", "virtual", "remote", "webinar", "digital", "zoom", "livestream", "hybrid",
];

export function isOnlineEvent(location: string | null): boolean {
  if (!location) return false;
  const lower = location.toLowerCase();
  return ONLINE_KEYWORDS.some((kw) => lower.includes(kw));
}

const REGION_KEYWORDS: Array<{ region: string; keywords: string[] }> = [
  { region: "Europe", keywords: ["germany","uk","united kingdom","france","spain","italy","netherlands","sweden","norway","denmark","finland","belgium","austria","switzerland","poland","portugal","ireland","europe","london","berlin","paris","amsterdam","munich","münchen","frankfurt","vienna","wien","zurich","stockholm","copenhagen","oslo","helsinki","brussels","dublin","madrid","barcelona","rome","milan","warsaw","prague","budapest","lisbon","edinburgh"] },
  { region: "North America", keywords: ["usa","united states","canada","mexico","california","new york","texas","florida","san francisco","los angeles","chicago","boston","seattle","austin","houston","dallas","miami","atlanta","las vegas","denver","toronto","vancouver","montreal","mexico city"] },
  { region: "South America", keywords: ["brazil","argentina","chile","colombia","peru","são paulo","sao paulo","buenos aires","santiago","bogotá","bogota","lima","rio de janeiro"] },
  { region: "Asia Pacific", keywords: ["china","japan","india","australia","singapore","korea","indonesia","malaysia","thailand","vietnam","new zealand","hong kong","taiwan","tokyo","shanghai","beijing","sydney","seoul","mumbai","bangalore","bengaluru","jakarta","bangkok","kuala lumpur","taipei","auckland","delhi"] },
  { region: "Middle East & Africa", keywords: ["uae","saudi arabia","israel","turkey","egypt","south africa","nigeria","kenya","morocco","qatar","dubai","abu dhabi","tel aviv","riyadh","istanbul","cairo","johannesburg","lagos","nairobi","cape town"] },
];

export function locationToRegion(location: string | null): string {
  if (!location) return "Other";
  const lower = location.toLowerCase();
  for (const { region, keywords } of REGION_KEYWORDS) {
    if (keywords.some((kw) => lower.includes(kw))) return region;
  }
  return "Other";
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PerCompany = { company: string; count: number; isCelonis: boolean };
export type FormatRow  = { company: string; inPerson: number; online: number; isCelonis: boolean };

export type EventsAnalysis = {
  total: number;
  celonisCount: number;
  celonisShare: number;
  mostActiveCompetitor: { name: string; count: number } | null;
  perCompany: PerCompany[];
  formatMix: FormatRow[];
  coverageGap: { region: string; competitorEvents: number } | null;
  topicGap: { topic: string; celonisCount: number; otherCount: number } | null;
  momentum: {
    thisYear: number;
    lastYear: number;
    direction: "up" | "down" | "flat";
    pctChange: number;
  } | null;
};

// ---------------------------------------------------------------------------
// Computation
// ---------------------------------------------------------------------------

export function computeAnalysis(events: EventItem[], allCompanies: string[]): EventsAnalysis {
  const celonisName = allCompanies.find((c) => c.toLowerCase().includes("celonis")) ?? "";
  const isCelonis = (c: string) => c === celonisName;

  const total = events.length;
  const celonisEvents = events.filter((e) => isCelonis(e.company));
  const celonisCount = celonisEvents.length;
  const celonisShare = total > 0 ? (celonisCount / total) * 100 : 0;

  // Per-company counts
  const countMap: Record<string, number> = {};
  for (const e of events) countMap[e.company] = (countMap[e.company] ?? 0) + 1;
  const perCompany: PerCompany[] = Object.entries(countMap)
    .map(([company, count]) => ({ company, count, isCelonis: isCelonis(company) }))
    .sort((a, b) => b.count - a.count);

  const mostActiveCompetitor = perCompany.find((c) => !c.isCelonis) ?? null;

  // Format mix
  const fmtMap: Record<string, { online: number; inPerson: number }> = {};
  for (const e of events) {
    if (!fmtMap[e.company]) fmtMap[e.company] = { online: 0, inPerson: 0 };
    if (isOnlineEvent(e.location)) fmtMap[e.company].online++;
    else fmtMap[e.company].inPerson++;
  }
  const formatMix: FormatRow[] = perCompany.map((c) => ({
    company: c.company,
    inPerson: fmtMap[c.company]?.inPerson ?? 0,
    online:   fmtMap[c.company]?.online   ?? 0,
    isCelonis: c.isCelonis,
  }));

  // Coverage gap
  const celonisRegions = new Set(
    celonisEvents
      .filter((e) => !isOnlineEvent(e.location))
      .map((e) => locationToRegion(e.location))
  );
  const gapMap: Record<string, number> = {};
  for (const e of events) {
    if (isCelonis(e.company) || isOnlineEvent(e.location)) continue;
    const r = locationToRegion(e.location);
    if (r !== "Other" && !celonisRegions.has(r)) {
      gapMap[r] = (gapMap[r] ?? 0) + 1;
    }
  }
  const topGap = Object.entries(gapMap).sort(([, a], [, b]) => b - a)[0];
  const coverageGap = topGap ? { region: topGap[0], competitorEvents: topGap[1] } : null;

  // Topic gap
  const topicCelonis: Record<string, number> = {};
  const topicOther: Record<string, number> = {};
  for (const e of events) {
    if (!e.event_topic) continue;
    if (isCelonis(e.company)) topicCelonis[e.event_topic] = (topicCelonis[e.event_topic] ?? 0) + 1;
    else topicOther[e.event_topic] = (topicOther[e.event_topic] ?? 0) + 1;
  }
  let topicGap: EventsAnalysis["topicGap"] = null;
  let maxDelta = 0;
  for (const [topic, otherCount] of Object.entries(topicOther)) {
    const cel = topicCelonis[topic] ?? 0;
    if (otherCount - cel > maxDelta) {
      maxDelta = otherCount - cel;
      topicGap = { topic, celonisCount: cel, otherCount };
    }
  }

  // Momentum
  const thisYr = new Date().getFullYear();
  let thisYear = 0;
  let lastYear = 0;
  for (const e of celonisEvents) {
    if (!e.event_date) continue;
    const d = new Date(e.event_date);
    if (isNaN(d.getTime())) continue;
    if (d.getFullYear() === thisYr) thisYear++;
    if (d.getFullYear() === thisYr - 1) lastYear++;
  }
  const pctChange = lastYear > 0 ? Math.round(((thisYear - lastYear) / lastYear) * 100) : 0;
  const momentum: EventsAnalysis["momentum"] =
    celonisCount > 0
      ? { thisYear, lastYear, direction: pctChange > 0 ? "up" : pctChange < 0 ? "down" : "flat", pctChange }
      : null;

  return { total, celonisCount, celonisShare, mostActiveCompetitor, perCompany, formatMix, coverageGap, topicGap, momentum };
}