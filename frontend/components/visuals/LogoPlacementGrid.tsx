"use client";

import { useMemo, useState } from "react";
import { EyeOff } from "lucide-react";

import DashboardCard from "@components/geo/DashboardCard";
import { ZoneSkeleton, ZoneError, ZoneEmpty } from "@components/geo/ZoneState";
import { useLogoPlacement } from "@/lib/branding/hooks";
import type { LogoPlacementEntry, LogoPlacementPosition } from "@/lib/branding/types";
import { CompanyChip } from "./CompanyChip";

const GRID_LAYOUT: (LogoPlacementPosition | null)[] = [
  "top-left",
  "top-center",
  "top-right",
  null,
  "center",
  null,
  "bottom-left",
  "bottom-center",
  "bottom-right",
];

const POSITION_LABELS: Record<LogoPlacementPosition, string> = {
  "top-left": "Top left",
  "top-center": "Top center",
  "top-right": "Top right",
  center: "Centered",
  "bottom-left": "Bottom left",
  "bottom-center": "Bottom center",
  "bottom-right": "Bottom right",
  "not-present": "Not present",
};

function GridCell({
  entry,
  max,
  selected,
  onSelect,
}: {
  entry: LogoPlacementEntry;
  max: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const intensity = max > 0 ? entry.pct / max : 0;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`aspect-square rounded-md border flex flex-col items-center justify-center gap-1 transition-colors cursor-pointer ${
        selected ? "border-secondary-green" : "border-white/10 hover:border-white/25"
      }`}
      style={{ backgroundColor: `rgba(92, 254, 80, ${0.08 + intensity * 0.32})` }}
    >
      <span className="text-sm font-medium text-primary-white">{entry.pct}%</span>
      <span className="text-[10px] text-neutral-grey-20 text-center px-1">
        {POSITION_LABELS[entry.position]}
      </span>
    </button>
  );
}

export function LogoPlacementGrid() {
  const { data, isLoading, isError, error } = useLogoPlacement();
  const [selected, setSelected] = useState<LogoPlacementPosition | null>(null);

  const byPosition = useMemo(() => {
    const map = new Map<LogoPlacementPosition, LogoPlacementEntry>();
    data?.positions.forEach((p) => map.set(p.position, p));
    return map;
  }, [data]);

  if (isLoading) return <ZoneSkeleton height={320} />;
  if (isError) return <ZoneError message={(error as Error)?.message} />;
  if (!data || data.positions.length === 0) {
    return <ZoneEmpty message="No logo placement analysis available yet." />;
  }

  const notPresent = byPosition.get("not-present");
  const spatial = data.positions.filter((p) => p.position !== "not-present");
  const max = Math.max(1, ...spatial.map((p) => p.pct));
  const activePosition = selected ?? spatial.reduce((a, b) => (b.pct > a.pct ? b : a)).position;
  const activeEntry = byPosition.get(activePosition);

  return (
    <DashboardCard
      label="Logo Placement"
      sublabel="Where competitors place their logo on marketing imagery — click a cell to see who"
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-3 gap-2 max-w-[280px]">
          {GRID_LAYOUT.map((position, i) => {
            if (!position) return <div key={`empty-${i}`} />;
            const entry = byPosition.get(position);
            if (!entry) return <div key={`empty-${i}`} />;
            return (
              <GridCell
                key={position}
                entry={entry}
                max={max}
                selected={activePosition === position}
                onSelect={() => setSelected(position)}
              />
            );
          })}
        </div>

        {activeEntry && (
          <div className="flex flex-col gap-1.5">
            <span className="text-xs text-neutral-grey-20">
              {POSITION_LABELS[activeEntry.position]} — {activeEntry.pct}%
            </span>
            {activeEntry.companies.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {activeEntry.companies.map((c) => (
                  <CompanyChip key={c} company={c} />
                ))}
              </div>
            ) : (
              <span className="text-[11px] text-neutral-grey-20">No tracked competitor favors this spot.</span>
            )}
          </div>
        )}

        {notPresent && (
          <div className="flex items-center gap-3 pt-3 border-t border-white/8">
            <EyeOff size={14} className="text-neutral-grey-20 shrink-0" />
            <span className="text-xs text-neutral-grey-20 shrink-0">
              Logo missing entirely on {notPresent.pct}% of analyzed imagery
            </span>
            <div className="flex flex-wrap gap-1.5">
              {notPresent.companies.map((c) => (
                <CompanyChip key={c} company={c} />
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardCard>
  );
}
