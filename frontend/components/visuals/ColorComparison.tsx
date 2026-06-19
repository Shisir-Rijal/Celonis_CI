"use client";

import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useColorInsights } from "@/lib/branding/hooks";
import { isHomeCompany } from "@/lib/competitors/highlight";
import type { ColorSpectrumEntry, CompetitorColorDiversity, UsageLabel } from "@/lib/branding/types";
import { CompanyChip } from "./CompanyChip";

const SPECTRUM_COLUMNS: UsageLabel[] = ["Very common", "Common", "Occasional", "Rare"];

/** Hue angle (0-360) for a hex color, or null for achromatic colors (black/white/grey) that have no meaningful hue. */
function hexToHue(hex: string): number | null {
  const clean = hex.replace("#", "");
  if (clean.length !== 6) return null;
  const r = parseInt(clean.slice(0, 2), 16) / 255;
  const g = parseInt(clean.slice(2, 4), 16) / 255;
  const b = parseInt(clean.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  if (delta < 0.04) return null;
  let hue: number;
  if (max === r) hue = ((g - b) / delta) % 6;
  else if (max === g) hue = (b - r) / delta + 2;
  else hue = (r - g) / delta + 4;
  hue *= 60;
  if (hue < 0) hue += 360;
  return hue;
}

function Swatch({ hex, size = 7 }: { hex: string; size?: number }) {
  return (
    <span
      aria-label={hex}
      title={hex}
      className="rounded-full border border-white/15 shrink-0"
      style={{ backgroundColor: hex, width: size * 4, height: size * 4 }}
    />
  );
}

function SpectrumEntryCard({ entry }: { entry: ColorSpectrumEntry }) {
  return (
    <div className="flex flex-col gap-2 py-3 border-b border-white/8 last:border-b-0">
      <div className="flex items-center gap-2">
        <Swatch hex={entry.representativeHex} size={6} />
        <span className="text-sm font-medium text-primary-white truncate">{entry.colorFamily}</span>
      </div>
      {entry.usedBy.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5 pl-1">
          {entry.usedBy.map((u) => (
            <CompanyChip key={u.company} company={u.company} hex={u.hex} />
          ))}
        </div>
      ) : (
        <span className="text-[11px] text-neutral-grey-20 pl-1">Unused — no competitor claims this color.</span>
      )}
      {entry.association && (
        <p className="text-[11px] text-neutral-grey-20 leading-relaxed">{entry.association}</p>
      )}
    </div>
  );
}

function SpectrumColumn({ usageLabel, entries }: { usageLabel: UsageLabel; entries: ColorSpectrumEntry[] }) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <div className="flex items-center justify-between pb-2 border-b border-white/15">
        <span className="text-[11px] uppercase tracking-widest text-neutral-grey-20 font-medium">
          {usageLabel}
        </span>
        <span className="text-[10px] text-neutral-grey-20">{entries.length}</span>
      </div>
      {entries.length === 0 ? (
        <span className="text-[11px] text-neutral-grey-20 py-3">—</span>
      ) : (
        <div className="flex flex-col">
          {entries.map((entry) => (
            <SpectrumEntryCard key={entry.colorFamily} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}

function DiversityRow({
  entry,
  max,
  expanded,
  onToggle,
}: {
  entry: CompetitorColorDiversity;
  max: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const home = isHomeCompany(entry.company);
  const count = entry.hues.length;
  const pct = max > 0 ? (count / max) * 100 : 0;

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex items-center gap-3 w-full text-left cursor-pointer group"
      >
        <span
          className={`text-xs w-28 truncate shrink-0 ${
            home ? "text-secondary-green font-medium" : "text-neutral-grey-10"
          }`}
        >
          {entry.company}
        </span>
        <span
          className={`flex-1 h-2 rounded-full bg-white/5 overflow-hidden ${
            home ? "ring-1 ring-secondary-green" : ""
          }`}
        >
          <span
            className={`block h-full rounded-full ${home ? "bg-secondary-green" : "bg-white/30"}`}
            style={{ width: `${pct}%` }}
          />
        </span>
        <span className="text-[11px] text-neutral-grey-20 w-5 text-right shrink-0">{count}</span>
        <ChevronDown
          size={14}
          className={`text-neutral-grey-20 group-hover:text-primary-white transition-transform shrink-0 ${
            expanded ? "" : "-rotate-90"
          }`}
        />
      </button>

      {expanded && (
        <div className="flex flex-col gap-2 pl-29 pb-1">
          {entry.hues.map((hue) => (
            <div key={hue.hueFamily} className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] text-neutral-grey-20 uppercase tracking-wide w-24 shrink-0">
                {hue.hueFamily}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {hue.colors.map((hex) => (
                  <span
                    key={hex}
                    title={hex}
                    className="flex items-center gap-1 text-[10px] text-neutral-grey-10 bg-white/5 border border-white/10 rounded-full pl-1 pr-1.5 py-0.5"
                  >
                    <Swatch hex={hex} size={3} />
                    {hex}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function WarmCoolCompanyList({ label, dotClass, companies }: { label: string; dotClass: string; companies: string[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="flex items-center gap-1.5 text-[11px] text-neutral-grey-20">
        <span className={`w-2 h-2 rounded-full ${dotClass}`} /> {label}
      </span>
      <div className="flex flex-wrap gap-1.5 pl-3.5">
        {companies.map((c) => (
          <CompanyChip key={c} company={c} />
        ))}
      </div>
    </div>
  );
}

type ColorTypeFilter = "primary" | "secondary";

function HueWheel({ spectrum }: { spectrum: ColorSpectrumEntry[] }) {
  const [colorType, setColorType] = useState<ColorTypeFilter>("primary");

  const points = useMemo(() => {
    return spectrum
      .flatMap((entry) =>
        entry.usedBy
          .filter((u) => u.colorType === colorType)
          .map((u) => ({ company: u.company, hex: u.hex }))
      )
      .map((p) => ({ ...p, hue: hexToHue(p.hex) }))
      .filter((p): p is { company: string; hex: string; hue: number } => p.hue !== null);
  }, [spectrum, colorType]);

  const radius = 150;
  const labelGap = 16;
  const size = radius * 2 + 220;
  const center = size / 2;

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="flex items-center gap-1 bg-white/5 border border-white/10 rounded-full p-0.5">
        {(["primary", "secondary"] as ColorTypeFilter[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setColorType(t)}
            className={`text-[11px] px-3 py-1 rounded-full capitalize transition-colors cursor-pointer ${
              colorType === t
                ? "bg-secondary-green text-primary-black font-medium"
                : "text-neutral-grey-20 hover:text-primary-white"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {!points.length ? (
        <ZoneEmpty message={`No chromatic ${colorType} colors to plot yet.`} />
      ) : (
        <div className="relative" style={{ width: size, height: size }}>
          <div
            className="absolute rounded-full opacity-25"
            style={{
              left: center - radius,
              top: center - radius,
              width: radius * 2,
              height: radius * 2,
              background: "conic-gradient(red, orange, yellow, lime, green, cyan, blue, violet, magenta, red)",
            }}
          />
          <div
            className="absolute rounded-full bg-neutral-grey-30"
            style={{
              left: center - radius + 16,
              top: center - radius + 16,
              width: (radius - 16) * 2,
              height: (radius - 16) * 2,
            }}
          />
          {points.map((p, i) => {
            const angleRad = (p.hue * Math.PI) / 180;
            const cos = Math.cos(angleRad);
            const sin = Math.sin(angleRad);
            const x = center + radius * cos;
            const y = center + radius * sin;
            const labelX = center + (radius + labelGap) * cos;
            const labelY = center + (radius + labelGap) * sin;
            const home = isHomeCompany(p.company);
            const rightHalf = cos >= 0;

            return (
              <span key={`${p.company}-${i}`}>
                <span
                  title={`${p.company} · ${p.hex}`}
                  className={`absolute rounded-full shrink-0 ${
                    home ? "ring-2 ring-secondary-green" : "border border-white/30"
                  }`}
                  style={{ backgroundColor: p.hex, width: 14, height: 14, left: x - 7, top: y - 7 }}
                />
                <span
                  className={`absolute whitespace-nowrap text-[11px] ${
                    home ? "text-secondary-green font-medium" : "text-neutral-grey-10"
                  }`}
                  style={{
                    left: labelX,
                    top: labelY,
                    transform: rightHalf ? "translate(0, -50%)" : "translate(-100%, -50%)",
                  }}
                >
                  {p.company}
                </span>
              </span>
            );
          })}
        </div>
      )}

      <p className="text-[11px] text-neutral-grey-20 text-center max-w-xs">
        Each dot is one competitor&apos;s {colorType} color, positioned by its actual hue angle —
        tight clusters show where the market converges, empty arcs show whitespace.
      </p>
    </div>
  );
}

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
