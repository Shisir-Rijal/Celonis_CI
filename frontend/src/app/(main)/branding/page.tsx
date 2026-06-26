"use client";

import { useMemo } from "react";

import PageToolbar from "@components/geo/PageToolbar";
import SectionWrapper from "@components/ui/SectionWrapper";
import { BrandingOverview } from "@components/visuals/BrandingOverview";
import { ColorComparison } from "@components/visuals/ColorComparison";
import { FontComparison } from "@components/visuals/FontComparison";
import { FontDimensionBreakdown } from "@components/visuals/FontDimensionBreakdown";
import { FontDiversity } from "@components/visuals/FontDiversity";
import { FontArchetypes } from "@components/visuals/FontArchetypes";
import { ImageryArchetypes } from "@components/visuals/ImageryArchetypes";
import { ArchetypesSlider, FixedArchetypesSlider } from '@components/visuals/ArchetypesSlider'
import { ImageryDimensionBreakdown } from "@components/visuals/ImageryDimensionBreakdown";
import { ImagerySimilarityNetwork } from "@components/visuals/charts/ImagerySimilarityNetwork";
import { LogoDimensionBreakdown } from "@components/visuals/LogoDimensionBreakdown";
import { LogoPlacementGrid } from "@components/visuals/LogoPlacementGrid";
import { VisualTrendCards } from "@components/visuals/VisualTrendCards";
import { useBrandArchetypes } from "@/lib/branding/hooks";

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
  const { data } = useBrandArchetypes();
  const updatedAt = useMemo(
    () => formatRelativeTime(data?.generatedAt),
    [data?.generatedAt]
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
            Visual Branding
          </h1>
          <p className="mt-2 text-sm text-neutral-grey-20 max-w-xl">
            Recently scraped branding from Celonis and its tracked competitors —{" "}
            <span className="text-primary-white font-medium">
              from Celonis and its tracked competitors
            </span>{" "}
            from their domain.
          </p>
        </div>
        <PageToolbar runtime="every 6 months" updatedAt={updatedAt} agentsRunning={1} />
      </header>

      {/* Zone 1 — Trending */}
      <SectionWrapper
        label="Visual Trends"
        description="High-level branding presence across all tracked competitors."
      >
        <VisualTrendCards />
      </SectionWrapper>

      {/* Zone 2 — Overview */}
      <SectionWrapper
        label="Branding Cards"
        description="Scraped visual identity across tracked competitors — scraped from their website."
      >
        <BrandingOverview />
      </SectionWrapper>

      {/* Zone 3 — Archetypes */}
      <SectionWrapper
        label="Archetypes"
        description="Scraped visual identity across tracked competitors — scraped from their website."
      >
        <ArchetypesSlider />
      </SectionWrapper>

      {/* Zone 3b — Marketing Archetypes (12 fixed Mark & Pearson archetypes) */}
      <SectionWrapper
        label="Marketing Archetypes"
        description="Same visual identity data, classified into the 12 established brand archetypes (Innocent, Sage, Hero, ...) instead of freely-named clusters."
      >
        <FixedArchetypesSlider />
      </SectionWrapper>

      {/* Zone 4 — Colors */}
      <SectionWrapper
        label="Colors"
        description="Analysis of brand colors"
      >
        <ColorComparison />
      </SectionWrapper>

      {/* Zone 5 — Fonts */}
      <SectionWrapper
        label="Fonts"
        description="Analysis of brand fonts"
      >
        <div className="flex flex-col gap-4">
          <FontArchetypes />
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <FontDimensionBreakdown />
            <FontDiversity />
          </div>
          <FontComparison />
        </div>
      </SectionWrapper>

      {/* Zone 6 — Logos */}
      <SectionWrapper
        label="Logos"
        description="Analysis of brand logos"
      >
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <LogoDimensionBreakdown />
          <LogoPlacementGrid />
        </div>
      </SectionWrapper>

      {/* Zone 7 — Imagery */}
      <SectionWrapper
        label="Images"
        description="Analysis of imagery"
      >
        <div className="flex flex-col gap-4">
          <ImageryArchetypes />
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <ImageryDimensionBreakdown />
            <ImagerySimilarityNetwork />
          </div>
        </div>
      </SectionWrapper>


    </div>
  );
}
