"use client";

import { ChevronDown } from "lucide-react";

import { isHomeCompany } from "@/lib/competitors/highlight";
import type { CompetitorColorDiversity } from "@/lib/branding/types";
import { Swatch } from "./Swatch";

export function DiversityRow({
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
