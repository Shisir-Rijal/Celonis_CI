"use client";

import { isHomeCompany } from "@/lib/competitors/highlight";

/**
 * Pill used to label a company wherever competitors are listed side by
 * side (color usage, diversity, fonts, ...). Celonis always gets a green
 * highlight so our own brand stands out from the competitor set — keep
 * using this component for any new section that lists companies so the
 * highlight stays consistent.
 */
export function CompanyChip({
  company,
  hex,
  light,
}: {
  company: string;
  hex?: string;
  /** Use on white/light card surfaces (e.g. imagery previews) instead of the default dark surface. */
  light?: boolean;
}) {
  const home = isHomeCompany(company);

  return (
    <span
      title={hex}
      className={`flex items-center gap-1.5 text-[11px] rounded-full py-0.5 border ${
        hex ? "pl-1 pr-2" : "px-2"
      } ${
        home
          ? "border-secondary-green text-secondary-green bg-secondary-green/10"
          : light
            ? "border-black/10 text-neutral-grey-30 bg-black/5"
            : "border-white/10 text-neutral-grey-10 bg-white/5"
      }`}
    >
      {hex && (
        <span
          className={`rounded-xs shrink-0 ${home ? "ring-1 ring-secondary-green" : ""}`}
          style={{ backgroundColor: hex, width: 12, height: 12 }}
        />
      )}
      {company}
    </span>
  );
}
