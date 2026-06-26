"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

import SectionHeader from "@components/geo/SectionHeader";

type SectionWrapperProps = {
  label: string;
  description?: string;
  action?: React.ReactNode;
  /** Whether the section starts expanded. Defaults to true. */
  defaultOpen?: boolean;
  className?: string;
  children: React.ReactNode;
};

/**
 * Standard collapsible wrapper for a page-level dashboard zone. Bundles the
 * disclosure chevron with `SectionHeader` so every section on a page gets
 * the same collapse/expand behaviour for free — just pass `label` /
 * `description` straight through.
 */
export default function SectionWrapper({
  label,
  description,
  action,
  defaultOpen = true,
  className,
  children,
}: SectionWrapperProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={twMerge(clsx("flex flex-col", className))}>
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={open ? `Collapse ${label}` : `Expand ${label}`}
          className="mt-1 shrink-0 text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer"
        >
          <ChevronDown
            size={18}
            className={clsx("transition-transform", !open && "-rotate-90")}
          />
        </button>
        <SectionHeader
          label={label}
          description={description}
          action={action}
          className="flex-1 mb-0"
        />
      </div>

      {open ? <div className="mt-5">{children}</div> : null}
    </section>
  );
}
