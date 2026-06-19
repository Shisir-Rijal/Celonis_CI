"use client";

import type { ReactNode } from "react";

/**
 * Generic "competitors converging on the same X" list — first used for
 * shared color families, reused for shared font styles. Anything with a
 * `companies` list and a `note` can plug in; callers supply the label and
 * the preview (swatches, font sample, etc.) themselves.
 */
export function SimilarGroups<T extends { companies: string[]; note: string | null }>({
  groups,
  emptyMessage,
  label,
  renderPreview,
}: {
  groups: T[];
  emptyMessage: string;
  label: (group: T) => string;
  renderPreview: (group: T) => ReactNode;
}) {
  if (groups.length === 0) {
    return <span className="text-sm text-neutral-grey-20">{emptyMessage}</span>;
  }

  return (
    <div className="flex flex-col">
      {groups.map((group) => (
        <div
          key={group.companies.join("-")}
          className="flex flex-col gap-2 py-4 border-b border-white/8 last:border-b-0"
        >
          <div className="flex items-center gap-2 flex-wrap">
            {renderPreview(group)}
            <span className="text-sm font-medium text-primary-white">
              {group.companies.join(" · ")}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full border bg-white/5 text-neutral-grey-20 border-white/10">
              {label(group)}
            </span>
          </div>
          {group.note && (
            <p className="text-xs text-neutral-grey-20 leading-relaxed">{group.note}</p>
          )}
        </div>
      ))}
    </div>
  );
}
