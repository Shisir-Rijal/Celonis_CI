"use client";

import { getCompetitorColor } from "@/lib/competitors/colors";
import { useCompetitorColors } from "@/lib/competitors/hooks";

type CompanyOption = {
  domain: string;
  name: string;
};

type CompanyChipFilterProps = {
  options: CompanyOption[];
  selected: string[]; // domains
  onChange: (selected: string[]) => void;
};

export default function CompanyChipFilter({
  options,
  selected,
  onChange,
}: CompanyChipFilterProps) {
  const { data: brandColors = {} } = useCompetitorColors();
  const allDomains = options.map((o) => o.domain);
  const isAllSelected = selected.length === 0;

  function toggle(domain: string) {
    if (selected.includes(domain)) {
      onChange(selected.filter((d) => d !== domain));
    } else {
      onChange([...selected, domain]);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => onChange([])}
        className={`text-xs font-medium px-3 py-1.5 rounded-full border transition-colors ${
          isAllSelected
            ? "bg-secondary-green text-primary-black border-secondary-green"
            : "bg-transparent text-neutral-grey-10 border-white/15 hover:border-white/30"
        }`}
      >
        All
      </button>

      {options.map((opt) => {
        const isSelected = selected.includes(opt.domain);
        const color = getCompetitorColor(opt.domain, allDomains, brandColors);
        return (
          <button
            key={opt.domain}
            type="button"
            onClick={() => toggle(opt.domain)}
            className="text-xs font-medium px-3 py-1.5 rounded-full border transition-colors"
            style={
              isSelected
                ? { backgroundColor: `${color}26`, color, borderColor: color }
                : undefined
            }
          >
            <span
              className={
                isSelected
                  ? ""
                  : "text-neutral-grey-10 border-white/15 hover:border-white/30"
              }
            >
              {opt.name}
              {isSelected && " ✓"}
            </span>
          </button>
        );
      })}
    </div>
  );
}