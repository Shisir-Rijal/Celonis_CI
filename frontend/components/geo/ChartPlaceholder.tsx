import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

type ChartPlaceholderProps = {
  label?: string;
  height?: number;
  className?: string;
};

/**
 * Soft placeholder used while a chart is being built. Light surface,
 * dashed border, quiet uppercase label. Replace with the real
 * Recharts/Nivo component as each zone is implemented.
 */
export default function ChartPlaceholder({
  label = "CHART",
  height = 240,
  className,
}: ChartPlaceholderProps) {
  return (
    <div
      style={{ minHeight: height }}
      className={twMerge(
        clsx(
          "w-full flex items-center justify-center rounded-lg",
          "border border-dashed border-neutral-grey-10 bg-neutral-grey-00/60",
          "text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20",
          className
        )
      )}
    >
      {label}
    </div>
  );
}
