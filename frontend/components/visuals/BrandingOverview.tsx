"use client";

import { useMemo, useState } from "react";

import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useVisuals } from "@/lib/visuals/hooks";
import { useCompetitorColors } from "@/lib/competitors/hooks";
import { getCompetitorColor } from "@/lib/competitors/colors";
import { CompetitorBrandingCard, ELEMENT_OPTIONS, type Element } from "./CompetitorBrandingCard";
import { Lightbox, type Gallery } from "./Lightbox";
import { MultiSelectFilter } from "./MultiSelectFilter";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BrandingOverview() {
  const { data, isLoading, isError, error } = useVisuals();
  const { data: brandColors = {} } = useCompetitorColors();

  const [competitors, setCompetitors] = useState<string[]>([]);
  const [selectedElements, setSelectedElements] = useState<string[]>([]);
  const [gallery, setGallery] = useState<Gallery | null>(null);

  const allCompanies = useMemo(
    () => [...new Set((data?.visuals ?? []).map((v) => v.company))].sort(),
    [data]
  );

  const elements: Element[] =
    selectedElements.length > 0
      ? (selectedElements as Element[])
      : ELEMENT_OPTIONS.map((o) => o.value);

  const filtered = useMemo(
    () =>
      (data?.visuals ?? []).filter(
        (v) => competitors.length === 0 || competitors.includes(v.company)
      ),
    [data, competitors]
  );

  const hasFilter = competitors.length > 0 || selectedElements.length > 0;

  function clearFilters() {
    setCompetitors([]);
    setSelectedElements([]);
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-[11px] text-neutral-grey-20 uppercase tracking-[0.12em] font-medium">
          Filter
        </span>

        <MultiSelectFilter
          label="Brands"
          options={allCompanies.map((c) => ({ value: c, label: c }))}
          selected={competitors}
          onChange={setCompetitors}
        />

        <MultiSelectFilter
          label="Elements"
          options={ELEMENT_OPTIONS}
          selected={selectedElements}
          onChange={setSelectedElements}
        />

        {hasFilter && (
          <button
            type="button"
            onClick={clearFilters}
            className="text-xs text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer"
          >
            Clear filters ×
          </button>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <ZoneSkeleton key={i} height={220} />
          ))}
        </div>
      ) : isError ? (
        <ZoneError message={(error as Error)?.message} />
      ) : !filtered.length ? (
        <ZoneEmpty
          message={
            hasFilter
              ? "No competitors match the selected filters."
              : "No visuals scraped yet."
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((item) => (
            <CompetitorBrandingCard
              key={item.company}
              item={item}
              elements={elements}
              accent={getCompetitorColor(item.company, allCompanies, brandColors)}
              onOpenGallery={(items, index, alt, bg) => setGallery({ items, index, alt, bg })}
            />
          ))}
        </div>
      )}

      {gallery && (
        <Lightbox
          gallery={gallery}
          onClose={() => setGallery(null)}
          onIndexChange={(index) => setGallery((g) => (g ? { ...g, index } : g))}
        />
      )}
    </div>
  );
}
