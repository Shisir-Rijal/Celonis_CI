"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

/**
 * Dropdown to pick one of `companies` and preview its actual logo image,
 * resolved from `logoUrls`. Used anywhere a bucket only lists company names
 * (logo placement positions, logo dimension categories) but a reviewer also
 * wants to see which logo a given company actually has.
 */
export function CompanyLogoDropdown({
  companies,
  logoUrls,
}: {
  companies: string[];
  logoUrls: Record<string, string>;
}) {
  const [selected, setSelected] = useState(companies[0] ?? "");
  const logoUrl = logoUrls[selected];

  if (companies.length === 0) return null;

  return (
    <div className="flex items-center gap-2.5">
      <div className="relative">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="appearance-none text-[11px] pl-2.5 pr-6 py-1 rounded-full bg-white/5 border border-white/10 text-neutral-grey-10 cursor-pointer hover:border-white/25 transition-colors focus:outline-none"
        >
          {companies.map((c) => (
            <option key={c} value={c} className="bg-neutral-grey-30 text-primary-white">
              {c}
            </option>
          ))}
        </select>
        <ChevronDown
          size={11}
          className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-neutral-grey-20"
        />
      </div>
      <div className="w-9 h-9 rounded-md bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden shrink-0">
        {logoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={logoUrl} alt={`${selected} logo`} className="max-w-full max-h-full object-contain" />
        ) : (
          <span className="text-[9px] text-neutral-grey-20">N/A</span>
        )}
      </div>
    </div>
  );
}
