"use client";

import DashboardCard from "@components/geo/DashboardCard";
import { CompanyChip } from "./CompanyChip";
import type { BrandArchetype } from "@/lib/branding/types";

/**
 * One holistic brand archetype — synthesized across color/font/logo/
 * imagery/video analysis (backend/app/agents/visualbranding/nodes/archetypes.py),
 * not tied to a single visual dimension. Can represent a single company.
 */
export function ArchetypeCard({ archetype }: { archetype: BrandArchetype }) {
  return (
    <DashboardCard className="flex flex-row gap-40 min-w-200 max-w-200 min-h-100 max-h-100 shrink-0 bg-white">
      {archetype.image && (
        <div className="aspect-4/3 w-80 shrink-0 rounded-sm bg-black/5 border border-black/10 overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={archetype.image} alt={archetype.name} className="w-full h-full object-cover" />
        </div>
      )}
      <div className="flex flex-col gap-3 min-w-0">
        {archetype.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
            {archetype.keywords.map((keyword) => (
                <span
                key={keyword}
                className="text-[12px] tracking-wide px-2 py-0.5 rounded-xs bg-neutral-grey-20 text-primary-black"
                >
                {keyword}
                </span>
            ))}
            </div>
        )}

        
        <span className="text-2xl font-medium text-primary-black">{archetype.name}</span>
        <p className="text-sm text-neutral-grey-20 leading-relaxed">{archetype.vibe}</p>
        <div className="flex flex-col gap-1.5 text-sm text-neutral-grey-20 overflow-y-auto">
            {archetype.traits.map((t) => (
            <span key={t.topic}>
                <span className="text-primary-black font-medium">{t.topic} — </span>
                {t.description}
            </span>
            ))}
        </div>
        <div className="flex flex-wrap gap-1.5 mt-auto pt-2 border-xs border-grey-10">
            {archetype.companies.map((c) => (
            <CompanyChip key={c} company={c} light />
            ))}
        </div>
      </div>
    </DashboardCard>
  );
}
