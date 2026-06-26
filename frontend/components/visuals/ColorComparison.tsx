"use client";

import { useMemo, useState } from "react";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useColorInsights } from "@/lib/branding/hooks";
import type { UsageLabel } from "@/lib/branding/types";
import { DiversityRow } from "./DiversityRow";
import { HueWheel } from "./HueWheel";
import { SpectrumColumn } from "./SpectrumColumn";
import { WarmCoolCompanyList } from "./WarmCoolCompanyList";

const SPECTRUM_COLUMNS: UsageLabel[] = ["Very common", "Common", "Occasional", "Rare"];

type ColorTypeFilter = "all" | "primary" | "secondary";
const COLOR_TYPE_FILTERS: ColorTypeFilter[] = ["all", "primary", "secondary"];

// When a primary/secondary filter is active, a hue family's tier must be
// recomputed from the *filtered* company count, or a color could end up
// showing the same count as another color while still sitting in a higher
// tier it only qualified for via the usage the filter just hid (e.g. "Red"
// landing in "Common" from combined primary+secondary use, but still showing
// there once filtered down to just its 2 primary users — same count as a
// color that was only ever used by 2 companies in total). These thresholds
// are deliberately lower than the "all" ones below — a color counted under
// just one role naturally has a smaller company count than the same color
// counted under either role.
function usageLabelForFiltered(count: number): UsageLabel {
  if (count > 3) return "Very common";
  if (count === 3) return "Common";
  if (count === 2) return "Occasional";
  return "Rare";
}

// "All" mirrors colors.py's `_usage_label` thresholds exactly (the backend
// bucket a color's combined-palette count puts it in) — kept as a function
// here, rather than trusting the entry's pre-set usageLabel field, so the
// tier always reflects the *currently filtered* usedBy count consistently
// with the filtered case above.
function usageLabelForAll(count: number): UsageLabel {
  if (count > 6) return "Very common";
  if (count >= 5) return "Common";
  if (count >= 3) return "Occasional";
  return "Rare";
}

export function ColorComparison() {
  const { data, isLoading, isError, error } = useColorInsights();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [colorTypeFilter, setColorTypeFilter] = useState<ColorTypeFilter>("all");
  const [warmCoolFilter, setWarmCoolFilter] = useState<ColorTypeFilter>("all");
  const [diversityFilter, setDiversityFilter] = useState<ColorTypeFilter>("all");

  const columns = useMemo(() => {
    if (!data) return [];
    const filtered = data.spectrum
      .map((entry) => {
        const usedBy =
          colorTypeFilter === "all" ? entry.usedBy : entry.usedBy.filter((u) => u.colorType === colorTypeFilter);
        const usageLabel =
          colorTypeFilter === "all" ? usageLabelForAll(usedBy.length) : usageLabelForFiltered(usedBy.length);
        return { ...entry, usedBy, usageCount: usedBy.length, usageLabel };
      })
      .filter((entry) => entry.usedBy.length > 0);

    return SPECTRUM_COLUMNS.map((usageLabel) => ({
      usageLabel,
      entries: filtered.filter((entry) => entry.usageLabel === usageLabel),
    }));
  }, [data, colorTypeFilter]);

  const warmCoolSplit = useMemo(() => {
    if (!data) return { warmPct: 0, coolPct: 0, neutralPct: 0, warmCompanies: [], coolCompanies: [], neutralCompanies: [] };
    const field = warmCoolFilter === "all" ? "overall" : warmCoolFilter;
    const warmCompanies: string[] = [];
    const coolCompanies: string[] = [];
    const neutralCompanies: string[] = [];
    for (const entry of data.warmCoolBreakdown) {
      const temperature = entry[field];
      if (temperature === "warm") warmCompanies.push(entry.company);
      else if (temperature === "cool") coolCompanies.push(entry.company);
      else if (temperature === "neutral") neutralCompanies.push(entry.company);
      // null (no colors of this type for this company) — excluded entirely, not just uncounted.
    }
    const total = warmCompanies.length + coolCompanies.length + neutralCompanies.length;
    const pct = (count: number) => (total ? Math.round((count / total) * 1000) / 10 : 0);
    return {
      warmPct: pct(warmCompanies.length),
      coolPct: pct(coolCompanies.length),
      neutralPct: pct(neutralCompanies.length),
      warmCompanies,
      coolCompanies,
      neutralCompanies,
    };
  }, [data, warmCoolFilter]);

  const filteredDiversity = useMemo(() => {
    if (!data) return [];
    if (diversityFilter === "all") return data.diversity;
    return data.diversity.map((d) => {
      const secondary = new Set(d.secondaryHexes);
      const hues = d.hues
        .map((h) => ({
          ...h,
          colors: h.colors.filter((hex) => (diversityFilter === "secondary" ? secondary.has(hex) : !secondary.has(hex))),
        }))
        .filter((h) => h.colors.length > 0);
      return { ...d, hues };
    });
  }, [data, diversityFilter]);

  function toggleCompany(company: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(company)) next.delete(company);
      else next.add(company);
      return next;
    });
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <ZoneSkeleton height={260} />
        <ZoneSkeleton height={160} />
      </div>
    );
  }
  if (isError) {
    return <ZoneError message={(error as Error)?.message} />;
  }
  if (!data || data.spectrum.length === 0) {
    return <ZoneEmpty message="No color analysis available yet." />;
  }

  const maxDiversity = Math.max(1, ...filteredDiversity.map((d) => d.hues.length));

  return (
    <div className="flex flex-col gap-4">
      <DashboardCard label="Color Spectrum" sublabel="How heavily each hue family is used across tracked competitors, by frequency">
        <div className="flex items-center gap-1 bg-white/5 border border-white/10 rounded-full p-0.5 w-fit mb-4">
          {COLOR_TYPE_FILTERS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setColorTypeFilter(t)}
              className={`text-[11px] px-3 py-1 rounded-full capitalize transition-colors cursor-pointer ${
                colorTypeFilter === t
                  ? "bg-secondary-green text-primary-black font-medium"
                  : "text-neutral-grey-20 hover:text-primary-white"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {columns.map((col) => (
            <SpectrumColumn
              key={col.usageLabel}
              usageLabel={col.usageLabel}
              entries={col.entries}
              totalCompetitors={data.diversity.length}
            />
          ))}
        </div>
      </DashboardCard>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DashboardCard label="Color Diversity" sublabel="Click a competitor to see which exact colors make up each hue">
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-1 bg-white/5 border border-white/10 rounded-full p-0.5 w-fit">
              {COLOR_TYPE_FILTERS.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setDiversityFilter(t)}
                  className={`text-[11px] px-3 py-1 rounded-full capitalize transition-colors cursor-pointer ${
                    diversityFilter === t
                      ? "bg-secondary-green text-primary-black font-medium"
                      : "text-neutral-grey-20 hover:text-primary-white"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="flex flex-col gap-3">
              {filteredDiversity.map((d) => (
                <DiversityRow
                  key={d.company}
                  entry={d}
                  max={maxDiversity}
                  expanded={expanded.has(d.company)}
                  onToggle={() => toggleCompany(d.company)}
                />
              ))}
            </div>
          </div>
        </DashboardCard>

        <DashboardCard label="Warm vs. Cool" sublabel="Share of warm, cool, and neutral tones across all tracked palettes">
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-1 bg-white/5 border border-white/10 rounded-full p-0.5 w-fit">
              {COLOR_TYPE_FILTERS.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setWarmCoolFilter(t)}
                  className={`text-[11px] px-3 py-1 rounded-full capitalize transition-colors cursor-pointer ${
                    warmCoolFilter === t
                      ? "bg-secondary-green text-primary-black font-medium"
                      : "text-neutral-grey-20 hover:text-primary-white"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="flex h-3 rounded-full overflow-hidden bg-white/5">
              <div className="h-full bg-[#FA4616]" style={{ width: `${warmCoolSplit.warmPct}%` }} />
              <div className="h-full bg-[#1A73E8]" style={{ width: `${warmCoolSplit.coolPct}%` }} />
              <div className="h-full bg-white/30" style={{ width: `${warmCoolSplit.neutralPct}%` }} />
            </div>
            <div className="flex flex-col gap-3">
              <WarmCoolCompanyList
                label={`Warm ${warmCoolSplit.warmPct}%`}
                dotClass="bg-[#FA4616]"
                companies={warmCoolSplit.warmCompanies}
              />
              <WarmCoolCompanyList
                label={`Cool ${warmCoolSplit.coolPct}%`}
                dotClass="bg-[#1A73E8]"
                companies={warmCoolSplit.coolCompanies}
              />
              <WarmCoolCompanyList
                label={`Neutral ${warmCoolSplit.neutralPct}%`}
                dotClass="bg-white/30"
                companies={warmCoolSplit.neutralCompanies}
              />
            </div>
          </div>
        </DashboardCard>
      </div>

      <DashboardCard label="Hue Wheel" sublabel="Where every tracked color falls on the color wheel">
        <HueWheel spectrum={data.spectrum} />
      </DashboardCard>
    </div>
  );
}
