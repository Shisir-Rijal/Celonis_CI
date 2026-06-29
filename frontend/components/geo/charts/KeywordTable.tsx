"use client";

import { useState, useMemo } from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { KeywordRow, LlmKeywordResult } from "@/lib/brand/types";

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
  organic: "Organic",
};

const FRAMING_LABELS: Record<string, string> = {
  technical: "Technical",
  strategic: "Strategic",
  visionary: "Visionary",
};

const LLM_LABELS: Record<string, string> = {
  "gpt-5.5": "GPT-5.5",
  "gpt-4o-mini": "GPT-4o mini",
  "gpt-4o": "GPT-4o",
  "claude-sonnet-4-6": "Claude Sonnet",
  "sonar-pro": "Perplexity",
};

const FONT = { fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif" };

function labelLlm(raw: string) {
  return LLM_LABELS[raw] ?? raw;
}

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
            : "bg-error/10 text-error"
        )
      )}
    >
      <span
        className={twMerge(
          clsx(
            "w-1.5 h-1.5 rounded-full",
            mentioned ? "bg-success" : "bg-error"
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
// LLM sub-row — always visible, dimmed if not mentioned
// ---------------------------------------------------------------------------

function LlmSubRow({ result }: { result: LlmKeywordResult }) {
  const [quoteOpen, setQuoteOpen] = useState(false);

  return (
    <>
      <tr
        className={twMerge(
          clsx(
            "text-xs border-b border-white/4 transition-opacity",
            !result.mentioned && "opacity-35"
          )
        )}
      >
        {/* LLM name — indented */}
        <td className="py-1.5 pr-4 pl-6">
          <span className="text-neutral-grey-10 font-mono text-[10px]">
            ↳ {labelLlm(result.llm)}
          </span>
        </td>

        {/* Tier — blank (inherited from parent row) */}
        <td />

        {/* Mentioned */}
        <td className="py-1.5 pr-4">
          <MentionedBadge mentioned={result.mentioned} />
        </td>

        {/* Strength */}
        <td className="py-1.5 pr-4">
          <StrengthBadge strength={result.recommendation_strength} />
        </td>

        {/* Framing */}
        <td className="py-1.5 pr-4 text-neutral-grey-20">
          {result.framing ? (FRAMING_LABELS[result.framing] ?? result.framing) : "—"}
        </td>

        {/* Excerpt toggle */}
        <td className="py-1.5">
          {result.exact_quote ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setQuoteOpen((o) => !o);
              }}
              className="text-[10px] text-neutral-grey-10 hover:text-primary-white transition-colors cursor-pointer"
            >
              {quoteOpen ? "▲ hide" : "▼ excerpt"}
            </button>
          ) : (
            <span className="text-neutral-grey-10">—</span>
          )}
        </td>
      </tr>

      {/* Expandable excerpt */}
      {quoteOpen && result.exact_quote && (
        <tr className="bg-white/3">
          <td colSpan={6} className="py-2 pl-10 pr-4">
            <p
              className="text-[11px] text-neutral-grey-10 leading-relaxed italic border-l-2 border-neutral-grey-20 pl-3"
              style={FONT}
            >
              {result.exact_quote}
            </p>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main keyword row
// When per_llm is populated → always-visible sub-rows, no expandable quote on
// the aggregate row.
// When per_llm is empty (single-LLM flat view) → expandable quote on this row.
// ---------------------------------------------------------------------------

function KeywordTableRow({ row }: { row: KeywordRow }) {
  const [open, setOpen] = useState(false);
  const hasSubRows = (row.per_llm?.length ?? 0) > 0;
  const hasQuote = !hasSubRows && Boolean(row.exact_quote);

  return (
    <>
      <tr
        className={twMerge(
          clsx(
            "border-b border-white/8 text-sm",
            hasSubRows && "bg-white/2",
            hasQuote && "cursor-pointer hover:bg-white/5"
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
          {row.framing ? (FRAMING_LABELS[row.framing] ?? row.framing) : "—"}
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

      {/* Expandable quote — only when no sub-rows */}
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

      {/* Per-LLM sub-rows — always visible when aggregated view */}
      {hasSubRows &&
        row.per_llm?.map((result) => (
          <LlmSubRow key={`${row.keyword}-${result.llm}`} result={result} />
        ))}
    </>
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
    <div className="flex flex-wrap items-center gap-3 mb-4" style={FONT}>
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
        <option value="organic">Organic</option>
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

  const hasSubRows = rows.some((r) => (r.per_llm?.length ?? 0) > 0);

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
        {filtered.length < rows.length ? " (filtered)" : ""}
        {hasSubRows
          ? " · Dimmed rows = not mentioned by that LLM · Click excerpt to expand"
          : " · Click a row to see the AI response excerpt"}
      </p>
    </div>
  );
}
