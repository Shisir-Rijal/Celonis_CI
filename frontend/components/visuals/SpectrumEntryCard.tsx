import type { ColorSpectrumEntry } from "@/lib/branding/types";
import { CompanyChip } from "./CompanyChip";
import { Swatch } from "./Swatch";

export function SpectrumEntryCard({ entry }: { entry: ColorSpectrumEntry }) {
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
