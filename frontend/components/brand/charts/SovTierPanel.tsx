"use client";

import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { SovEntry, SovTier } from "@/lib/brand/types";

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

function SovRow({
  entry,
  rank,
  maxRate,
}: {
  entry: SovEntry;
  rank: number;
  maxRate: number;
}) {
  const barWidth = maxRate > 0 ? (entry.mention_rate / maxRate) * 100 : 0;
  const pct = (entry.mention_rate * 100).toFixed(1);

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-black/4 last:border-0">
      {/* Rank */}
      <span
        className="text-[11px] w-4 shrink-0 text-right tabular-nums"
        style={{ fontFamily: "system-ui, -apple-system, sans-serif", color: "#CBCBCB" }}
      >
        {rank}
      </span>

      {/* Company + bar */}
      <div className="flex-1 min-w-0 flex flex-col gap-1.5">
        <div className="flex items-center justify-between gap-2">
          <span
            className={twMerge(
              clsx(
                "text-sm truncate font-medium",
                entry.is_target
                  ? "text-secondary-green"
                  : "text-primary-black"
              )
            )}
          >
            {entry.company}
          </span>
          <span
            className="text-xs shrink-0 tabular-nums text-neutral-grey-20"
            style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
          >
            {pct}%
          </span>
        </div>

        {/* Progress bar */}
        <div className="h-[3px] w-full rounded-full bg-neutral-grey-00 overflow-hidden">
          <div
            className={twMerge(
              clsx(
                "h-full rounded-full transition-all duration-500",
                entry.is_target ? "bg-secondary-green" : "bg-neutral-grey-10"
              )
            )}
            style={{ width: `${barWidth}%` }}
          />
        </div>
      </div>

      {/* Count badge */}
      <span
        className="text-[11px] w-6 shrink-0 text-center rounded-full bg-neutral-grey-00 py-0.5 tabular-nums text-neutral-grey-20"
        style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
        title={`${entry.mention_count} mention${entry.mention_count !== 1 ? "s" : ""}`}
      >
        {entry.mention_count}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------

type SovTierPanelProps = {
  tier: SovTier;
};

export default function SovTierPanel({ tier }: SovTierPanelProps) {
  if (!tier.entries.length) {
    return (
      <div className="text-sm text-neutral-grey-20 py-4 text-center">
        No co-mentions found for this tier.
      </div>
    );
  }

  // Highest mention rate drives the bar widths (relative scaling)
  const maxRate = Math.max(...tier.entries.map((e) => e.mention_rate));

  return (
    <div>
      {/* Column header */}
      <div className="flex items-center gap-3 mb-1 pb-2 border-b border-black/8">
        <span className="w-4 shrink-0" />
        <div className="flex-1 flex items-center justify-between">
          <span
            className="text-[10px] tracking-[0.14em] uppercase text-neutral-grey-20"
            style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
          >
            Company
          </span>
          <span
            className="text-[10px] tracking-[0.14em] uppercase text-neutral-grey-20"
            style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
          >
            Rate
          </span>
        </div>
        <span className="w-6 shrink-0" />
      </div>

      {/* Rows */}
      {tier.entries.map((entry, i) => (
        <SovRow
          key={entry.company}
          entry={entry}
          rank={i + 1}
          maxRate={maxRate}
        />
      ))}

      {/* Footer */}
      <p
        className="mt-3 text-[11px] text-neutral-grey-20"
        style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
      >
        {tier.total_keywords} keyword{tier.total_keywords !== 1 ? "s" : ""} in
        this tier · count = mentions
      </p>
    </div>
  );
}
