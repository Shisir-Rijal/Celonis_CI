"use client";

import { useState } from "react";

import DashboardCard from "@components/geo/DashboardCard";
import type { DimensionCategory } from "@/lib/branding/types";
import { CompanyChip } from "./CompanyChip";
import { ExampleImageRow } from "./ExampleImageRow";

type Dimension = {
  key: string;
  label: string;
  categories: DimensionCategory[];
};

function CategoryBar({
  category,
  max,
  previewUrls,
  previewNoun,
}: {
  category: DimensionCategory;
  max: number;
  /** Lets each bucket preview the actual logo/image behind a company. */
  previewUrls?: Record<string, string[]>;
  previewNoun?: string;
}) {
  const width = max > 0 ? (category.pct / max) * 100 : 0;
  return (
    <div className="flex flex-col gap-1.5 py-2.5 border-b border-white/8 last:border-b-0">
      <div className="flex items-center gap-3">
        <span className="text-sm text-primary-white w-44 shrink-0 truncate">{category.category}</span>
        <span className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
          <span className="block h-full rounded-full bg-secondary-green" style={{ width: `${width}%` }} />
        </span>
        <span className="text-[11px] text-neutral-grey-20 w-9 text-right shrink-0">{category.pct}%</span>
      </div>
      {category.companies.length > 0 && (
        <div className="flex flex-col gap-2 pl-1">
          <div className="flex flex-wrap gap-1.5">
            {category.companies.map((c) => (
              <CompanyChip key={c} company={c} />
            ))}
          </div>
          {previewUrls && (
            <ExampleImageRow companies={category.companies} imageUrls={previewUrls} noun={previewNoun} />
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Tabbed "category breakdown" used for every "how do tracked competitors
 * split across X" dimension — imagery style/effect/subject/look & feel/color
 * scheme, logo type/color/shape style/signal shape, etc. Pass the dimensions
 * straight from the relevant hook; this component only renders them.
 */
export function DimensionBreakdownPanel({
  label,
  sublabel,
  dimensions,
  previewUrls,
  previewNoun,
}: {
  label: string;
  sublabel: string;
  dimensions: Dimension[];
  /** Lets each bucket preview the actual logo/image behind a company. */
  previewUrls?: Record<string, string[]>;
  previewNoun?: string;
}) {
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const active = dimensions.find((d) => d.key === activeKey) ?? dimensions[0];
  const max = Math.max(1, ...active.categories.map((c) => c.pct));

  return (
    <DashboardCard label={label} sublabel={sublabel}>
      <div className="flex flex-col gap-5">
        <div className="flex items-center gap-1 flex-wrap bg-white/5 border border-white/10 rounded-full p-0.5 w-fit">
          {dimensions.map((d) => (
            <button
              key={d.key}
              type="button"
              onClick={() => setActiveKey(d.key)}
              className={`text-[11px] px-3 py-1 rounded-full transition-colors cursor-pointer ${
                active.key === d.key
                  ? "bg-secondary-green text-primary-black font-medium"
                  : "text-neutral-grey-20 hover:text-primary-white"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>
        <div className="flex flex-col">
          {active.categories.map((category) => (
            <CategoryBar
              key={category.category}
              category={category}
              max={max}
              previewUrls={previewUrls}
              previewNoun={previewNoun}
            />
          ))}
        </div>
      </div>
    </DashboardCard>
  );
}
