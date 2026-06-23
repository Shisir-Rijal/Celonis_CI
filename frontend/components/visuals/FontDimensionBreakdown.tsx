"use client";

import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useFontInsights } from "@/lib/branding/hooks";
import { DimensionBreakdownPanel } from "./DimensionBreakdownPanel";

export function FontDimensionBreakdown() {
  const { data, isLoading, isError, error } = useFontInsights();

  if (isLoading) return <ZoneSkeleton height={320} />;
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.dimensions.length === 0) {
    return <ZoneEmpty message="No font dimension analysis available yet." />;
  }

  return (
    <DimensionBreakdownPanel
      label="Font Dimensions"
      sublabel="How tracked competitors' fonts break down across style, weight, size, and personality"
      dimensions={data.dimensions}
    />
  );
}
