"use client";

import { useState, useMemo, useEffect } from "react";

import SectionHeader from "@components/geo/SectionHeader";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import EventCard from "@components/events/EventCard";
import { useEvents } from "@/lib/events/hooks";
import type { EventItem } from "@/lib/events/types";

// ---------------------------------------------------------------------------
// Region mapping
// ---------------------------------------------------------------------------

const REGION_KEYWORDS: Array<{ region: string; keywords: string[] }> = [
  {
    region: "Online / Virtual",
    keywords: ["online", "virtual", "remote", "webinar", "digital", "zoom", "livestream", "hybrid"],
  },
  {
    region: "Europe",
    keywords: [
      // countries
      "germany", "uk", "united kingdom", "england", "france", "spain", "italy",
      "netherlands", "sweden", "norway", "denmark", "finland", "belgium", "austria",
      "switzerland", "poland", "portugal", "czech", "hungary", "romania", "greece",
      "ireland", "scotland", "europe", "eu",
      // cities
      "london", "berlin", "paris", "amsterdam", "munich", "münchen", "hamburg",
      "frankfurt", "vienna", "wien", "zurich", "zürich", "geneva", "stockholm",
      "copenhagen", "oslo", "helsinki", "brussels", "dublin", "madrid", "barcelona",
      "rome", "milan", "warsaw", "prague", "budapest", "lisbon", "athens", "edinburgh",
      "cologne", "köln", "düsseldorf", "stuttgart", "lyon", "marseille", "rotterdam",
    ],
  },
  {
    region: "North America",
    keywords: [
      // countries / regions
      "usa", "united states", "canada", "mexico",
      // US states
      "california", "new york", "texas", "florida", "illinois", "washington",
      "georgia", "massachusetts", "nevada", "colorado", "virginia", "pennsylvania",
      "arizona", "oregon", "michigan", "ohio", "minnesota", "north carolina",
      // cities
      "new york city", "nyc", "san francisco", "los angeles", "chicago", "boston",
      "seattle", "austin", "houston", "dallas", "miami", "atlanta", "las vegas",
      "denver", "toronto", "vancouver", "montreal", "mexico city", "san jose",
      "san diego", "phoenix", "portland", "detroit", "nashville", "charlotte",
      "salt lake city", "minneapolis", "ottawa", "calgary", "philadelphia",
    ],
  },
  {
    region: "South America",
    keywords: [
      "brazil", "argentina", "chile", "colombia", "peru", "venezuela",
      "uruguay", "ecuador", "bolivia", "paraguay",
      "são paulo", "sao paulo", "buenos aires", "santiago", "bogotá", "bogota",
      "lima", "rio de janeiro", "montevideo", "quito", "caracas", "medellín",
    ],
  },
  {
    region: "Asia Pacific",
    keywords: [
      "china", "japan", "india", "australia", "singapore", "south korea", "korea",
      "indonesia", "malaysia", "thailand", "vietnam", "new zealand", "hong kong",
      "taiwan", "philippines", "bangladesh", "sri lanka", "myanmar", "cambodia",
      "tokyo", "shanghai", "beijing", "sydney", "melbourne", "seoul", "mumbai",
      "bangalore", "bengaluru", "jakarta", "bangkok", "kuala lumpur", "taipei",
      "auckland", "osaka", "shenzhen", "guangzhou", "pune", "hyderabad", "delhi",
    ],
  },
  {
    region: "Middle East & Africa",
    keywords: [
      "uae", "united arab emirates", "saudi arabia", "israel", "turkey",
      "egypt", "south africa", "nigeria", "kenya", "ghana", "morocco",
      "qatar", "kuwait", "bahrain", "jordan", "lebanon", "iran", "oman",
      "dubai", "abu dhabi", "tel aviv", "riyadh", "istanbul", "cairo",
      "johannesburg", "lagos", "nairobi", "casablanca", "doha", "muscat",
      "cape town", "accra", "addis ababa", "dar es salaam",
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
// Period filter helpers
// ---------------------------------------------------------------------------

const PERIOD_OPTIONS = [
  { value: "upcoming",    label: "Upcoming"     },
  { value: "past_month",  label: "Past month"   },
  { value: "past_3m",     label: "Past 3 months"},
  { value: "all",         label: "All"          },
] as const;

type Period = typeof PERIOD_OPTIONS[number]["value"];

function eventDate(e: EventItem): Date | null {
  if (!e.event_date) return null;
  const d = new Date(e.event_date);
  return isNaN(d.getTime()) ? null : d;
}

function matchesPeriod(e: EventItem, period: Period): boolean {
  if (period === "all") return true;
  const d = eventDate(e);
  if (!d) return false;
  const now = new Date();
  if (period === "upcoming") return d >= now;
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - (period === "past_month" ? 1 : 3));
  return d >= cutoff && d < now;
}

function applyFilters(
  events: EventItem[],
  competitor: string,
  period: Period,
  region: string,
  topic: string,
): EventItem[] {
  return events.filter((e) => {
    if (competitor && e.company !== competitor) return false;
    if (region && locationToRegion(e.location) !== region) return false;
    if (topic && e.event_topic !== topic) return false;
    return matchesPeriod(e, period);
  });
}

// ---------------------------------------------------------------------------
// Shared select style
// ---------------------------------------------------------------------------

const SELECT_CLS =
  "text-xs border border-white/10 rounded-sm px-3 py-1.5 bg-neutral-grey-30 text-primary-white " +
  "focus:outline-none focus:ring-1 focus:ring-secondary-green/50 cursor-pointer";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EventsOverview() {
  const { data, isLoading, isError, error } = useEvents();

  const [competitor, setCompetitor] = useState("");
  const [period, setPeriod]         = useState<Period>("all");
  const [region, setRegion]         = useState("");
  const [topic, setTopic]           = useState("");
  const [visibleCount, setVisibleCount] = useState(12);

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

  const allTopics = useMemo(() => {
    const countMap: Record<string, number> = {};
    for (const e of data?.events ?? []) {
      if (e.event_topic) countMap[e.event_topic] = (countMap[e.event_topic] ?? 0) + 1;
    }
    return Object.entries(countMap)
      .sort((a, b) => b[1] - a[1])
      .map(([t]) => t);
  }, [data]);

  const filtered = useMemo(
    () => applyFilters(data?.events ?? [], competitor, period, region, topic),
    [data, competitor, period, region, topic]
  );

  const hasFilter = Boolean(competitor || region || period !== "all" || topic);

  useEffect(() => { setVisibleCount(12); }, [filtered]);

  function clearFilters() {
    setCompetitor("");
    setPeriod("all");
    setRegion("");
    setTopic("");
  }

  return (
    <section className="flex flex-col gap-5">
      <SectionHeader
        label="Recent events"
        description="Scraped events across tracked competitors — filter by competitor, time window, or region."
        action={
          hasFilter ? (
            <button
              type="button"
              onClick={clearFilters}
              className="text-xs text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer"
            >
              Clear filters ×
            </button>
          ) : undefined
        }
      />

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-[11px] text-neutral-grey-20 uppercase tracking-[0.12em] font-medium">
          Filter
        </span>

        <select
          className={SELECT_CLS}
          value={competitor}
          onChange={(e) => setCompetitor(e.target.value)}
        >
          <option value="">All competitors</option>
          {allCompanies.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <select
          className={SELECT_CLS}
          value={period}
          onChange={(e) => setPeriod(e.target.value as Period)}
        >
          {PERIOD_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <select
          className={SELECT_CLS}
          value={region}
          onChange={(e) => setRegion(e.target.value)}
        >
          <option value="">All regions</option>
          {allRegions.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>

        <select
          className={SELECT_CLS}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
        >
          <option value="">All topics</option>
          {allTopics.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <ZoneSkeleton key={i} height={220} />
          ))}
        </div>
      ) : isError ? (
        <ZoneError message={(error as Error)?.message} />
      ) : !filtered.length ? (
        <ZoneEmpty
          message={
            hasFilter
              ? "No events match the selected filters."
              : "No events scraped yet."
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.slice(0, visibleCount).map((event, i) => (
              <EventCard
                key={`${event.company}-${event.event_date ?? i}-${i}`}
                event={event}
                allCompanies={allCompanies}
              />
            ))}
          </div>
          <div className="flex items-center justify-between gap-4">
            <p className="text-[11px] text-neutral-grey-20">
              {Math.min(visibleCount, filtered.length)} of {filtered.length} events
              {hasFilter ? " (filtered)" : ""}
            </p>
            {visibleCount < filtered.length && (
              <button
                type="button"
                onClick={() => setVisibleCount((n) => n + 12)}
                className="text-xs font-medium text-primary-white border border-white/12 rounded-sm px-4 py-1.5 hover:border-secondary-green hover:text-secondary-green transition-colors cursor-pointer"
              >
                Show more ({filtered.length - visibleCount} remaining)
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
