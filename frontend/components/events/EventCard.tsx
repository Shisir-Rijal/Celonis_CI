"use client";

import { MapPin, Users, ExternalLink, Calendar } from "lucide-react";

import DashboardCard from "@components/geo/DashboardCard";
import type { EventItem } from "@/lib/events/types";
import { useCompetitorColors } from "@/lib/competitors/hooks";
import { getCompetitorColor } from "@/lib/competitors/colors";

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function toText(summary: string | string[] | null): string {
  if (!summary) return "";
  return Array.isArray(summary) ? summary.join(" ") : summary;
}

type EventCardProps = {
  event: EventItem;
  allCompanies: string[];
};

export default function EventCard({ event, allCompanies }: EventCardProps) {
  const { data: brandColors = {} } = useCompetitorColors();
  const color = getCompetitorColor(event.company, allCompanies, brandColors);
  const label = event.name ?? event.title ?? "Untitled event";
  const text  = toText(event.summary);

  return (
    <DashboardCard className="flex flex-col gap-4 h-full">
      {/* Company badge + topic + date */}
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[10px] tracking-widest uppercase font-medium px-2 py-0.5 rounded-sm"
            style={{ backgroundColor: `${color}26`, color }}
          >
            {event.company}
          </span>
          {event.event_topic && (
            <span className="text-[10px] tracking-widest uppercase font-medium text-neutral-grey-20 px-2 py-0.5 rounded-sm bg-white/5">
              {event.event_topic}
            </span>
          )}
        </div>
        {event.event_date && (
          <div className="flex items-center gap-1 text-[11px] text-neutral-grey-20 shrink-0">
            <Calendar size={11} />
            <span>{formatDate(event.event_date)}</span>
          </div>
        )}
      </div>

      {/* Title */}
      <h3 className="text-base font-medium text-primary-white leading-snug">
        {label}
      </h3>

      {/* Location + attendees */}
      <div className="flex items-center gap-4 text-xs text-neutral-grey-20">
        {event.location && (
          <span className="flex items-center gap-1">
            <MapPin size={11} className="shrink-0" />
            {event.location}
          </span>
        )}
        {event.attendees != null && (
          <span className="flex items-center gap-1">
            <Users size={11} className="shrink-0" />
            {event.attendees.toLocaleString()}
          </span>
        )}
      </div>

      {/* Summary */}
      {text && (
        <p className="text-xs text-neutral-grey-10 leading-relaxed line-clamp-3 flex-1">
          {text}
        </p>
      )}

      {/* Speakers */}
      {event.speakers?.length ? (
        <div className="text-[11px] text-neutral-grey-20">
          <span className="uppercase tracking-widest font-medium">Speakers · </span>
          {event.speakers.slice(0, 3).join(", ")}
          {event.speakers.length > 3 && ` +${event.speakers.length - 3}`}
        </div>
      ) : null}

      {/* Source link */}
      {event.source_link && (
        <div className="mt-auto pt-3 border-t border-white/8">
          <a
            href={event.source_link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-secondary-green hover:opacity-80 transition-opacity font-medium"
          >
            View event <ExternalLink size={11} />
          </a>
        </div>
      )}
    </DashboardCard>
  );
}
