"use client";

import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useLogoDimensions } from "@/lib/branding/hooks";
import { DimensionBreakdownPanel } from "./DimensionBreakdownPanel";

export function LogoDimensionBreakdown() {
  const { data, isLoading, isError, error } = useLogoDimensions();

  if (isLoading) return <ZoneSkeleton height={320} />;
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.dimensions.length === 0) {
    return <ZoneEmpty message="No logo dimension analysis available yet." />;
  }

  return (
    <DimensionBreakdownPanel
      label="Logo Dimensions"
      sublabel="How tracked competitors' logos break down across type, color, shape style, and signal shape"
      dimensions={data.dimensions}
    />
  );
}
