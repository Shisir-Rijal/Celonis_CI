"use client";

import { useState, useMemo } from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { KeywordRow } from "@/lib/brand/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIER_LABELS: Record<string, string> = {
  brand_category: "Brand",
  use_case: "Use Case",
  competitor_trigger: "Competitor",
  unknown: "—",
};

const STRENGTH_LABELS: Record<string, string> = {
  listed: "Listed",
  attributed: "Attributed",
  recommended: "Recommended",
  default: "Default",
};

const FRAMING_LABELS: Record<string, string> = {
  technical: "Technical",
  strategic: "Strategic",
  visionary: "Visionary",
};

const FONT = { fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif" };

// ---------------------------------------------------------------------------
// Badge helpers
// ---------------------------------------------------------------------------

function MentionedBadge({ mentioned }: { mentioned: boolean }) {
  return (
    <span
      className={twMerge(
        clsx(
          "inline-flex items-center gap-1 text-[10px] font-medium rounded-full px-2 py-0.5",
          mentioned
            ? "bg-success/10 text-success"
            : "bg-neutral-grey-00 text-neutral-grey-20"
        )
      )}
    >
      <span
        className={twMerge(
          clsx(
            "w-1.5 h-1.5 rounded-full",
            mentioned ? "bg-success" : "bg-neutral-grey-10"
          )
        )}
      />
      {mentioned ? "Yes" : "No"}
    </span>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const label = TIER_LABELS[tier] ?? tier;
  return (
    <span className="text-[10px] tracking-[0.1em] uppercase text-neutral-grey-20 font-medium">
      {label}
    </span>
  );
}

function StrengthBadge({ strength }: { strength: string | null }) {
  if (!strength) return <span className="text-neutral-grey-10 text-xs">—</span>;
  const label = STRENGTH_LABELS[strength] ?? strength;
  const colorMap: Record<string, string> = {
    listed: "bg-neutral-grey-00 text-neutral-grey-20",
    attributed: "bg-secondary-blue/10 text-secondary-blue",
    recommended: "bg-success/10 text-success",
    default: "bg-secondary-green/20 text-green-700",
  };
  return (
    <span
      className={twMerge(
        clsx(
          "inline-block text-[10px] font-medium rounded-full px-2 py-0.5",
          colorMap[strength] ?? "bg-neutral-grey-00 text-neutral-grey-20"
        )
      )}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

type Filters = {
  tier: string;
  mentioned: string;
  strength: string;
};

function FilterBar({
  filters,
  onChange,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
}) {
  return (
    <div
      className="flex flex-wrap items-center gap-3 mb-4"
      style={FONT}
    >
      <span className="text-[11px] text-neutral-grey-20 uppercase tracking-[0.12em] font-medium">
        Filter
      </span>

      <select
        className="text-xs border border-white/10 rounded-md px-2 py-1.5 bg-neutral-grey-30 text-primary-white focus:outline-none focus:ring-1 focus:ring-secondary-green/50"
        value={filters.tier}
        onChange={(e) => onChange({ ...filters, tier: e.target.value })}
      >
        <option value="">All Tiers</option>
        <option value="brand_category">Brand</option>
        <option value="use_case">Use Case</option>
        <option value="competitor_trigger">Competitor Trigger</option>
      </select>

      <select
        className="text-xs border border-white/10 rounded-md px-2 py-1.5 bg-neutral-grey-30 text-primary-white focus:outline-none focus:ring-1 focus:ring-secondary-green/50"
        value={filters.mentioned}
        onChange={(e) => onChange({ ...filters, mentioned: e.target.value })}
      >
        <option value="">All</option>
        <option value="yes">Mentioned</option>
        <option value="no">Not Mentioned</option>
      </select>

      <select
        className="text-xs border border-white/10 rounded-md px-2 py-1.5 bg-neutral-grey-30 text-primary-white focus:outline-none focus:ring-1 focus:ring-secondary-green/50"
        value={filters.strength}
        onChange={(e) => onChange({ ...filters, strength: e.target.value })}
      >
        <option value="">All Strengths</option>
        <option value="listed">Listed</option>
        <option value="attributed">Attributed</option>
        <option value="recommended">Recommended</option>
        <option value="default">Default</option>
      </select>

      {(filters.tier || filters.mentioned || filters.strength) && (
        <button
          type="button"
          className="text-xs text-neutral-grey-20 hover:text-primary-white transition-colors"
          onClick={() => onChange({ tier: "", mentioned: "", strength: "" })}
        >
          Clear ×
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row with expandable quote
// ---------------------------------------------------------------------------

function KeywordTableRow({ row }: { row: KeywordRow }) {
  const [open, setOpen] = useState(false);
  const hasQuote = Boolean(row.exact_quote);

  return (
    <>
      <tr
        className={twMerge(
          clsx(
            "border-b border-white/8 text-sm",
            hasQuote ? "cursor-pointer hover:bg-white/5" : ""
          )
        )}
        onClick={() => hasQuote && setOpen((o) => !o)}
        title={hasQuote ? "Click to see AI response excerpt" : undefined}
      >
        {/* Keyword */}
        <td className="py-2.5 pr-4">
          <span className="font-medium text-primary-white">{row.keyword}</span>
          {hasQuote && (
            <span className="ml-1.5 text-[10px] text-neutral-grey-10">
              {open ? "▲" : "▼"}
            </span>
          )}
        </td>

        {/* Tier */}
        <td className="py-2.5 pr-4">
          <TierBadge tier={row.tier} />
        </td>

        {/* Mentioned */}
        <td className="py-2.5 pr-4">
          <MentionedBadge mentioned={row.mentioned} />
        </td>

        {/* Strength */}
        <td className="py-2.5 pr-4">
          <StrengthBadge strength={row.recommendation_strength} />
        </td>

        {/* Framing */}
        <td className="py-2.5 pr-4 text-xs text-neutral-grey-20">
          {row.framing ? FRAMING_LABELS[row.framing] ?? row.framing : "—"}
        </td>

        {/* Counter-positioning */}
        <td className="py-2.5 text-xs text-neutral-grey-20 max-w-[200px]">
          {row.counter_positioning ? (
            <span className="text-warning">{row.counter_positioning}</span>
          ) : (
            "—"
          )}
        </td>
      </tr>

      {/* Expandable quote row */}
      {open && row.exact_quote && (
        <tr className="bg-white/5">
          <td colSpan={6} className="py-3 px-4">
            <p
              className="text-xs text-neutral-grey-10 leading-relaxed italic border-l-2 border-neutral-grey-20 pl-3"
              style={FONT}
            >
              {row.exact_quote}
            </p>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main table
// ---------------------------------------------------------------------------

type KeywordTableProps = {
  rows: KeywordRow[];
};

export default function KeywordTable({ rows }: KeywordTableProps) {
  const [filters, setFilters] = useState<Filters>({
    tier: "",
    mentioned: "",
    strength: "",
  });

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (filters.tier && r.tier !== filters.tier) return false;
      if (filters.mentioned === "yes" && !r.mentioned) return false;
      if (filters.mentioned === "no" && r.mentioned) return false;
      if (filters.strength && r.recommendation_strength !== filters.strength)
        return false;
      return true;
    });
  }, [rows, filters]);

  if (!rows.length) {
    return (
      <p className="text-sm text-neutral-grey-20 py-4">
        No keyword data available.
      </p>
    );
  }

  return (
    <div style={FONT}>
      <FilterBar filters={filters} onChange={setFilters} />

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/8">
              {["Keyword", "Tier", "Mentioned", "Strength", "Framing", "Criticism"].map(
                (h) => (
                  <th
                    key={h}
                    className="pb-2.5 pr-4 text-[10px] tracking-[0.12em] uppercase text-neutral-grey-20 font-medium whitespace-nowrap"
                  >
                    {h}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <KeywordTableRow key={row.keyword} row={row} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[11px] text-neutral-grey-20">
        {filtered.length} of {rows.length} keywords
        {filtered.length < rows.length ? " (filtered)" : ""} · Click a row to see the AI response excerpt
      </p>
    </div>
  );
}
