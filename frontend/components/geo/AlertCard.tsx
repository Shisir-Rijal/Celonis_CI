import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { AlertTriangle } from "lucide-react";

import DashboardCard from "./DashboardCard";

type Priority = "high" | "medium" | "low";

type AlertCardProps = {
  category: string;
  text: string;
  priority?: Priority;
  recommendation?: string;
};

const priorityStyles: Record<
  Priority,
  { chipBg: string; chipText: string; icon: string }
> = {
  high: {
    chipBg: "bg-error/10",
    chipText: "text-error",
    icon: "text-error",
  },
  medium: {
    chipBg: "bg-warning/10",
    chipText: "text-warning",
    icon: "text-warning",
  },
  low: {
    chipBg: "bg-white/10",
    chipText: "text-neutral-grey-10",
    icon: "text-neutral-grey-10",
  },
};

/**
 * Alert card for the Deep Dive zone. One concept per card, scannable.
 *
 * Pattern: small uppercase category + coloured priority chip on top, one
 * concise text, optional recommendation line below with a warning icon.
 * Never used as a wall of text — one sentence each.
 */
export default function AlertCard({
  category,
  text,
  priority = "medium",
  recommendation,
}: AlertCardProps) {
  const styles = priorityStyles[priority];

  return (
    <DashboardCard className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-10 font-medium">
          {category}
        </span>
        <span
          className={twMerge(
            clsx(
              "px-2 py-0.5 rounded-full text-[10px] tracking-[0.12em] uppercase font-medium",
              styles.chipBg,
              styles.chipText
            )
          )}
        >
          {priority}
        </span>
      </div>

      <p className="text-sm text-primary-white leading-relaxed">{text}</p>

      {recommendation ? (
        <div
          className={twMerge(
            clsx(
              "flex items-start gap-2 text-sm border-t border-white/8 pt-3",
              styles.icon
            )
          )}
        >
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{recommendation}</span>
        </div>
      ) : null}
    </DashboardCard>
  );
}
