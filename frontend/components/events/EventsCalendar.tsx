"use client";

import { useState, useMemo } from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { ChevronLeft, ChevronRight } from "lucide-react";

import DashboardCard from "@components/brand/DashboardCard";
import { useEvents } from "@/lib/events/hooks";
import { useCompetitorColors } from "@/lib/competitors/hooks";
import { getCompetitorColor } from "@/lib/competitors/colors";
import type { EventItem } from "@/lib/events/types";

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

const WEEKDAYS    = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS_FULL = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];

function parseEventDate(e: EventItem): Date | null {
  const raw = e.event_date ?? e.date ?? null;
  if (!raw) return null;
  const d = new Date(raw);
  return isNaN(d.getTime()) ? null : d;
}

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

// 0 = Monday … 6 = Sunday
function firstWeekday(year: number, month: number): number {
  return (new Date(year, month, 1).getDay() + 6) % 7;
}

type EventsByDate = Record<string, EventItem[]>;
type View = "month" | "year";

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

function DayTooltip({
  dateStr,
  events,
  allCompanies,
  brandColors,
  colIdx,
  rowIdx,
  totalRows,
}: {
  dateStr: string;
  events: EventItem[];
  allCompanies: string[];
  brandColors: Record<string, string>;
  colIdx: number;
  rowIdx: number;
  totalRows: number;
}) {
  const label = new Date(dateStr + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric",
  });

  return (
    <div
      className={twMerge(
        clsx(
          "absolute z-50 w-60 bg-primary-black border border-white/12 rounded-lg p-3",
          "shadow-[0_8px_24px_rgba(0,0,0,0.6)] flex flex-col gap-2 pointer-events-none",
          colIdx >= 4 ? "right-0" : "left-0",
          rowIdx >= totalRows - 1 ? "bottom-full mb-1" : "top-full mt-1"
        )
      )}
    >
      <div className="text-[10px] tracking-[0.14em] uppercase text-neutral-grey-20 font-medium">
        {label}
      </div>
      {events.map((e, i) => (
        <div key={i} className="flex items-start gap-2">
          <span
            className="mt-[3px] w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: getCompetitorColor(e.company, allCompanies, brandColors) }}
          />
          <div className="min-w-0">
            <div className="text-xs text-primary-white font-medium leading-snug line-clamp-2">
              {e.name ?? e.title ?? "Untitled"}
            </div>
            <div className="text-[10px] text-neutral-grey-20 mt-0.5">
              {e.company}
              {e.location ? ` · ${e.location}` : ""}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Month view
// ---------------------------------------------------------------------------

function MonthView({
  year,
  month,
  eventsByDate,
  allCompanies,
  brandColors,
}: {
  year: number;
  month: number;
  eventsByDate: EventsByDate;
  allCompanies: string[];
  brandColors: Record<string, string>;
}) {
  const [hoveredDate, setHoveredDate] = useState<string | null>(null);
  const today = toISODate(new Date());

  const monthPrefix = `${year}-${String(month + 1).padStart(2, "0")}`;
  const monthTotal = Object.entries(eventsByDate)
    .filter(([d]) => d.startsWith(monthPrefix))
    .reduce((sum, [, evts]) => sum + evts.length, 0);

  const cells: (number | null)[] = [
    ...Array(firstWeekday(year, month)).fill(null),
    ...Array.from({ length: daysInMonth(year, month) }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const totalRows = cells.length / 7;

  return (
    <div>
      {/* Month total */}
      {monthTotal > 0 && (
        <div className="flex justify-end mb-2">
          <span className="text-[11px] text-neutral-grey-20">
            <span className="font-medium text-primary-white">{monthTotal}</span> events this month
          </span>
        </div>
      )}

      {/* Weekday headers */}
      <div className="grid grid-cols-7 border-b border-white/8 mb-0">
        {WEEKDAYS.map((d) => (
          <div key={d} className="text-[10px] tracking-[0.12em] uppercase text-neutral-grey-20 text-center py-2 font-medium">
            {d}
          </div>
        ))}
      </div>

      {/* Day grid — no overflow-hidden so tooltips escape */}
      <div className="grid grid-cols-7 border-l border-white/8">
        {cells.map((day, i) => {
          const colIdx = i % 7;
          const rowIdx = Math.floor(i / 7);

          if (day === null) {
            return (
              <div
                key={`empty-${i}`}
                className="border-b border-r border-white/8 min-h-[80px] bg-white/2"
              />
            );
          }

          const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const dayEvents = eventsByDate[dateStr] ?? [];
          const isToday = dateStr === today;
          const isHovered = hoveredDate === dateStr;

          return (
            <div
              key={dateStr}
              className={twMerge(clsx(
                "relative border-b border-r border-white/8 min-h-[80px] p-2 transition-colors",
                dayEvents.length > 0 && "cursor-pointer hover:bg-white/4"
              ))}
              onMouseEnter={() => dayEvents.length > 0 && setHoveredDate(dateStr)}
              onMouseLeave={() => setHoveredDate(null)}
            >
              {/* Day number */}
              <div className={twMerge(clsx(
                "text-xs font-medium mb-2 w-6 h-6 flex items-center justify-center rounded-full",
                isToday
                  ? "bg-secondary-green text-primary-black"
                  : "text-neutral-grey-20"
              ))}>
                {day}
              </div>

              {/* Event dots */}
              {dayEvents.length > 0 && (
                <div className="flex flex-wrap gap-1 items-center">
                  {dayEvents.slice(0, 6).map((e, j) => (
                    <span
                      key={j}
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: getCompetitorColor(e.company, allCompanies, brandColors) }}
                    />
                  ))}
                  {dayEvents.length > 6 && (
                    <span className="text-[9px] text-neutral-grey-20 leading-none">
                      +{dayEvents.length - 6}
                    </span>
                  )}
                </div>
              )}

              {/* Tooltip */}
              {isHovered && dayEvents.length > 0 && (
                <DayTooltip
                  dateStr={dateStr}
                  events={dayEvents}
                  allCompanies={allCompanies}
                  brandColors={brandColors}
                  colIdx={colIdx}
                  rowIdx={rowIdx}
                  totalRows={totalRows}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mini-month for year view
// ---------------------------------------------------------------------------

function MiniMonth({
  year,
  month,
  eventsByDate,
  allCompanies,
  brandColors,
  onClick,
}: {
  year: number;
  month: number;
  eventsByDate: EventsByDate;
  allCompanies: string[];
  brandColors: Record<string, string>;
  onClick: () => void;
}) {
  const total   = daysInMonth(year, month);
  const offset  = firstWeekday(year, month);
  const today   = toISODate(new Date());

  const cells: (number | null)[] = [
    ...Array(offset).fill(null),
    ...Array.from({ length: total }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col gap-1.5 p-3 rounded-lg border border-white/8 bg-white/3 hover:bg-white/6 transition-colors text-left w-full cursor-pointer"
    >
      <div className="text-xs font-medium text-neutral-grey-10 mb-1">
        {MONTHS_FULL[month]}
      </div>

      {/* Mini weekday headers */}
      <div className="grid grid-cols-7">
        {WEEKDAYS.map((d) => (
          <div key={d} className="text-[8px] text-neutral-grey-20 text-center">
            {d[0]}
          </div>
        ))}
      </div>

      {/* Mini days */}
      <div className="grid grid-cols-7 gap-y-0.5">
        {cells.map((day, i) => {
          if (day === null) return <div key={`e-${i}`} className="w-5 h-5" />;
          const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const events  = eventsByDate[dateStr] ?? [];
          const isToday = dateStr === today;

          return (
            <div
              key={dateStr}
              className={twMerge(clsx(
                "relative w-5 h-5 flex items-center justify-center rounded-sm",
                isToday && "ring-1 ring-secondary-green"
              ))}
              title={events.length ? events.map((e) => e.name ?? e.company).join(", ") : undefined}
            >
              <span className={clsx(
                "text-[8px] leading-none",
                isToday ? "text-secondary-green" : "text-neutral-grey-20"
              )}>
                {day}
              </span>
              {events.length > 0 && (
                <div className="absolute bottom-0 left-0 right-0 flex justify-center gap-[2px]">
                  {events.slice(0, 3).map((e, j) => (
                    <span
                      key={j}
                      className="w-[3px] h-[3px] rounded-full shrink-0"
                      style={{ backgroundColor: getCompetitorColor(e.company, allCompanies, brandColors) }}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function EventsCalendar() {
  const { data, isLoading } = useEvents();
  const { data: brandColors = {} } = useCompetitorColors();
  const now = new Date();

  const [view, setView]   = useState<View>("month");
  const [year, setYear]   = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  const allCompanies = useMemo(
    () => [...new Set((data?.events ?? []).map((e) => e.company))].sort(),
    [data]
  );

  const eventsByDate = useMemo<EventsByDate>(() => {
    const map: EventsByDate = {};
    for (const e of data?.events ?? []) {
      const d = parseEventDate(e);
      if (!d) continue;
      const key = toISODate(d);
      (map[key] ??= []).push(e);
    }
    return map;
  }, [data]);

  function prevMonth() {
    if (month === 0) { setYear((y) => y - 1); setMonth(11); }
    else setMonth((m) => m - 1);
  }
  function nextMonth() {
    if (month === 11) { setYear((y) => y + 1); setMonth(0); }
    else setMonth((m) => m + 1);
  }

  return (
    <DashboardCard>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-5 gap-4 flex-wrap">
        {/* Navigation */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={view === "month" ? prevMonth : () => setYear((y) => y - 1)}
            className="p-1.5 rounded-sm text-neutral-grey-20 hover:text-primary-white hover:bg-white/8 transition-colors cursor-pointer"
          >
            <ChevronLeft size={15} />
          </button>
          <span className="text-sm font-medium text-primary-white min-w-[150px] text-center">
            {view === "month" ? `${MONTHS_FULL[month]} ${year}` : String(year)}
          </span>
          <button
            type="button"
            onClick={view === "month" ? nextMonth : () => setYear((y) => y + 1)}
            className="p-1.5 rounded-sm text-neutral-grey-20 hover:text-primary-white hover:bg-white/8 transition-colors cursor-pointer"
          >
            <ChevronRight size={15} />
          </button>
        </div>

        {/* View toggle */}
        <div className="flex items-center gap-0.5 bg-white/5 rounded-sm p-0.5">
          {(["month", "year"] as View[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={twMerge(clsx(
                "px-3 py-1 text-xs rounded-sm transition-colors cursor-pointer capitalize font-medium",
                view === v
                  ? "bg-secondary-green text-primary-black"
                  : "text-neutral-grey-20 hover:text-primary-white"
              ))}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Competitor legend */}
      {allCompanies.length > 0 && (
        <div className="flex flex-wrap items-center gap-4 mb-5 pb-4 border-b border-white/8">
          {allCompanies.map((c) => (
            <div key={c} className="flex items-center gap-1.5 text-[11px] text-neutral-grey-20">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: getCompetitorColor(c, allCompanies, brandColors) }}
              />
              {c}
            </div>
          ))}
        </div>
      )}

      {/* Calendar body */}
      {isLoading ? (
        <div className="h-64 flex items-center justify-center text-neutral-grey-20 text-sm animate-pulse">
          Loading events…
        </div>
      ) : view === "month" ? (
        <MonthView
          year={year}
          month={month}
          eventsByDate={eventsByDate}
          allCompanies={allCompanies}
          brandColors={brandColors}
        />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {Array.from({ length: 12 }, (_, m) => (
            <MiniMonth
              key={m}
              year={year}
              month={m}
              eventsByDate={eventsByDate}
              allCompanies={allCompanies}
              brandColors={brandColors}
              onClick={() => { setMonth(m); setView("month"); }}
            />
          ))}
        </div>
      )}
    </DashboardCard>
  );
}
