import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

type DashboardCardProps = {
  label?: string;
  sublabel?: string;
  children: React.ReactNode;
  className?: string;
};

/**
 * Light card used as the base container for every panel in the brand
 * dashboard. White surface, subtle 1px border, very soft shadow so cards
 * lift off the page canvas without competing with the data.
 *
 * Optional `label` renders as a small uppercase header. `sublabel` is a
 * normal-case helper line right under it (e.g. "vs. last 7 days").
 */
export default function DashboardCard({
  label,
  sublabel,
  children,
  className,
}: DashboardCardProps) {
  return (
    <div
      className={twMerge(
        clsx(
          "rounded-xl border border-black/5 bg-primary-white p-6",
          "shadow-[0_1px_2px_rgba(0,0,0,0.04)]",
          className
        )
      )}
    >
      {label ? (
        <div className="mb-5">
          <div className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
            {label}
          </div>
          {sublabel ? (
            <div className="mt-1 text-xs text-neutral-grey-20">{sublabel}</div>
          ) : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}
