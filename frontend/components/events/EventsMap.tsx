"use client";

import { useState, useMemo } from "react";
import dynamic from "next/dynamic";

import { useEvents } from "@/lib/events/hooks";
import { useCompetitorColors } from "@/lib/competitors/hooks";
import { getCompetitorColor } from "@/lib/competitors/colors";
import type { EventItem } from "@/lib/events/types";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/brand/ZoneState";
import DashboardCard from "@components/brand/DashboardCard";

// SSR-free Leaflet map
const EventsMapCore = dynamic(() => import("./EventsMapCore"), {
  ssr: false,
  loading: () => <ZoneSkeleton height={520} />,
});

// ---------------------------------------------------------------------------
// Region / mode helpers
// ---------------------------------------------------------------------------

const REGION_KEYWORDS: Array<{ region: string; keywords: string[] }> = [
  {
    region: "Online / Virtual",
    keywords: ["online", "virtual", "remote", "webinar", "digital", "zoom", "livestream", "hybrid"],
  },
  {
    region: "Europe",
    keywords: [
      "germany", "uk", "united kingdom", "england", "france", "spain", "italy",
      "netherlands", "sweden", "norway", "denmark", "finland", "belgium", "austria",
      "switzerland", "poland", "portugal", "czech", "hungary", "romania", "greece",
      "ireland", "scotland", "europe", "eu",
      "london", "berlin", "paris", "amsterdam", "munich", "münchen", "hamburg",
      "frankfurt", "vienna", "wien", "zurich", "zürich", "geneva", "stockholm",
      "copenhagen", "oslo", "helsinki", "brussels", "dublin", "madrid", "barcelona",
      "rome", "milan", "warsaw", "prague", "budapest", "lisbon", "athens", "edinburgh",
    ],
  },
  {
    region: "North America",
    keywords: [
      "usa", "united states", "canada", "mexico",
      "california", "new york", "texas", "florida", "illinois", "washington",
      "georgia", "massachusetts", "nevada", "colorado",
      "new york city", "nyc", "san francisco", "los angeles", "chicago", "boston",
      "seattle", "austin", "houston", "dallas", "miami", "atlanta", "las vegas",
      "denver", "toronto", "vancouver", "montreal", "mexico city", "san jose",
      "san diego", "phoenix", "portland", "salt lake city", "ottawa", "calgary",
    ],
  },
  {
    region: "South America",
    keywords: [
      "brazil", "argentina", "chile", "colombia", "peru", "venezuela",
      "uruguay", "ecuador", "bolivia",
      "são paulo", "sao paulo", "buenos aires", "santiago", "bogotá", "bogota",
      "lima", "rio de janeiro", "montevideo", "medellín",
    ],
  },
  {
    region: "Asia Pacific",
    keywords: [
      "china", "japan", "india", "australia", "singapore", "south korea", "korea",
      "indonesia", "malaysia", "thailand", "vietnam", "new zealand", "hong kong",
      "taiwan", "philippines",
      "tokyo", "shanghai", "beijing", "sydney", "seoul", "mumbai",
      "bangalore", "bengaluru", "jakarta", "bangkok", "kuala lumpur", "taipei",
      "auckland", "osaka", "delhi",
    ],
  },
  {
    region: "Middle East & Africa",
    keywords: [
      "uae", "united arab emirates", "saudi arabia", "israel", "turkey",
      "egypt", "south africa", "nigeria", "kenya", "ghana", "morocco",
      "qatar", "kuwait", "bahrain", "jordan",
      "dubai", "abu dhabi", "tel aviv", "riyadh", "istanbul", "cairo",
      "johannesburg", "lagos", "nairobi", "casablanca", "doha", "cape town",
    ],
  },
];

const REGION_ORDER = [
  "Online / Virtual",
  "Europe",
  "North America",
  "South America",
  "Asia Pacific",
  "Middle East & Africa",
  "Other",
];

function locationToRegion(location: string | null): string {
  if (!location) return "Other";
  const lower = location.toLowerCase();
  for (const { region, keywords } of REGION_KEYWORDS) {
    if (keywords.some((kw) => lower.includes(kw))) return region;
  }
  return "Other";
}

// ---------------------------------------------------------------------------
// Filter helpers
// ---------------------------------------------------------------------------

const MAP_PERIOD_OPTIONS = [
  { value: "month", label: "This month" },
  { value: "year",  label: "This year"  },
  { value: "all",   label: "All time"   },
] as const;
type MapPeriod = typeof MAP_PERIOD_OPTIONS[number]["value"];

const SIZE_OPTIONS = [
  { value: "all",    label: "All sizes"   },
  { value: "small",  label: "Small (<100)" },
  { value: "medium", label: "Mid (100–999)" },
  { value: "large",  label: "Large (1000+)" },
] as const;
type EventSize = typeof SIZE_OPTIONS[number]["value"];

const MODE_OPTIONS = [
  { value: "all",       label: "Online & in-person" },
  { value: "online",    label: "Online only"         },
  { value: "in-person", label: "In-person only"      },
] as const;
type EventMode = typeof MODE_OPTIONS[number]["value"];

function matchesPeriod(e: EventItem, period: MapPeriod): boolean {
  if (period === "all") return true;
  const raw = e.event_date;
  if (!raw) return false;
  const d = new Date(raw);
  if (isNaN(d.getTime())) return false;
  const now = new Date();
  if (period === "month") {
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
  }
  return d.getFullYear() === now.getFullYear();
}

function matchesSize(e: EventItem, size: EventSize): boolean {
  if (size === "all") return true;
  const n = e.attendees;
  if (n === null || n === undefined) return false;
  if (size === "small")  return n < 100;
  if (size === "medium") return n >= 100 && n < 1000;
  return n >= 1000;
}

function matchesMode(e: EventItem, mode: EventMode): boolean {
  if (mode === "all") return true;
  const isOnline = locationToRegion(e.location) === "Online / Virtual";
  return mode === "online" ? isOnline : !isOnline;
}

// ---------------------------------------------------------------------------
// Sidebar stats
// ---------------------------------------------------------------------------

type MapStats = {
  leader:      { name: string; count: number } | null;
  peakMonth:   { label: string; count: number } | null;
  topLocation: { name: string; count: number } | null;
};

function computeStats(events: EventItem[]): MapStats {
  if (!events.length) return { leader: null, peakMonth: null, topLocation: null };

  const byCo: Record<string, number> = {};
  const byMonth: Record<string, number> = {};
  const byLoc: Record<string, number> = {};

  for (const e of events) {
    byCo[e.company] = (byCo[e.company] ?? 0) + 1;

    if (e.event_date) {
      const d = new Date(e.event_date);
      if (!isNaN(d.getTime())) {
        const key = d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
        byMonth[key] = (byMonth[key] ?? 0) + 1;
      }
    }

    if (e.location) {
      const isOnline = locationToRegion(e.location) === "Online / Virtual";
      if (!isOnline) {
        const city = e.location.split(",")[0].trim();
        if (city) byLoc[city] = (byLoc[city] ?? 0) + 1;
      }
    }
  }

  const topCo  = Object.entries(byCo).sort(([, a], [, b]) => b - a)[0];
  const topMo  = Object.entries(byMonth).sort(([, a], [, b]) => b - a)[0];
  const topL   = Object.entries(byLoc).sort(([, a], [, b]) => b - a)[0];

  return {
    leader:      topCo ? { name: topCo[0], count: topCo[1] } : null,
    peakMonth:   topMo ? { label: topMo[0], count: topMo[1] } : null,
    topLocation: topL  ? { name: topL[0],  count: topL[1]  } : null,
  };
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const SELECT_CLS =
  "text-xs border border-white/10 rounded-sm px-3 py-1.5 bg-neutral-grey-30 text-primary-white " +
  "focus:outline-none focus:ring-1 focus:ring-secondary-green/50 cursor-pointer";


// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EventsMap() {
  const { data, isLoading, isError, error } = useEvents();
  const { data: brandColors = {} } = useCompetitorColors();

  const [competitor, setCompetitor] = useState("");
  const [region, setRegion]         = useState("");
  const [period, setPeriod]         = useState<MapPeriod>("month");
  const [size, setSize]             = useState<EventSize>("all");
  const [mode, setMode]             = useState<EventMode>("all");

  const allCompanies = useMemo(
    () => [...new Set((data?.events ?? []).map((e) => e.company))].sort(),
    [data]
  );

  const allRegions = useMemo(() => {
    const present = new Set(
      (data?.events ?? []).map((e) => locationToRegion(e.location))
    );
    return REGION_ORDER.filter((r) => present.has(r));
  }, [data]);

  const filtered = useMemo(() => {
    return (data?.events ?? []).filter((e) => {
      if (competitor && e.company !== competitor) return false;
      if (region && locationToRegion(e.location) !== region) return false;
      if (!matchesPeriod(e, period)) return false;
      if (!matchesSize(e, size)) return false;
      if (!matchesMode(e, mode)) return false;
      return true;
    });
  }, [data, competitor, region, period, size, mode]);

  const stats = useMemo(() => computeStats(filtered), [filtered]);

  const hasFilter = Boolean(competitor || region || period !== "month" || size !== "all" || mode !== "all");

  function clearFilters() {
    setCompetitor("");
    setRegion("");
    setPeriod("month");
    setSize("all");
    setMode("all");
  }

  const mapContent = isLoading ? (
    <ZoneSkeleton height={520} />
  ) : isError ? (
    <ZoneError message={(error as Error)?.message} />
  ) : !filtered.length ? (
    <ZoneEmpty message="No events with known locations for this period." />
  ) : (
    <EventsMapCore
      events={filtered}
      allCompanies={allCompanies}
      brandColors={brandColors}
      region={region}
    />
  );

  return (
    <div className="flex flex-col gap-4 mt-5">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-[11px] text-neutral-grey-20 uppercase tracking-[0.12em] font-medium">
          Filter
        </span>

        <select className={SELECT_CLS} value={period} onChange={(e) => setPeriod(e.target.value as MapPeriod)}>
          {MAP_PERIOD_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>

        <select className={SELECT_CLS} value={mode} onChange={(e) => setMode(e.target.value as EventMode)}>
          {MODE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>

        <select className={SELECT_CLS} value={size} onChange={(e) => setSize(e.target.value as EventSize)}>
          {SIZE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>

        <select className={SELECT_CLS} value={competitor} onChange={(e) => setCompetitor(e.target.value)}>
          <option value="">All competitors</option>
          {allCompanies.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        <select className={SELECT_CLS} value={region} onChange={(e) => setRegion(e.target.value)}>
          <option value="">All regions</option>
          {allRegions.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>

        {hasFilter && (
          <button
            type="button"
            onClick={clearFilters}
            className="text-xs text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer"
          >
            Clear ×
          </button>
        )}

        <span className="ml-auto text-[11px] text-neutral-grey-20">
          {filtered.length} event{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Map + sidebar */}
      <div className="flex gap-4 items-stretch">
        {/* Map */}
        <div className="flex-1 rounded-lg overflow-hidden border border-white/8" style={{ height: 520 }}>
          {mapContent}
        </div>

        {/* Sidebar stats */}
        <div className="flex flex-col gap-3 w-52 shrink-0">
          {/* Event Leader */}
          <DashboardCard label="Event Leader" sublabel="Most active competitor" className="flex-1 p-4">
            {isLoading ? (
              <div className="h-10 bg-white/8 rounded animate-pulse" />
            ) : stats.leader ? (
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: getCompetitorColor(stats.leader.name, allCompanies, brandColors) }}
                  />
                  <span className="text-base font-medium text-primary-white leading-tight break-words">
                    {stats.leader.name}
                  </span>
                </div>
                <span className="text-xs text-neutral-grey-20">
                  {stats.leader.count} event{stats.leader.count !== 1 ? "s" : ""}
                </span>
              </div>
            ) : (
              <span className="text-sm text-neutral-grey-20">—</span>
            )}
          </DashboardCard>

          {/* Peak Month */}
          <DashboardCard label="Peak Month" sublabel="Highest event activity" className="flex-1 p-4">
            {isLoading ? (
              <div className="h-10 bg-white/8 rounded animate-pulse" />
            ) : stats.peakMonth ? (
              <div className="flex flex-col gap-1.5">
                <span className="text-base font-medium text-primary-white leading-tight">
                  {stats.peakMonth.label}
                </span>
                <span className="text-xs text-neutral-grey-20">
                  {stats.peakMonth.count} event{stats.peakMonth.count !== 1 ? "s" : ""}
                </span>
              </div>
            ) : (
              <span className="text-sm text-neutral-grey-20">—</span>
            )}
          </DashboardCard>

          {/* Top Location */}
          <DashboardCard label="Top Location" sublabel="Most in-person events" className="flex-1 p-4">
            {isLoading ? (
              <div className="h-10 bg-white/8 rounded animate-pulse" />
            ) : stats.topLocation ? (
              <div className="flex flex-col gap-1.5">
                <span className="text-base font-medium text-primary-white leading-tight">
                  {stats.topLocation.name}
                </span>
                <span className="text-xs text-neutral-grey-20">
                  {stats.topLocation.count} event{stats.topLocation.count !== 1 ? "s" : ""}
                </span>
              </div>
            ) : (
              <span className="text-sm text-neutral-grey-20">—</span>
            )}
          </DashboardCard>
        </div>
      </div>

      {/* Legend */}
      {!isLoading && !isError && allCompanies.length > 0 && (
        <div className="flex flex-wrap items-center gap-4">
          {allCompanies.map((company, i) => (
            <button
              key={company}
              type="button"
              onClick={() => setCompetitor(competitor === company ? "" : company)}
              className={[
                "flex items-center gap-1.5 text-xs transition-opacity cursor-pointer",
                competitor && competitor !== company ? "opacity-30" : "opacity-100",
              ].join(" ")}
            >
              <span
                className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: getCompetitorColor(company, allCompanies, brandColors) }}
              />
              <span className="text-neutral-grey-10">{company}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default EventsMap;