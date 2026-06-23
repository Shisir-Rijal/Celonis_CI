"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

/**
 * Dropdown-arrow disclosure that reveals every company's example image(s)
 * side by side, all at once — no per-brand filter/select. Mirrors how
 * ImagerySimilarityNetwork's detail panel lines up sample images for a pair
 * of companies, just for an arbitrary-size bucket of companies instead.
 *
 * Used by both logo dimensions (one logo per company) and imagery dimensions
 * (a few sample images per company — the same ones the vision classifier
 * looked at, so showing only one would risk showing the one outlier image
 * that *doesn't* support the bucket's classification, e.g. a mascot image
 * under "Abstract shapes" when the verdict was actually based on the
 * company's other, genuinely abstract images).
 */
export function ExampleImageRow({
  companies,
  imageUrls,
  noun = "images",
}: {
  companies: string[];
  imageUrls: Record<string, string[]>;
  /** Disclosure label, e.g. "logos" vs "images". */
  noun?: string;
}) {
  const [expanded, setExpanded] = useState(false);

  if (companies.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1 text-[11px] text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer w-fit"
      >
        <ChevronDown size={12} className={`transition-transform ${expanded ? "rotate-180" : ""}`} />
        {expanded ? `Hide ${noun}` : `Show ${noun}`}
      </button>
      {expanded && (
        <div className="flex flex-col gap-2">
          {companies.map((c) => {
            const urls = imageUrls[c] || [];
            return (
              <div key={c} className="flex items-center gap-2">
                <span className="text-[10px] text-neutral-grey-20 w-28 shrink-0 truncate">{c}</span>
                <div className="flex flex-wrap gap-1.5">
                  {urls.length > 0 ? (
                    urls.map((url, i) => (
                      <div
                        key={i}
                        className="w-12 h-12 rounded-md bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden shrink-0"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={url} alt={`${c} ${noun} ${i + 1}`} className="max-w-full max-h-full object-contain p-1" />
                      </div>
                    ))
                  ) : (
                    <span className="text-[9px] text-neutral-grey-20">N/A</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
