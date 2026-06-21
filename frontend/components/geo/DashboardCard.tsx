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
          "rounded-sm border-2 border-neutral-grey-30 p-6",
          className
        )
      )}
    >
      {label ? (
        <div className="mb-5">
          <div className="text-[24px] text-neutral-grey-00 font-medium">
            {label}
          </div>
          {sublabel ? (
            <div className="mt-1 text-sm text-neutral-grey-20">{sublabel}</div>
          ) : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}
