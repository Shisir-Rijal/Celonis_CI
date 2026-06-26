import type { ColorSpectrumEntry, UsageLabel } from "@/lib/branding/types";
import { SpectrumEntryCard } from "./SpectrumEntryCard";

export function SpectrumColumn({
  usageLabel,
  entries,
  totalCompetitors,
}: {
  usageLabel: UsageLabel;
  entries: ColorSpectrumEntry[];
  totalCompetitors: number;
}) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <div className="flex items-center justify-between pb-2 border-b border-white/15">
        <span className="text-[11px] uppercase tracking-widest text-white font-medium">
          {usageLabel}
        </span>
        <span className="text-[10px] text-neutral-grey-20">{entries.length}</span>
      </div>
      {entries.length === 0 ? (
        <span className="text-[11px] text-neutral-grey-20 py-5">—</span>
      ) : (
        <div className="flex flex-col">
          {entries.map((entry) => (
            <SpectrumEntryCard key={entry.colorFamily} entry={entry} totalCompetitors={totalCompetitors} />
          ))}
        </div>
      )}
    </div>
  );
}
