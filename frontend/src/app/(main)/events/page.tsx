"use client";

import { useMemo } from "react";

import PageToolbar from "@components/geo/PageToolbar";
import SectionHeader from "@components/geo/SectionHeader";
import EventsKpis from "@components/events/EventsKpis";
import EventsCharts from "@components/events/EventsCharts";
import EventsAlerts from "@components/events/EventsAlerts";
import EventsOverview from "@components/events/EventsOverview";
import { EventsCalendar } from "@components/events/EventsCalendar";
import { EventsMap } from "@components/events/EventsMap";
import { useEvents } from "@/lib/events/hooks";

function formatRelativeTime(iso: string | null | undefined): string {
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

export default function EventsPage() {
  const { data } = useEvents();
  const updatedAt = useMemo(
    () => formatRelativeTime(data?.latest_run_at),
    [data?.latest_run_at]
  );

  return (
    <div className="w-full flex flex-col gap-24">
      {/* Page header */}
      <header className="flex items-end justify-between gap-6 pb-6 border-b border-neutral-grey-30">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] tracking-[0.18em] uppercase text-neutral-grey-20 font-medium">
            Celonis and Competitors
          </span>
          <h1 className="text-3xl font-medium text-primary-white leading-none">
            Events Overview
          </h1>
          <p className="mt-2 text-sm text-neutral-grey-20 max-w-xl">
            Recently scraped events from Celonis and its tracked competitors —{" "}
            <span className="text-primary-white font-medium">
              sources are luma, meetup, news reports and the company websites
            </span>{" "}
            across all regions.
          </p>
        </div>
        <PageToolbar runtime="every month" updatedAt={updatedAt} agentsRunning={1} />
      </header>

      {/* Zone 1 — KPIs */}
      <section>
        <SectionHeader
          label="Event summary"
          description="High-level event presence across all tracked competitors."
        />
        <EventsKpis />
      </section>

      {/* Zone 2 — Charts */}
      <section>
        <SectionHeader
          label="Competitive landscape"
          description="Event volume and format split across all tracked competitors."
        />
        <EventsCharts />
      </section>

      {/* Zone 3 — Alerts */}
      <section>
        <SectionHeader
          label="Celonis positioning"
          description="Automated strategic signals derived from scraped event data."
        />
        <EventsAlerts />
      </section>

      {/* Zone 4 — Calendar */}
      <section>
        <SectionHeader
          label="Events Calendar"
          description="Calendar including all scraped industry events"
        />
        <EventsCalendar />
      </section>

      {/* Zone 5 — Map */}
      <section>
        <SectionHeader
          label="Location Map"
          description="World map showing the location of all events"
        />
        <EventsMap />
      </section>

      {/* Zone 6 — Event cards */}
      <section>
        <EventsOverview />
      </section>
    </div>
  );
}