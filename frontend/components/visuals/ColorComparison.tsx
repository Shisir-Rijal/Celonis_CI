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

export function ColorComparison() {
  const { data, isLoading, isError, error } = useColorInsights();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const columns = useMemo(() => {
    if (!data) return [];
    return SPECTRUM_COLUMNS.map((usageLabel) => ({
      usageLabel,
      entries: data.spectrum.filter((entry) => entry.usageLabel === usageLabel),
    }));
  }, [data]);

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

  const maxDiversity = Math.max(1, ...data.diversity.map((d) => d.hues.length));

  return (
    <div className="flex flex-col gap-4">
      <DashboardCard label="Color Spectrum" sublabel="How heavily each hue family is used across tracked competitors, by frequency">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
          {columns.map((col) => (
            <SpectrumColumn key={col.usageLabel} usageLabel={col.usageLabel} entries={col.entries} />
          ))}
        </div>
      </DashboardCard>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DashboardCard label="Color Diversity" sublabel="Click a competitor to see which exact colors make up each hue">
          <div className="flex flex-col gap-3">
            {data.diversity.map((d) => (
              <DiversityRow
                key={d.company}
                entry={d}
                max={maxDiversity}
                expanded={expanded.has(d.company)}
                onToggle={() => toggleCompany(d.company)}
              />
            ))}
          </div>
        </DashboardCard>

        <DashboardCard label="Warm vs. Cool" sublabel="Share of warm, cool, and neutral tones across all tracked palettes">
          <div className="flex flex-col gap-4">
            <div className="flex h-3 rounded-full overflow-hidden bg-white/5">
              <div className="h-full bg-[#FA4616]" style={{ width: `${data.warmCoolSplit.warmPct}%` }} />
              <div className="h-full bg-[#1A73E8]" style={{ width: `${data.warmCoolSplit.coolPct}%` }} />
              <div className="h-full bg-white/30" style={{ width: `${data.warmCoolSplit.neutralPct}%` }} />
            </div>
            <div className="flex flex-col gap-3">
              <WarmCoolCompanyList
                label={`Warm ${data.warmCoolSplit.warmPct}%`}
                dotClass="bg-[#FA4616]"
                companies={data.warmCoolSplit.warmCompanies}
              />
              <WarmCoolCompanyList
                label={`Cool ${data.warmCoolSplit.coolPct}%`}
                dotClass="bg-[#1A73E8]"
                companies={data.warmCoolSplit.coolCompanies}
              />
              <WarmCoolCompanyList
                label={`Neutral ${data.warmCoolSplit.neutralPct}%`}
                dotClass="bg-white/30"
                companies={data.warmCoolSplit.neutralCompanies}
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
