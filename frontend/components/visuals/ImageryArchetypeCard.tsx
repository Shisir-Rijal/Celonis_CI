"use client";

import DashboardCard from "@components/geo/DashboardCard";
import { CompanyChip } from "./CompanyChip";
import type { ImageryArchetype } from "@/lib/branding/types";

export function ImageryArchetypeCard({ archetype }: { archetype: ImageryArchetype }) {
  return (
    <DashboardCard className="flex flex-col gap-3 bg-primary-white border-black/8 w-72 shrink-0">
      <div className="aspect-[4/3] rounded-md bg-black/5 border border-black/10 overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={archetype.image} alt={archetype.name} className="w-full h-full object-cover" />
      </div>
      <span className="text-sm font-medium text-primary-black">{archetype.name}</span>
      <p className="text-xs text-neutral-grey-20 leading-relaxed">{archetype.description}</p>
      <div className="flex flex-wrap gap-1.5 mt-auto">
        {archetype.companies.map((c) => (
          <CompanyChip key={c} company={c} light />
        ))}
      </div>
    </DashboardCard>
  );
}
