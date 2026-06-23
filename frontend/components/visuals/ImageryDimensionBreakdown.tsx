"use client";

import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useImageryDimensions } from "@/lib/branding/hooks";
import { DimensionBreakdownPanel } from "./DimensionBreakdownPanel";

export function ImageryDimensionBreakdown() {
  const { data, isLoading, isError, error } = useImageryDimensions();

  if (isLoading) return <ZoneSkeleton height={320} />;
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.dimensions.length === 0) {
    return <ZoneEmpty message="No imagery dimension analysis available yet." />;
  }

  return (
    <DimensionBreakdownPanel
      label="Imagery Dimensions"
      sublabel="How tracked competitors' imagery breaks down across style, effect, subject matter, look & feel, and color scheme"
      dimensions={data.dimensions}
      previewUrls={data.imageSamples}
      previewNoun="images"
    />
  );
}
