import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { ArrowUp, ArrowDown, Minus } from "lucide-react";

type DeltaDirection = "up" | "down" | "flat";

type KpiTileProps = {
  label: string;
  value: string | number;
  suffix?: string;
  subtitle?: string;
  delta?: {
    value: number;
    direction?: DeltaDirection;
    label?: string;
  } | null;
  highlight?: boolean;
};

function inferDirection(value: number): DeltaDirection {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

const directionStyles: Record<DeltaDirection, string> = {
  up: "text-success",
  down: "text-error",
  flat: "text-neutral-grey-20",
};

const directionIcons: Record<DeltaDirection, React.ReactNode> = {
  up: <ArrowUp size={12} strokeWidth={2.5} />,
  down: <ArrowDown size={12} strokeWidth={2.5} />,
  flat: <Minus size={12} strokeWidth={2.5} />,
};

/**
 * KPI tile — uppercase label, big number, subtitle, optional delta strip
 * at the bottom. Light surface, generous internal proximity so label and
 * number read as one unit.
 *
 * `highlight=true` adds a thin green accent bar at the top, marking a
 * "hero" tile (e.g. GEO Score) without colouring the number.
 */
export default function KpiTile({
  label,
  value,
  suffix,
  subtitle,
  delta,
  highlight = false,
}: KpiTileProps) {
  const direction = delta
    ? delta.direction ?? inferDirection(delta.value)
    : null;

  return (
    <div
      className={twMerge(
        clsx(
          "relative overflow-hidden rounded-xl border border-black/5 bg-primary-white p-6",
          "shadow-[0_1px_2px_rgba(0,0,0,0.04)] flex flex-col gap-2 min-h-[170px]"
        )
      )}
    >
      {highlight ? (
        <div className="absolute top-0 left-0 right-0 h-[3px] bg-secondary-green" />
      ) : null}

      {/* Tightly grouped: label + value + subtitle (proximity) */}
      <div className="flex flex-col gap-2">
        <span className="text-[11px] tracking-[0.16em] uppercase text-neutral-grey-20 font-medium">
          {label}
        </span>

        <div className="flex items-baseline gap-1">
          <span className="text-[44px] leading-none font-medium tracking-tight text-primary-black">
            {value}
          </span>
          {suffix ? (
            <span className="text-lg text-neutral-grey-20 font-normal">
              {suffix}
            </span>
          ) : null}
        </div>

        {subtitle ? (
          <span className="text-xs text-neutral-grey-20">{subtitle}</span>
        ) : null}
      </div>

      {/* Delta sits visually separated at the bottom */}
      {delta && direction ? (
        <div className="mt-auto pt-3">
          <div
            className={twMerge(
              clsx(
                "inline-flex items-center gap-1 text-xs font-medium",
                directionStyles[direction]
              )
            )}
          >
            {directionIcons[direction]}
            <span>
              {delta.value > 0 ? "+" : ""}
              {delta.value}
              {delta.label ? (
                <span className="text-neutral-grey-20 font-normal">
                  {" "}
                  {delta.label}
                </span>
              ) : null}
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
